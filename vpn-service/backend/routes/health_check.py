from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config.database import get_db
from models.vpn_node import VPNNode
from services.health_checker import HealthChecker
from typing import List, Dict, Any
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

@router.get("/check-all-nodes")
async def check_all_nodes(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Проверка состояния всех VPN узлов"""
    try:
        # Получаем все узлы из базы данных
        query = select(VPNNode).where(VPNNode.status == 'active')
        result = await db.execute(query)
        nodes = result.scalars().all()
        
        if not nodes:
            return {
                "message": "No active nodes found",
                "checked_at": datetime.utcnow().isoformat(),
                "total_nodes": 0,
                "healthy_nodes": 0,
                "nodes": []
            }
        
        health_checker = HealthChecker()
        healthy_count = 0
        nodes_status = []
        
        for node in nodes:
            logger.info(f"Checking health for node: {node.name}")
            
            # Проверяем здоровье узла
            is_healthy, error_msg, response_time, inbounds_count, active_inbounds_count = await health_checker.check_node_health(node)
            
            if is_healthy:
                healthy_count += 1
            
            nodes_status.append({
                "node_id": node.id,
                "node_name": node.name,
                "node_url": node.x3ui_url,
                "is_healthy": is_healthy,
                "error": error_msg,
                "response_time_ms": response_time,
                "inbounds_count": inbounds_count,
                "active_inbounds_count": active_inbounds_count
            })
            
            # Обновляем статус в базе данных
            node.health_status = 'healthy' if is_healthy else 'unhealthy'
            node.response_time_ms = response_time
            node.last_health_check = datetime.utcnow()
        
        await db.commit()
        
        return {
            "message": "Health check completed",
            "checked_at": datetime.utcnow().isoformat(),
            "total_nodes": len(nodes),
            "healthy_nodes": healthy_count,
            "nodes": nodes_status
        }
        
    except Exception as e:
        logger.error(f"Error during health check: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/nodes")
async def get_nodes_status(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """Получение статуса всех узлов без проверки"""
    try:
        query = select(VPNNode)
        result = await db.execute(query)
        nodes = result.scalars().all()
        
        return [{
            "id": node.id,
            "name": node.name,
            "url": node.x3ui_url,
            "status": node.status,
            "health_status": node.health_status,
            "response_time_ms": node.response_time_ms,
            "last_health_check": node.last_health_check.isoformat() if node.last_health_check else None,
            "current_users": node.current_users,
            "max_users": node.max_users,
            "load_percentage": node.load_percentage
        } for node in nodes]
        
    except Exception as e:
        logger.error(f"Error getting nodes status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get nodes status: {str(e)}") 