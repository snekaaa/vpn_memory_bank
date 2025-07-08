"""
Сервис кэширования тарифных планов
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

class PlansCacheService:
    """Сервис кэширования планов с TTL"""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 минут по умолчанию
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        
    async def get_cached_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Получить данные из кэша
        
        Args:
            cache_key: Ключ кэша
            
        Returns:
            Данные из кэша или None если данных нет или они устарели
        """
        async with self._lock:
            # Проверяем, есть ли данные в кэше
            if cache_key not in self._cache:
                logger.debug(f"Cache miss for key: {cache_key}")
                return None
                
            # Проверяем, не устарел ли кэш
            cache_time = self._cache_timestamps.get(cache_key)
            if cache_time is None:
                logger.debug(f"No timestamp for cache key: {cache_key}")
                return None
                
            if datetime.now() - cache_time > timedelta(seconds=self.ttl_seconds):
                logger.debug(f"Cache expired for key: {cache_key}")
                # Удаляем устаревшие данные
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
                return None
                
            logger.debug(f"Cache hit for key: {cache_key}")
            return self._cache[cache_key]
            
    async def set_cached_data(self, cache_key: str, data: Dict[str, Any]) -> None:
        """
        Сохранить данные в кэш
        
        Args:
            cache_key: Ключ кэша
            data: Данные для сохранения
        """
        async with self._lock:
            self._cache[cache_key] = data
            self._cache_timestamps[cache_key] = datetime.now()
            logger.debug(f"Data cached for key: {cache_key}")
            
    async def invalidate_cache(self, cache_key: Optional[str] = None) -> None:
        """
        Очистить кэш
        
        Args:
            cache_key: Ключ для очистки (если None, очищается весь кэш)
        """
        async with self._lock:
            if cache_key is None:
                # Очищаем весь кэш
                self._cache.clear()
                self._cache_timestamps.clear()
                logger.info("All cache cleared")
            else:
                # Очищаем конкретный ключ
                if cache_key in self._cache:
                    del self._cache[cache_key]
                if cache_key in self._cache_timestamps:
                    del self._cache_timestamps[cache_key]
                logger.info(f"Cache cleared for key: {cache_key}")
                
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Получить статистику кэша
        
        Returns:
            Статистика кэша
        """
        async with self._lock:
            now = datetime.now()
            valid_entries = 0
            expired_entries = 0
            
            for key, timestamp in self._cache_timestamps.items():
                if now - timestamp <= timedelta(seconds=self.ttl_seconds):
                    valid_entries += 1
                else:
                    expired_entries += 1
                    
            return {
                "total_entries": len(self._cache),
                "valid_entries": valid_entries,
                "expired_entries": expired_entries,
                "ttl_seconds": self.ttl_seconds,
                "cache_keys": list(self._cache.keys())
            }

# Глобальный экземпляр кэша
plans_cache = PlansCacheService(ttl_seconds=300)  # 5 минут TTL

# Декоратор для кэширования функций
def cache_with_ttl(cache_key: str, ttl_seconds: int = 300):
    """
    Декоратор для кэширования результатов функций
    
    Args:
        cache_key: Ключ для кэширования
        ttl_seconds: Время жизни кэша в секундах
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Создаем экземпляр кэша для этой функции
            cache_service = PlansCacheService(ttl_seconds=ttl_seconds)
            
            # Проверяем кэш
            cached_data = await cache_service.get_cached_data(cache_key)
            if cached_data is not None:
                logger.debug(f"Returning cached data for {func.__name__}")
                return cached_data
                
            # Выполняем функцию
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Сохраняем в кэш
            await cache_service.set_cached_data(cache_key, result)
            logger.debug(f"Cached new data for {func.__name__}")
            
            return result
        return wrapper
    return decorator

@lru_cache(maxsize=128)
def get_plans_lru_cache():
    """
    LRU кэш для быстрого доступа к планам
    Используется как fallback если основной кэш недоступен
    """
    from services.service_plans_manager import service_plans_manager
    try:
        return service_plans_manager.get_plans()
    except Exception as e:
        logger.error(f"Error in LRU cache: {e}")
        return {}

def invalidate_lru_cache():
    """Очистка LRU кэша"""
    get_plans_lru_cache.cache_clear()
    logger.info("LRU cache cleared") 