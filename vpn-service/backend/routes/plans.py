"""
API endpoints для управления тарифными планами
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from datetime import datetime
from services.service_plans_manager import service_plans_manager
from services.plans_cache import plans_cache, get_plans_lru_cache, invalidate_lru_cache
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])
security = HTTPBearer(auto_error=False)

class PlanCreate(BaseModel):
    """Схема для создания нового плана"""
    name: str
    price: float
    duration_days: int
    description: str
    discount: Optional[str] = None
    active: bool = True

class PlanUpdate(BaseModel):
    """Схема для обновления плана"""
    name: Optional[str] = None
    price: Optional[float] = None
    duration_days: Optional[int] = None
    description: Optional[str] = None
    discount: Optional[str] = None
    active: Optional[bool] = None

class PlanResponse(BaseModel):
    """Схема ответа плана"""
    id: str
    name: str
    price: float
    duration: str
    duration_days: int
    description: str
    discount: Optional[str] = None
    active: bool

@router.get("/", response_model=Dict[str, PlanResponse])
async def get_all_plans():
    """
    Получить все тарифные планы (с кэшированием)
    """
    try:
        # Проверяем кэш
        cached_plans = await plans_cache.get_cached_data("all_plans")
        if cached_plans is not None:
            logger.debug("Returning cached plans")
            return cached_plans
        
        # Получаем планы из сервиса
        plans = service_plans_manager.get_plans()
        
        # Сохраняем в кэш
        await plans_cache.set_cached_data("all_plans", plans)
        logger.debug("Plans cached successfully")
        
        return plans
    except Exception as e:
        logger.error(f"Error getting plans: {e}")
        # Fallback на LRU кэш
        try:
            fallback_plans = get_plans_lru_cache()
            logger.warning("Using LRU cache fallback")
            return fallback_plans
        except Exception as fe:
            logger.error(f"Fallback also failed: {fe}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при получении списка планов"
            )

@router.get("/bot", response_model=Dict[str, Dict[str, Any]])
async def get_plans_for_bot():
    """
    Получить планы в формате для Telegram бота (с кэшированием)
    """
    try:
        # Проверяем кэш
        cached_bot_plans = await plans_cache.get_cached_data("bot_plans")
        if cached_bot_plans is not None:
            logger.debug("Returning cached bot plans")
            return cached_bot_plans
        
        # Получаем планы из сервиса
        bot_plans = service_plans_manager.get_plans_for_bot()
        
        # Сохраняем в кэш
        await plans_cache.set_cached_data("bot_plans", bot_plans)
        logger.info(f"Bot plans loaded and cached: {len(bot_plans)} active plans")
        
        return bot_plans
    except Exception as e:
        logger.error(f"Error getting bot plans: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении планов для бота"
        )

@router.get("/health", response_model=Dict[str, Any])
async def plans_health_check():
    """
    Health check для системы планов подписок
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "plans_api",
            "version": "1.0.0"
        }
        
        # Проверяем доступность планов
        try:
            plans = service_plans_manager.get_plans()
            health_status["plans_count"] = len(plans)
            health_status["plans_available"] = True
        except Exception as e:
            health_status["plans_available"] = False
            health_status["plans_error"] = str(e)
            health_status["status"] = "degraded"
        
        # Проверяем кэш
        try:
            cache_stats = await plans_cache.get_cache_stats()
            health_status["cache"] = {
                "available": True,
                "entries": cache_stats["total_entries"],
                "valid_entries": cache_stats["valid_entries"]
            }
        except Exception as e:
            health_status["cache"] = {
                "available": False,
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Проверяем LRU кэш
        try:
            lru_plans = get_plans_lru_cache()
            health_status["lru_cache"] = {
                "available": True,
                "entries": len(lru_plans)
            }
        except Exception as e:
            health_status["lru_cache"] = {
                "available": False,
                "error": str(e)
            }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@router.get("/metrics", response_model=Dict[str, Any])
async def plans_metrics():
    """
    Метрики производительности системы планов
    """
    try:
        # Получаем статистику кэша
        cache_stats = await plans_cache.get_cache_stats()
        
        # Проверяем время ответа API
        start_time = datetime.now()
        plans = service_plans_manager.get_plans()
        response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "api_response_time_ms": round(response_time_ms, 2),
            "total_plans": len(plans),
            "active_plans": len([p for p in plans.values() if p.get("active", True)]),
            "cache": cache_stats,
            "endpoints": {
                "get_all_plans": "/api/v1/plans/",
                "get_bot_plans": "/api/v1/plans/bot",
                "get_plan_by_id": "/api/v1/plans/{plan_id}",
                "create_plan": "POST /api/v1/plans/",
                "update_plan": "PUT /api/v1/plans/{plan_id}",
                "delete_plan": "DELETE /api/v1/plans/{plan_id}"
            }
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении метрик"
        )

@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan_by_id(plan_id: str):
    """
    Получить конкретный тарифный план по ID
    """
    try:
        plan = service_plans_manager.get_plan(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"План с ID {plan_id} не найден"
            )
        return plan
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plan {plan_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении плана"
        )

@router.post("/", response_model=Dict[str, str])
async def create_plan(plan_id: str, plan_data: PlanCreate):
    """
    Создать новый тарифный план
    """
    try:
        # Проверяем, что план не существует
        existing_plan = service_plans_manager.get_plan(plan_id)
        if existing_plan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"План с ID {plan_id} уже существует"
            )
        
        # Формируем данные плана
        new_plan_data = {
            "id": plan_id,
            "name": plan_data.name,
            "price": plan_data.price,
            "duration": f"{plan_data.duration_days} дней",
            "duration_days": plan_data.duration_days,
            "description": plan_data.description,
            "discount": plan_data.discount,
            "active": plan_data.active
        }
        
        success = service_plans_manager.create_plan(plan_id, new_plan_data)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось создать план"
            )
        
        await invalidate_lru_cache()
        await plans_cache.invalidate_cache("all_plans")
        await plans_cache.invalidate_cache("bot_plans")
        
        return {"status": "success", "message": f"План {plan_id} успешно создан"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating plan {plan_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при создании плана"
        )

@router.put("/{plan_id}", response_model=Dict[str, str])
async def update_plan(plan_id: str, plan_data: PlanUpdate):
    """
    Обновить тарифный план
    """
    try:
        # Проверяем, что план существует
        existing_plan = service_plans_manager.get_plan(plan_id)
        if not existing_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"План с ID {plan_id} не найден"
            )
        
        # Формируем данные для обновления
        update_data = plan_data.dict(exclude_unset=True)
        
        # Обновляем duration если нужно
        if 'duration_days' in update_data:
            update_data['duration'] = f"{update_data['duration_days']} дней"
            
        success = service_plans_manager.update_plan(plan_id, update_data)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось обновить план"
            )
        
        await invalidate_lru_cache()
        await plans_cache.invalidate_cache("all_plans")
        await plans_cache.invalidate_cache("bot_plans")
        
        return {"status": "success", "message": f"План {plan_id} успешно обновлен"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating plan {plan_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении плана"
        )

@router.delete("/{plan_id}", response_model=Dict[str, str])
async def delete_plan(plan_id: str):
    """
    Удалить тарифный план
    """
    try:
        # Проверяем, что план существует
        existing_plan = service_plans_manager.get_plan(plan_id)
        if not existing_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"План с ID {plan_id} не найден"
            )
        
        success = service_plans_manager.delete_plan(plan_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось удалить план"
            )
        
        await invalidate_lru_cache()
        await plans_cache.invalidate_cache("all_plans")
        await plans_cache.invalidate_cache("bot_plans")
        
        return {"status": "success", "message": f"План {plan_id} успешно удален"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting plan {plan_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при удалении плана"
        )
        
@router.get("/cache/stats", response_model=Dict[str, Any])
async def get_cache_stats():
    """
    Получить статистику Redis кэша
    """
    try:
        stats = await plans_cache.get_cache_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики кэша")

@router.post("/cache/clear", response_model=Dict[str, str])
async def clear_cache():
    """
    Очистить Redis кэш планов
    """
    try:
        await plans_cache.invalidate_cache()
        await invalidate_lru_cache()
        return {"status": "success", "message": "Кэш планов успешно очищен"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Ошибка очистки кэша") 