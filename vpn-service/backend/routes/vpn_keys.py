from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from config.database import get_db
from models.user import User
from models.vpn_key import VPNKey
from models.vpn_node import VPNNode
from models.user_server_assignment import UserServerAssignment
from services.auth_service import get_current_user
from services.simple_key_update_service import SimpleKeyUpdateService
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/vpn-keys", tags=["vpn-keys"])

@router.get("/")
async def get_user_vpn_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить VPN ключи пользователя"""
    return {
        "user_id": current_user.id,
        "vpn_keys": [],
        "message": "VPN keys functionality not implemented yet"
    }

@router.post("/create")
async def create_vpn_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создать новый VPN ключ"""
    return {
        "user_id": current_user.id,
        "vpn_key": None,
        "message": "VPN key creation not implemented yet"
    }

@router.post("/user/{telegram_id}/create-for-country")
async def create_vpn_key_for_user_country(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Создать VPN ключ для пользователя с учетом назначенной страны"""
    try:
        logger.info("Creating VPN key for user country", telegram_id=telegram_id)
        
        # Получаем пользователя
        user_query = select(User).where(User.telegram_id == telegram_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Получаем назначение пользователя с eager loading
        assignment_query = select(UserServerAssignment).options(
            selectinload(UserServerAssignment.country),
            selectinload(UserServerAssignment.node)
        ).where(
            UserServerAssignment.user_id == telegram_id
        )
        assignment_result = await db.execute(assignment_query)
        assignment = assignment_result.scalar_one_or_none()
        
        if not assignment:
            raise HTTPException(status_code=404, detail="No country assignment found")
        
        # Получаем все активные ноды из назначенной страны
        country_nodes_query = select(VPNNode).where(
            VPNNode.location == assignment.country.name,
            VPNNode.status == "active"
        ).order_by(VPNNode.priority.desc())
        
        country_nodes_result = await db.execute(country_nodes_query)
        country_nodes = country_nodes_result.scalars().all()
        
        logger.info("Found nodes for country", 
                   country=assignment.country.name,
                   node_count=len(country_nodes),
                   node_ids=[node.id for node in country_nodes])
        
        if not country_nodes:
            raise HTTPException(
                status_code=404, 
                detail=f"No active nodes found for country {assignment.country.name}"
            )
        
        # Выбираем лучшую ноду (с наименьшей загрузкой)
        best_node = None
        min_load = float('inf')
        
        for node in country_nodes:
            # Считаем количество активных ключей на ноде
            node_keys_query = select(VPNKey).where(
                VPNKey.node_id == node.id,
                VPNKey.status == "active"
            )
            node_keys_result = await db.execute(node_keys_query)
            key_count = len(node_keys_result.scalars().all())
            
            if key_count < min_load:
                min_load = key_count
                best_node = node
        
        if not best_node:
            raise HTTPException(status_code=404, detail="No suitable node found")
        
        logger.info("Selected best node for country", 
                   telegram_id=telegram_id,
                   country=assignment.country.name,
                   node_id=best_node.id,
                   node_name=best_node.name,
                   current_load=min_load)
        
        # Создаем ключ используя существующий сервис но с принудительным выбором ноды
        # ВРЕМЕННО: Принудительно назначаем пользователя на лучшую ноду
        assignment.node_id = best_node.id
        await db.commit()
        
        logger.info("Forced user assignment to best node", 
                   telegram_id=telegram_id,
                   new_node_id=best_node.id)
        
        # Создаем новый ключ через SimpleKeyUpdateService
        # ОН САМ правильно удалит старые ключи из X3UI и БД
        key_result = await SimpleKeyUpdateService.update_user_key(
            db, user.id, force_new=True
        )
        
        if key_result.get("success"):
            vpn_key_data = key_result.get("vpn_key")
            
            logger.info("Successfully created key for country", 
                       telegram_id=telegram_id,
                       key_id=vpn_key_data.get("id"),
                       country=assignment.country.name)
            
            return {
                "success": True,
                "vpn_key": {
                    "id": vpn_key_data.get("id"),
                    "vless_url": vpn_key_data.get("vless_url"),
                    "node_id": vpn_key_data.get("node_id"),
                    "country": assignment.country.name,
                    "created_at": vpn_key_data.get("created_at")
                },
                "message": f"VPN key created for {assignment.country.name}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create VPN key")
            
    except Exception as e:
        logger.error("Error creating VPN key for country", 
                    telegram_id=telegram_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) 