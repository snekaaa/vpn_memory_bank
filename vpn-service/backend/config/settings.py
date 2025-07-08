from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os

class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Основные настройки
    app_name: str = "VPN Service"
    debug: bool = False
    environment: str = "development"
    
    # База данных
    database_url: str = os.environ.get("DATABASE_URL", "postgresql+asyncpg://vpnuser:vpnpass@localhost/vpndb")
    postgres_db: str = "vpndb"
    postgres_user: str = "vpnuser"
    postgres_password: str = "vpnpass"
    
    # Безопасность
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # ЮKassa
    yookassa_shop_id: Optional[str] = None
    yookassa_secret_key: Optional[str] = None
    yookassa_webhook_secret: Optional[str] = None
    
    # Робокасса (настройки перенесены в БД через систему платежных провайдеров)
    
    # CoinGate (криптоплатежи)
    coingate_api_key: Optional[str] = None
    coingate_environment: str = "sandbox"  # sandbox или live
    coingate_webhook_secret: Optional[str] = None
    
    # 3X-UI Panel (DEPRECATED - используются настройки из БД для каждой ноды)
    # x3ui_api_url: str = ""  # Удалено - используется node.x3ui_url
    # x3ui_username: str = ""  # Удалено - используется node.x3ui_username  
    # x3ui_password: str = ""  # Удалено - используется node.x3ui_password
    # x3ui_server_ip убран - используем ноды из базы данных
    x3ui_default_inbound_id: int = 2  # Используется как fallback
    
    # Telegram Bot
    telegram_bot_token: str = "8062277246:AAESIC7inc1vnM6jXs3R6ZrfUh3m3FW-lHs"
    telegram_webhook_url: Optional[str] = None
    
    # Домен приложения
    app_domain: str = "https://raccoon-topical-ocelot.ngrok-free.app"
    
    # Redis (для Celery)
    redis_url: str = "redis://localhost:6379/0"
    
    # Sentry (мониторинг ошибок)
    sentry_dsn: Optional[str] = None
    
    # Логирование
    log_level: str = "INFO"
    
    # Trial Automation Settings
    trial_automation_enabled: bool = True
    trial_period_days: int = 3
    trial_max_per_user: int = 1
    trial_admin_user: str = "trial_automation"
    trial_description_template: str = "Автоматический триальный период - {days} дней"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"  # Разрешаем дополнительные поля из .env

@lru_cache()
def get_settings() -> Settings:
    """Получить настройки приложения (кешированные)"""
    return Settings() 