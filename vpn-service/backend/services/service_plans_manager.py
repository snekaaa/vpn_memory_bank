"""
Централизованный сервис управления тарифными планами с персистентностью
"""

from typing import Dict, Any, Optional
import logging
import json
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config.database import get_db_session

logger = logging.getLogger(__name__)

class ServicePlansManager:
    """Централизованное управление тарифными планами"""
    
    def __init__(self):
        # Файл для сохранения планов
        self._plans_file = Path("/app/data/plans.json")
        self._plans_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Базовые планы (fallback если база данных недоступна)
        self._default_plans = {
            "monthly": {
                "id": "monthly", 
                "name": "Месячная подписка",
                "price": 199.0,
                "currency": "RUB",
                "duration": "30 дней",
                "duration_days": 30,
                "description": "VPN подписка на 1 месяц",
                "active": True
            },
            "quarterly": {
                "id": "quarterly",
                "name": "Квартальная подписка", 
                "price": 499.0,
                "currency": "RUB",
                "duration": "90 дней",
                "duration_days": 90,
                "description": "VPN подписка на 3 месяца",
                "discount": "17%",
                "active": True
            },
            "semi_annual": {
                "id": "semi_annual",
                "name": "Полугодовая подписка",
                "price": 899.0,
                "currency": "RUB",
                "duration": "180 дней",
                "duration_days": 180,
                "description": "VPN подписка на 6 месяцев",
                "discount": "25%",
                "active": True
            },
            "annual": {
                "id": "annual",
                "name": "Годовая подписка",
                "price": 1599.0,
                "currency": "RUB",
                "duration": "365 дней",
                "duration_days": 365,
                "description": "VPN подписка на 1 год",
                "discount": "33%",
                "active": True
            }
        }
        
        # Загружаем планы из файла если он существует
        self._load_plans_from_file()
    
    def _load_plans_from_file(self) -> None:
        """Загрузка планов из файла"""
        try:
            if self._plans_file.exists():
                with open(self._plans_file, 'r', encoding='utf-8') as f:
                    loaded_plans = json.load(f)
                    # Валидируем загруженные планы
                    if isinstance(loaded_plans, dict) and loaded_plans:
                        # Проверяем каждый план
                        valid_plans = {}
                        for plan_id, plan_data in loaded_plans.items():
                            if self._validate_plan(plan_data):
                                valid_plans[plan_id] = plan_data
                            else:
                                logger.warning(f"Invalid plan in file: {plan_id}")
                        
                        if valid_plans:
                            self._default_plans = valid_plans
                            logger.info(f"Loaded {len(valid_plans)} plans from file")
                        else:
                            logger.warning("No valid plans in file, using defaults")
                    else:
                        logger.warning("Invalid plans file format, using defaults")
            else:
                logger.info("Plans file not found, using defaults")
                # Сохраняем дефолтные планы в файл
                self._save_plans_to_file()
        except Exception as e:
            logger.error(f"Error loading plans from file: {e}")
            logger.info("Using default plans")
    
    def _save_plans_to_file(self) -> None:
        """Сохранение планов в файл"""
        try:
            with open(self._plans_file, 'w', encoding='utf-8') as f:
                json.dump(self._default_plans, f, indent=2, ensure_ascii=False)
            logger.debug("Plans saved to file")
        except Exception as e:
            logger.error(f"Error saving plans to file: {e}")
    
    def get_plans(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение всех активных тарифных планов (с fallback)
        
        Returns:
            Словарь с тарифными планами
        """
        try:
            # В будущем здесь можно будет загружать из базы данных
            # Пока возвращаем дефолтные планы
            plans = self._default_plans.copy()
            
            # Проверяем валидность планов
            if not plans or len(plans) == 0:
                logger.warning("No plans available, using fallback")
                plans = self._get_fallback_plans()
            
            # Проверяем, что у всех планов есть необходимые поля
            for plan_id, plan_data in plans.items():
                if not self._validate_plan(plan_data):
                    logger.warning(f"Invalid plan {plan_id}, using fallback")
                    plans = self._get_fallback_plans()
                    break

            # Убедимся что у всех планов есть валюта
            for plan_id, plan_data in plans.items():
                plan_data.setdefault('currency', 'RUB')
                    
            return plans
            
        except Exception as e:
            logger.error(f"Error getting service plans: {e}")
            return self._get_fallback_plans()
    
    def _validate_plan(self, plan_data: Dict[str, Any]) -> bool:
        """Валидация плана подписки"""
        required_fields = ["id", "name", "price", "duration", "duration_days", "description", "active"]
        return all(field in plan_data for field in required_fields)
    
    def get_plans_for_robokassa(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение планов, отформатированных для Robokassa
        """
        plans = self.get_plans()
        robokassa_plans = {}
        for plan_id, plan_data in plans.items():
            if plan_data.get("active", False):
                robokassa_plans[plan_id] = {
                    "id": plan_data["id"],
                    "name": plan_data["name"],
                    "price": plan_data["price"],
                    "currency": plan_data.get("currency", "RUB"),
                    "description": plan_data["description"],
                    "duration_days": plan_data["duration_days"]
                }
        return robokassa_plans

    def get_plans_for_bot(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение планов, отформатированных для Telegram бота
        Возвращает только активные планы с полным набором данных
        """
        plans = self.get_plans()
        bot_plans = {}
        for plan_id, plan_data in plans.items():
            if plan_data.get("active", True):  # По умолчанию активны
                bot_plans[plan_id] = plan_data.copy()
        return bot_plans

    def _get_fallback_plans(self) -> Dict[str, Dict[str, Any]]:
        """Получение fallback планов в случае критических ошибок"""
        return {
            "monthly": {
                "id": "monthly", 
                "name": "Месячная подписка",
                "price": 199.0,
                "currency": "RUB",
                "duration": "30 дней",
                "duration_days": 30,
                "description": "VPN подписка на 1 месяц",
                "active": True
            },
            "quarterly": {
                "id": "quarterly",
                "name": "Квартальная подписка", 
                "price": 499.0,
                "currency": "RUB",
                "duration": "90 дней",
                "duration_days": 90,
                "description": "VPN подписка на 3 месяца",
                "discount": "17%",
                "active": True
            }
        }
    
    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение конкретного тарифного плана
        
        Args:
            plan_id: ID плана
            
        Returns:
            Данные плана или None если не найден
        """
        plans = self.get_plans()
        return plans.get(plan_id)
    
    def update_plan(self, plan_id: str, plan_data: Dict[str, Any]) -> bool:
        """
        Обновление тарифного плана
        
        Args:
            plan_id: ID плана
            plan_data: Новые данные плана
            
        Returns:
            True если обновление прошло успешно
        """
        try:
            # Обновляем в памяти и сохраняем в файл
            if plan_id in self._default_plans:
                self._default_plans[plan_id].update(plan_data)
                self._save_plans_to_file()  # Сохраняем изменения
                logger.info(f"Updated plan {plan_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating service plan {plan_id}: {e}")
            return False
    
    def create_plan(self, plan_id: str, plan_data: Dict[str, Any]) -> bool:
        """
        Создание нового тарифного плана
        
        Args:
            plan_id: ID плана
            plan_data: Данные плана
            
        Returns:
            True если создание прошло успешно
        """
        try:
            if plan_id not in self._default_plans:
                self._default_plans[plan_id] = plan_data
                self._save_plans_to_file()  # Сохраняем изменения
                logger.info(f"Created plan {plan_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error creating service plan {plan_id}: {e}")
            return False
    
    def delete_plan(self, plan_id: str) -> bool:
        """
        Удаление тарифного плана
        
        Args:
            plan_id: ID плана
            
        Returns:
            True если удаление прошло успешно
        """
        try:
            if plan_id in self._default_plans:
                del self._default_plans[plan_id]
                self._save_plans_to_file()  # Сохраняем изменения
                logger.info(f"Deleted plan {plan_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting service plan {plan_id}: {e}")
            return False

# Создаем единственный экземпляр менеджера
service_plans_manager = ServicePlansManager() 