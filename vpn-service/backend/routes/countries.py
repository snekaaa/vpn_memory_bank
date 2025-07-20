"""
Country Management API Routes
Обеспечивает API endpoints для управления странами VPN серверов
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import structlog

from config.database import get_db
from services.country_service import CountryService
from services.user_server_service import UserServerService, NodeSelectionResult

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/countries", tags=["countries"])


@router.get("/available", response_model=List[dict])
async def get_available_countries(db: AsyncSession = Depends(get_db)):
    """
    Получить список активных стран с доступными VPN серверами
    
    Returns:
        List[dict]: Список стран с ключами {id, code, name, flag_emoji, display_name}
    """
    try:
        country_service = CountryService(db)
        countries = await country_service.get_available_countries()
        
        result = [country.to_dict() for country in countries]
        
        logger.info("Available countries fetched", count=len(result))
        return result
        
    except Exception as e:
        logger.error("Failed to fetch available countries", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch countries")


@router.get("/{country_code}/nodes", response_model=List[dict])
async def get_country_nodes(
    country_code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список активных нод для указанной страны
    
    Args:
        country_code: ISO код страны (RU, NL, DE)
    
    Returns:
        List[dict]: Список нод с информацией о загрузке и здоровье
    """
    try:
        country_service = CountryService(db)
        
        # Получаем страну по коду
        country = await country_service.get_country_by_code(country_code.upper())
        if not country:
            raise HTTPException(status_code=404, detail=f"Country {country_code} not found")
        
        # Получаем ноды для страны
        nodes = await country_service.get_nodes_by_country(country.id)
        
        result = []
        for node in nodes:
            result.append({
                "id": node.id,
                "name": node.name,
                "description": node.description,
                "location": node.location,
                "status": node.status,
                "health_status": node.health_status,
                "load_percentage": node.load_percentage,
                "current_users": node.current_users,
                "max_users": node.max_users,
                "priority": node.priority,
                "response_time_ms": node.response_time_ms,
                "can_accept_users": node.can_accept_users
            })
        
        logger.info("Country nodes fetched", 
                   country_code=country_code, 
                   nodes_count=len(result))
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch country nodes", 
                    country_code=country_code, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch country nodes")


@router.post("/switch", response_model=dict)
async def switch_user_country(
    user_id: int,
    country_code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Переключить пользователя на сервер в указанной стране
    
    Args:
        user_id: Telegram ID пользователя
        country_code: ISO код целевой страны
    
    Returns:
        dict: Результат переключения с информацией о новом сервере
    """
    try:
        user_server_service = UserServerService(db)
        
        # Выполняем переключение
        result = await user_server_service.assign_user_to_country(user_id, country_code.upper())
        
        if result.success:
            response = {
                "success": True,
                "node_id": result.node.id if result.node else None,
                "node_name": result.node.name if result.node else None,
                "country_code": country_code.upper(),
                "processing_time_ms": result.processing_time_ms,
                "fallback_used": result.fallback_used,
                "message": result.error_message if result.fallback_used else "Switch successful"
            }
            
            logger.info("User country switch successful", 
                       user_id=user_id,
                       country_code=country_code,
                       node_id=result.node.id if result.node else None,
                       processing_time=result.processing_time_ms)
            return response
        else:
            logger.error("User country switch failed", 
                        user_id=user_id,
                        country_code=country_code,
                        error=result.error_message)
            raise HTTPException(
                status_code=400, 
                detail={
                    "success": False,
                    "error": result.error_message,
                    "processing_time_ms": result.processing_time_ms
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to switch user country", 
                    user_id=user_id,
                    country_code=country_code,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to switch country")


@router.get("/user/{user_id}/assignment", response_model=dict)
async def get_user_server_assignment(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить текущее назначение пользователя на сервер
    
    Args:
        user_id: Telegram ID пользователя
    
    Returns:
        dict: Информация о текущем назначении или null
    """
    try:
        user_server_service = UserServerService(db)
        country_service = CountryService(db)
        
        # Получаем текущее назначение
        assignment = await user_server_service.get_user_current_assignment(user_id)
        
        if assignment:
            # Получаем информацию о стране
            country = await country_service.get_country_by_id(assignment.country_id)
            
            result = {
                "user_id": assignment.user_id,
                "node_id": assignment.node_id,
                "country": country.to_dict() if country else None,
                "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                "last_switch_at": assignment.last_switch_at.isoformat() if assignment.last_switch_at else None
            }
            
            logger.info("User assignment fetched", 
                       user_id=user_id,
                       node_id=assignment.node_id,
                       country_code=country.code if country else None)
            return result
        else:
            logger.info("No assignment found for user", user_id=user_id)
            return {"user_id": user_id, "assignment": None}
            
    except Exception as e:
        logger.error("Failed to fetch user assignment", 
                    user_id=user_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch user assignment")


@router.get("/stats", response_model=dict)
async def get_country_statistics(
    db: AsyncSession = Depends(get_db)
):
    """
    Получить статистику по странам и серверам
    
    Returns:
        dict: Статистика по странам, нодам и пользователям
    """
    try:
        country_service = CountryService(db)
        
        countries = await country_service.get_available_countries()
        
        stats = {
            "total_countries": len(countries),
            "countries": []
        }
        
        for country in countries:
            nodes = await country_service.get_nodes_by_country(country.id)
            
            # Подсчитываем статистику по нодам
            total_nodes = len(nodes)
            healthy_nodes = len([n for n in nodes if n.is_healthy])
            total_capacity = sum(n.max_users for n in nodes)
            total_users = sum(n.current_users for n in nodes)
            avg_load = (total_users / total_capacity * 100) if total_capacity > 0 else 0
            
            country_stats = {
                "country": country.to_dict(),
                "nodes_total": total_nodes,
                "nodes_healthy": healthy_nodes,
                "total_capacity": total_capacity,
                "current_users": total_users,
                "average_load_percentage": round(avg_load, 1),
                "availability": healthy_nodes > 0
            }
            
            stats["countries"].append(country_stats)
        
        logger.info("Country statistics generated", countries_count=len(countries))
        return stats
        
    except Exception as e:
        logger.error("Failed to generate country statistics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate statistics") 