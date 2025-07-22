from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os

class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Системные настройки (остаются в ENV)
    debug: bool = False
    environment: str = "development"
    
    # База данных
    database_url: str = os.environ.get("DATABASE_URL", "postgresql+asyncpg://vpnuser:vpnpass@localhost/vpndb")
    
    # Безопасность (критично для безопасности - остается в ENV)
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    
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
    
    # Настройки теперь в БД через app_settings:
    # - app_name → app_settings.site_name
    # - telegram_bot_token → app_settings.telegram_bot_token  
    # - access_token_expire_minutes → app_settings.token_expire_minutes
    # - admin_telegram_ids → app_settings.admin_telegram_ids
    # - admin_usernames → app_settings.admin_usernames
    
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