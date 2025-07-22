"""
Настройки приложения
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import find_dotenv, load_dotenv
from functools import lru_cache
from typing import Optional, List

# Загрузка переменных окружения из .env файла
env_file = find_dotenv()
load_dotenv(env_file)

class Settings(BaseSettings):
    """Настройки бота и приложения"""
    
    # Базовые настройки
    APP_NAME: str = Field("VPN Telegram Bot", description="Название приложения")
    DEBUG: bool = Field(False, description="Режим отладки")
    
    # Настройки Telegram Bot API
    TELEGRAM_TOKEN: str = Field(os.getenv("TELEGRAM_BOT_TOKEN", ""), alias="TELEGRAM_BOT_TOKEN", 
                              description="Токен Telegram API")
    # Совместимость со старым кодом
    telegram_bot_token: str = Field(os.getenv("TELEGRAM_BOT_TOKEN", ""), description="Токен Telegram API (совместимость)")
    telegram_webhook_url: Optional[str] = None
    
    # Настройки для сервера X-UI
    XUI_API_URL: str = Field(os.getenv("XUI_API_URL", "http://admin.example.com:5478"), 
                           description="URL API сервера X-UI")
    XUI_USERNAME: str = Field(os.getenv("XUI_USERNAME", "admin"), 
                            description="Имя пользователя X-UI")
    XUI_PASSWORD: str = Field(os.getenv("XUI_PASSWORD", "admin"), 
                            description="Пароль X-UI")
    XUI_HOST: str = Field(os.getenv("XUI_HOST", "78.40.193.142"), 
                        description="Хост VPN сервера")
    XUI_PORT: int = Field(os.getenv("XUI_PORT", 443), 
                        description="Порт VPN сервера")
    
    # Для совместимости со старым кодом
    xui_username: str = Field(os.getenv("XUI_USERNAME", "admin"), description="X-UI Username (совместимость)")
    xui_password: str = Field(os.getenv("XUI_PASSWORD", "H23Dtz5W33mw6dFL"), description="X-UI Password (совместимость)")
    xui_domain: str = Field(os.getenv("XUI_HOST", "78.40.193.142"), description="X-UI Domain (совместимость)")
    
    # Настройки для БД PostgreSQL
    DATABASE_URL: str = Field(os.getenv("DATABASE_URL", "postgresql://vpn_user:vpn_password@db:5432/vpn_db"),
                            description="URL подключения к базе данных PostgreSQL")
    
    # Для совместимости со старым кодом (нижний регистр)
    database_url: str = Field(os.getenv("DATABASE_URL", "postgresql://vpn_user:vpn_password@db:5432/vpn_db"),
                            description="URL подключения к базе данных (совместимость)")
    
    # Совместимость с предыдущей версией - для backend API
    backend_api_url: str = Field(os.getenv("BACKEND_API_URL", "http://backend:8000"), description="Backend API URL")
    api_timeout: int = 30
    
    # Пути к файлам
    BASE_DIR: Path = Path(__file__).parent.parent
    
    # Payments
    payment_timeout_minutes: int = 15
    
    # Subscription prices (в рублях)
    trial_price: int = 0
    monthly_price: int = 0
    quarterly_price: int = 0
    yearly_price: int = 0
    
    # Messaging
    max_message_length: int = 4096
    
    # Redis (для состояний FSM в продакшене)
    redis_url: Optional[str] = None
    
    # Admin Configuration - определяются через property для избежания конфликтов с pydantic
    admin_log_enabled: bool = True
    admin_session_timeout: int = 3600  # 1 hour

    # ПРИМЕЧАНИЕ: admin_telegram_ids и admin_usernames теперь берутся из БД
    # через app_settings. Эти методы оставлены для совместимости со старым кодом
    # и используют fallback значения если БД недоступна
    
    @property
    def admin_telegram_ids(self) -> List[int]:
        """Получить список админских Telegram ID (fallback из ENV)"""
        env_admin_ids = os.getenv('ADMIN_TELEGRAM_IDS')
        if env_admin_ids:
            try:
                return [int(id.strip()) for id in env_admin_ids.split(',') if id.strip()]
            except ValueError:
                pass
        # Дефолтные значения (если БД недоступна)
        return [352313872]  # av_nosov admin ID

    @property
    def admin_usernames(self) -> List[str]:
        """Получить список админских username (fallback из ENV)"""
        env_admin_usernames = os.getenv('ADMIN_USERNAMES')
        if env_admin_usernames:
            return [username.strip() for username in env_admin_usernames.split(',') if username.strip()]
        # Дефолтные значения (если БД недоступна)
        return ["av_nosov", "seo2seo"]
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "allow"  # Разрешаем дополнительные поля, не указанные в модели
    }

@lru_cache()
def get_settings() -> Settings:
    """Получение настроек приложения"""
    return Settings()

# Глобальный экземпляр настроек для быстрого доступа
settings = get_settings()

@lru_cache()
def get_bot_settings() -> Settings:
    """Alias for get_settings for compatibility"""
    return get_settings() 