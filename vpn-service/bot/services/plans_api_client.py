"""
API клиент для получения планов подписок из backend
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class PlansAPIClient:
    """Клиент для работы с API планов подписок"""
    
    def __init__(self, api_base_url: str = "http://backend:8000"):
        self.api_base_url = api_base_url
        self.timeout = aiohttp.ClientTimeout(total=10)
        
        # Локальный кэш с TTL
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=1)  # 1 минута TTL для быстрых обновлений
        
        # Fallback планы УДАЛЕНЫ - всегда используем API/БД
        self._fallback_plans = {}
    
    def _is_cache_valid(self) -> bool:
        """Проверка валидности кэша"""
        if self._cache is None or self._cache_timestamp is None:
            return False
        return datetime.now() - self._cache_timestamp < self._cache_ttl
    
    async def _fetch_plans_from_api(self) -> Dict[str, Any]:
        """
        Загрузка планов из API
        
        Returns:
            Словарь с планами подписок
        """
        url = f"{self.api_base_url}/api/v1/plans/bot"
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Successfully loaded {len(data)} plans from API")
                        return data
                    else:
                        logger.error(f"API returned status {response.status}")
                        raise Exception(f"API error: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.error("Timeout when fetching plans from API")
            raise Exception("API timeout")
        except aiohttp.ClientError as e:
            logger.error(f"Client error when fetching plans: {e}")
            raise Exception(f"Client error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error when fetching plans: {e}")
            raise
    
    async def get_plans(self) -> Dict[str, Any]:
        """
        Получить планы подписок (с кэшированием и fallback)
        
        Returns:
            Словарь с планами подписок
        """
        # Проверяем локальный кэш
        if self._is_cache_valid():
            logger.debug("Returning cached plans")
            return self._cache
        
        try:
            # Пытаемся загрузить из API
            plans = await self._fetch_plans_from_api()
            
            # Обновляем кэш
            self._cache = plans
            self._cache_timestamp = datetime.now()
            
            return plans
            
        except Exception as e:
            logger.error(f"Failed to load plans from API: {e}")
            
            # Если есть устаревший кэш, используем его
            if self._cache is not None:
                logger.warning("Using stale cache as fallback")
                return self._cache
            
            # Больше никаких fallback планов - показываем ошибку
            logger.error("No plans available - API is down and no cache")
            raise Exception("Plans API is unavailable and no cached data")
    
    async def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить конкретный план подписки
        
        Args:
            plan_id: ID плана
            
        Returns:
            Данные плана или None
        """
        try:
            plans = await self.get_plans()
            return plans.get(plan_id)
        except Exception as e:
            logger.error(f"Error getting plan {plan_id}: {e}")
            return None
    
    async def invalidate_cache(self) -> None:
        """Принудительно очистить локальный кэш"""
        self._cache = None
        self._cache_timestamp = None
        logger.info("Plans cache invalidated")
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """
        Получить информацию о состоянии кэша
        
        Returns:
            Информация о кэше
        """
        return {
            "cache_exists": self._cache is not None,
            "cache_valid": self._is_cache_valid(),
            "cache_timestamp": self._cache_timestamp.isoformat() if self._cache_timestamp else None,
            "cache_ttl_minutes": self._cache_ttl.total_seconds() / 60,
            "plans_count": len(self._cache) if self._cache else 0,
            "api_base_url": self.api_base_url
        }

# Глобальный экземпляр клиента
plans_api_client = PlansAPIClient() 