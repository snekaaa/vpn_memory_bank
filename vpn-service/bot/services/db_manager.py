"""
Модуль для работы с PostgreSQL базой данных
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
import structlog
from datetime import datetime
from sqlalchemy import text

logger = structlog.get_logger(__name__)
Base = declarative_base()

class User(Base):
    """Модель пользователя Telegram"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Отношение к VPN ключам (один ко многим)
    vpn_keys = relationship("VPNKey", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class VPNKey(Base):
    """Модель VPN ключа"""
    __tablename__ = 'vpn_keys'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    uuid = Column(String(36), nullable=False)
    vless_url = Column(Text, nullable=False)
    xui_email = Column(String(255), nullable=False)
    xui_inbound_id = Column(Integer, nullable=False)
    xui_client_id = Column(String(36), nullable=True)  # UUID клиента в X3UI панели, должен совпадать с uuid
    xui_created = Column(Boolean, default=True)
    subscription_type = Column(String(50), default='auto')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношение к пользователю (многие к одному)
    user = relationship("User", back_populates="vpn_keys")
    
    def __repr__(self):
        return f"<VPNKey(id={self.id}, uuid={self.uuid})>"


class DBManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self):
        """Инициализация соединения с базой данных"""
        try:
            database_url = os.getenv('DATABASE_URL', 'postgresql://vpn_user:vpn_password@db:5432/vpn_db')
            logger.info("Initializing database connection", db_url=database_url.split('@')[1])
            
            # Создаем синхронный engine для стандартных операций
            self.engine = create_engine(
                database_url,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800
            )
            self.Session = sessionmaker(bind=self.engine)
            
            # Проверяем соединение синхронно
            self.engine.connect().close()
            logger.info("Database connection established successfully")
        except Exception as e:
            logger.error("Error initializing database connection", error=str(e))
            raise
    
    def create_tables(self):
        """Создание таблиц в базе данных (синхронно)"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created successfully")
            
            # Создаем индексы для оптимизации с использованием text()
            try:
                with self.engine.begin() as conn:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vpn_keys_user_id ON vpn_keys(user_id)"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)"))
                
                logger.info("Database indexes created successfully")
            except Exception as e:
                logger.error("Error creating database indexes", error=str(e))
            
            return True
        except Exception as e:
            logger.error("Error creating database tables", error=str(e))
            return False
    
    def get_or_create_user(self, telegram_id, username=None, first_name=None, last_name=None):
        """Получение пользователя из БД, если не существует - создание нового"""
        session = self.Session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                logger.info("Creating new user", telegram_id=telegram_id)
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
                session.commit()
            return user
        except Exception as e:
            logger.error("Error getting or creating user", 
                        telegram_id=telegram_id,
                        error=str(e))
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_user_by_telegram_id(self, telegram_id):
        """Получение пользователя по ID Telegram"""
        session = self.Session()
        try:
            return session.query(User).filter_by(telegram_id=telegram_id).first()
        except Exception as e:
            logger.error("Error getting user by telegram_id", 
                        telegram_id=telegram_id,
                        error=str(e))
            return None
        finally:
            session.close()
    
    def get_vpn_key_by_id(self, key_id):
        """Получение VPN ключа по ID"""
        session = self.Session()
        try:
            return session.query(VPNKey).filter_by(id=key_id).first()
        except Exception as e:
            logger.error("Error getting VPN key by id", key_id=key_id, error=str(e))
            return None
        finally:
            session.close()
    
    def get_vpn_keys_by_telegram_id(self, telegram_id):
        """Получение VPN ключей пользователя по telegram_id"""
        session = self.Session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return []
            
            return session.query(VPNKey).filter_by(user_id=user.id).all()
        except Exception as e:
            logger.error("Error getting VPN keys", 
                        telegram_id=telegram_id,
                        error=str(e))
            return []
        finally:
            session.close() 