"""
App Settings Service
Сервис для управления настройками приложения с кешированием
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from cachetools import TTLCache
import json
import structlog

from models.app_settings import AppSettings

logger = structlog.get_logger(__name__)

# Глобальный кеш настроек (TTL = 5 минут)
settings_cache = TTLCache(maxsize=1, ttl=300)


class AppSettingsService:
    """Сервис для работы с настройками приложения"""
    
    @staticmethod
    async def get_settings(db: AsyncSession) -> AppSettings:
        """
        Получить настройки с кешированием
        Создает настройки по умолчанию если их нет
        """
        cache_key = "app_settings_v1"
        
        # Проверяем кеш
        if cache_key in settings_cache:
            logger.info("Settings loaded from cache")
            return settings_cache[cache_key]
        
        # Загружаем из БД
        settings = await AppSettingsService._fetch_settings_from_db(db)
        
        # Кешируем
        settings_cache[cache_key] = settings
        logger.info("Settings loaded from database and cached")
        
        return settings
    
    @staticmethod
    async def _fetch_settings_from_db(db: AsyncSession) -> AppSettings:
        """Получить настройки из БД, создать если не существуют"""
        stmt = select(AppSettings).where(AppSettings.id == 1)
        result = await db.execute(stmt)
        settings = result.scalar_one_or_none()
        
        if settings is None:
            # Создаем настройки по умолчанию
            settings = AppSettings(
                id=1,
                site_name="VPN Service",
                trial_enabled=True,
                trial_days=7,
                trial_max_per_user=1,
                token_expire_minutes=30,
                admin_telegram_ids='["352313872"]',
                admin_usernames='["av_nosov", "seo2seo"]',
                bot_apps_message="Скачайте приложения для вашего устройства:"
            )
            db.add(settings)
            await db.commit()
            await db.refresh(settings)
            logger.info("Created default app settings")
        
        return settings
    
    @staticmethod
    async def update_settings(db: AsyncSession, settings_data: Dict[str, Any]) -> AppSettings:
        """
        Обновить настройки приложения
        """
        # Получаем текущие настройки
        settings = await AppSettingsService._fetch_settings_from_db(db)
        
        # Обновляем поля
        for key, value in settings_data.items():
            if hasattr(settings, key):
                # Специальная обработка для списков admin IDs/usernames
                if key == 'admin_telegram_ids' and isinstance(value, str):
                    # Парсим строку "123,456" в JSON массив строк
                    try:
                        ids = [x.strip() for x in value.split(',') if x.strip()]
                        settings.admin_telegram_ids = json.dumps(ids)
                    except ValueError:
                        logger.warning(f"Invalid admin_telegram_ids format: {value}")
                        continue
                elif key == 'admin_usernames' and isinstance(value, str):
                    # Парсим строку "user1,user2" в JSON массив
                    usernames = [x.strip() for x in value.split(',') if x.strip()]
                    settings.admin_usernames = json.dumps(usernames)
                else:
                    setattr(settings, key, value)
                    
                logger.info(f"Updated setting {key} = {value}")
        
        await db.commit()
        await db.refresh(settings)
        
        # Очищаем кеш для принудительного обновления
        AppSettingsService.invalidate_cache()
        
        logger.info("App settings updated successfully")
        return settings
    
    @staticmethod
    async def reset_to_defaults(db: AsyncSession) -> AppSettings:
        """
        Сброс настроек к значениям по умолчанию
        """
        # Удаляем существующие настройки
        await db.execute(update(AppSettings).where(AppSettings.id == 1).values(
            site_name="VPN Service",
            site_domain=None,
            site_description=None,
            trial_enabled=True,
            trial_days=7,
            trial_max_per_user=1,
            token_expire_minutes=30,
            admin_telegram_ids='["352313872"]',
            admin_usernames='["av_nosov", "seo2seo"]',
            telegram_bot_token=None,
            bot_welcome_message=None,
            bot_help_message=None,
            bot_apps_message="Скачайте приложения для вашего устройства:"
        ))
        
        await db.commit()
        
        # Очищаем кеш
        AppSettingsService.invalidate_cache()
        
        # Возвращаем обновленные настройки
        settings = await AppSettingsService._fetch_settings_from_db(db)
        logger.info("App settings reset to defaults")
        return settings
    
    @staticmethod
    def invalidate_cache():
        """Принудительная очистка кеша настроек"""
        settings_cache.clear()
        logger.info("Settings cache invalidated")
    
    @staticmethod
    async def get_setting_value(db: AsyncSession, key: str, default=None):
        """Получить значение конкретной настройки"""
        settings = await AppSettingsService.get_settings(db)
        return getattr(settings, key, default)
    
    @staticmethod
    async def is_admin_telegram_id(db: AsyncSession, telegram_id: int) -> bool:
        """Проверить является ли telegram_id админским"""
        settings = await AppSettingsService.get_settings(db)
        admin_ids = settings.admin_telegram_ids_list
        # Преобразуем telegram_id в строку для сравнения
        return str(telegram_id) in admin_ids
    
    @staticmethod
    async def is_admin_username(db: AsyncSession, username: str) -> bool:
        """Проверить является ли username админским"""
        settings = await AppSettingsService.get_settings(db)
        admin_usernames = settings.admin_usernames_list
        return username in admin_usernames


# Функция для получения настроек (для совместимости с существующим кодом)
async def get_app_settings(db: AsyncSession) -> AppSettings:
    """Получить настройки приложения"""
    return await AppSettingsService.get_settings(db) 