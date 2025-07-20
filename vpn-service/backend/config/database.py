from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)
settings = get_settings()

# Fallback для debug если атрибута нет
debug_mode = getattr(settings, 'debug', False)

# Создание движка базы данных
# Для SQLite убираем параметры пула подключений
if settings.database_url.startswith("sqlite"):
    engine = create_async_engine(
        settings.database_url,
        echo=debug_mode,
        connect_args={"check_same_thread": False}
    )
else:
    # Для других БД используем полную конфигурацию
    engine = create_async_engine(
        settings.database_url,
        echo=debug_mode,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

# Создание фабрики сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
    )

async def get_db() -> AsyncSession:
    """Получить сессию базы данных"""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            logger.error("Database session error", error=str(e))
            await session.rollback()
            raise
        finally:
            await session.close()

def get_db_session() -> AsyncSession:
    """Получить новую сессию базы данных (без dependency injection)"""
    return async_session_maker()

async def init_database():
    """Инициализация базы данных"""
    try:
        # Импортируем все модели для создания таблиц
        from models.user import User
        from models.subscription import Subscription
        from models.payment import Payment
        from models.payment_provider import PaymentProvider
        from models.vpn_key import VPNKey
        from models.vpn_node import VPNNode
        from models.user_node_assignment import UserNodeAssignment
        
        async with engine.begin() as conn:
            # Создаем все таблицы
            await conn.run_sync(Base.metadata.create_all)
            logger.info("База данных инициализирована")
    except Exception as e:
        logger.error("Ошибка инициализации базы данных", error=str(e))
        raise 