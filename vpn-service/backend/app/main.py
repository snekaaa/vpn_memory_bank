from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import structlog
from config.database import engine, get_db
from config.settings import get_settings
from routes import auth, users, subscriptions, payments, vpn_keys, webhooks, integration, health_check, test_routes
from models import database
import os

logger = structlog.get_logger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Обработка запуска и остановки приложения"""
    # Инициализация БД
    logger.info("Инициализация базы данных...")
    await database.init_database()
    yield
    # Очистка ресурсов
    logger.info("Остановка приложения...")

app = FastAPI(
    title=settings.app_name,
    description="VPN Service API with Telegram Bot Integration",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение статических файлов
# Проверяем существование директории
static_dir = "app/static"
if not os.path.exists(static_dir):
    # Если директория не существует, используем путь относительно корня проекта
    static_dir = "backend/app/static"
    if not os.path.exists(static_dir):
        logger.warning(f"Static directory not found at {static_dir}, falling back to backend/static")
        static_dir = "backend/static"

logger.info(f"Mounting static files from: {static_dir}")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Подключение роутеров
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(vpn_keys.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(integration.router, prefix="/api/v1")
app.include_router(health_check.router, prefix="/api/v1")
app.include_router(test_routes.router, prefix="/test")

# Подключение админки
from app.admin.routes import router as admin_router
app.include_router(admin_router)

@app.get("/")
async def root():
    """Корневой эндпоинт API"""
    return {
        "message": "VPN Service API with Integration",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "integration": "/api/v1/integration/"
    }

@app.get("/health")
async def health_check():
    """Проверка состояния приложения"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.environment
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 