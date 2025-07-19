"""
VPN Key Lifecycle Service
Управление жизненным циклом VPN ключей: активация, деактивация, реактивация
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from models.vpn_key import VPNKey, VPNKeyStatus
from models.vpn_node import VPNNode
from services.x3ui_client import X3UIClient
from services.x3ui_panel_service import X3UIPanelService

logger = structlog.get_logger(__name__)

class VPNKeyLifecycleService:
    """Сервис управления жизненным циклом VPN ключей"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def deactivate_user_keys(self, user_id: int) -> Dict[str, Any]:
        """
        Деактивировать все ключи пользователя при истечении подписки
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict с результатами деактивации
        """
        try:
            logger.info("🔄 Starting user keys deactivation", user_id=user_id)
            
            # 1. Получаем все активные ключи пользователя
            result = await self.db.execute(
                select(VPNKey)
                .where(
                    VPNKey.user_id == user_id,
                    VPNKey.status.in_(["active", "ACTIVE", VPNKeyStatus.ACTIVE.value])
                )
            )
            active_keys = result.scalars().all()
            
            if not active_keys:
                logger.info("📭 No active keys found for user", user_id=user_id)
                return {
                    "success": True,
                    "message": "No active keys found",
                    "deactivated_count": 0,
                    "total_keys": 0,
                    "errors": []
                }
            
            logger.info("🔍 Found active keys for deactivation", 
                       user_id=user_id,
                       keys_count=len(active_keys))
            
            deactivated_count = 0
            errors = []
            
            # 2. Деактивируем каждый ключ
            for key in active_keys:
                try:
                    logger.info("🔒 Deactivating key", 
                               key_id=key.id,
                               email=key.xui_email,
                               node_id=key.node_id)
                    
                    # Деактивируем в 3xUI панели
                    x3ui_success = await self._disable_key_in_x3ui(key)
                    
                    if x3ui_success:
                        # Обновляем статус в БД на 'suspended'
                        await self._update_key_status(key.id, VPNKeyStatus.SUSPENDED.value)
                        deactivated_count += 1
                        
                        logger.info("✅ Key deactivated successfully", 
                                   key_id=key.id,
                                   email=key.xui_email)
                    else:
                        # Даже если 3xUI не сработал, помечаем как suspended в БД
                        await self._update_key_status(key.id, VPNKeyStatus.SUSPENDED.value)
                        deactivated_count += 1
                        errors.append(f"Key {key.id}: 3xUI deactivation failed, but marked as suspended")
                        
                        logger.warning("⚠️ Key marked as suspended despite 3xUI failure", 
                                     key_id=key.id,
                                     email=key.xui_email)
                        
                except Exception as e:
                    error_msg = f"Key {key.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error("💥 Error deactivating key", 
                               key_id=key.id,
                               error=str(e))
            
            # 3. Коммитим изменения
            await self.db.commit()
            
            result = {
                "success": True,
                "message": f"Deactivated {deactivated_count} out of {len(active_keys)} keys",
                "deactivated_count": deactivated_count,
                "total_keys": len(active_keys),
                "errors": errors
            }
            
            logger.info("🔒 User keys deactivation completed", 
                       user_id=user_id,
                       result=result)
            
            return result
            
        except Exception as e:
            await self.db.rollback()
            logger.error("💥 Critical error during keys deactivation", 
                        user_id=user_id,
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "deactivated_count": 0,
                "total_keys": 0
            }
    
    async def reactivate_user_keys(self, user_id: int) -> Dict[str, Any]:
        """
        Реактивировать ключи пользователя при возобновлении подписки
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict с результатами реактивации
        """
        try:
            logger.info("🔄 Starting user keys reactivation", user_id=user_id)
            
            # 1. Получаем все приостановленные ключи пользователя
            result = await self.db.execute(
                select(VPNKey)
                .where(
                    VPNKey.user_id == user_id,
                    VPNKey.status.in_(["suspended", "SUSPENDED", VPNKeyStatus.SUSPENDED.value])
                )
            )
            suspended_keys = result.scalars().all()
            
            if not suspended_keys:
                logger.info("📭 No suspended keys found for user", user_id=user_id)
                return {
                    "success": True,
                    "message": "No suspended keys found",
                    "reactivated_count": 0,
                    "total_keys": 0,
                    "errors": []
                }
            
            logger.info("🔍 Found suspended keys for reactivation", 
                       user_id=user_id,
                       keys_count=len(suspended_keys))
            
            reactivated_count = 0
            errors = []
            
            # 2. Реактивируем каждый ключ
            for key in suspended_keys:
                try:
                    logger.info("🔓 Reactivating key", 
                               key_id=key.id,
                               email=key.xui_email,
                               node_id=key.node_id)
                    
                    # Реактивируем в 3xUI панели
                    x3ui_success = await self._enable_key_in_x3ui(key)
                    
                    if x3ui_success:
                        # Обновляем статус в БД на 'active'
                        await self._update_key_status(key.id, VPNKeyStatus.ACTIVE.value)
                        reactivated_count += 1
                        
                        logger.info("✅ Key reactivated successfully", 
                                   key_id=key.id,
                                   email=key.xui_email)
                    else:
                        # Если 3xUI не сработал, оставляем suspended
                        errors.append(f"Key {key.id}: 3xUI reactivation failed")
                        
                        logger.warning("⚠️ Key reactivation failed in 3xUI", 
                                     key_id=key.id,
                                     email=key.xui_email)
                        
                except Exception as e:
                    error_msg = f"Key {key.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error("💥 Error reactivating key", 
                               key_id=key.id,
                               error=str(e))
            
            # 3. Коммитим изменения
            await self.db.commit()
            
            result = {
                "success": True,
                "message": f"Reactivated {reactivated_count} out of {len(suspended_keys)} keys",
                "reactivated_count": reactivated_count,
                "total_keys": len(suspended_keys),
                "errors": errors
            }
            
            logger.info("🔓 User keys reactivation completed", 
                       user_id=user_id,
                       result=result)
            
            return result
            
        except Exception as e:
            await self.db.rollback()
            logger.error("💥 Critical error during keys reactivation", 
                        user_id=user_id,
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "reactivated_count": 0,
                "total_keys": 0
            }
    
    async def get_user_keys_status(self, user_id: int) -> Dict[str, Any]:
        """Получить статус всех ключей пользователя"""
        try:
            result = await self.db.execute(
                select(VPNKey)
                .where(VPNKey.user_id == user_id)
            )
            keys = result.scalars().all()
            
            status_counts = {
                "active": 0,
                "suspended": 0,
                "expired": 0,
                "revoked": 0,
                "total": len(keys)
            }
            
            keys_details = []
            
            for key in keys:
                status = key.status.lower() if key.status else "unknown"
                
                if status in ["active"]:
                    status_counts["active"] += 1
                elif status in ["suspended"]:
                    status_counts["suspended"] += 1
                elif status in ["expired"]:
                    status_counts["expired"] += 1
                elif status in ["revoked"]:
                    status_counts["revoked"] += 1
                
                keys_details.append({
                    "id": key.id,
                    "email": key.xui_email,
                    "status": key.status,
                    "node_id": key.node_id,
                    "created_at": key.created_at.isoformat() if key.created_at else None
                })
            
            return {
                "success": True,
                "user_id": user_id,
                "status_counts": status_counts,
                "keys": keys_details
            }
            
        except Exception as e:
            logger.error("Error getting user keys status", 
                        user_id=user_id,
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id
            }
    
    async def _disable_key_in_x3ui(self, key: VPNKey) -> bool:
        """Деактивировать ключ в 3xUI панели"""
        try:
            if not key.node_id:
                logger.warning("No node assigned to key", key_id=key.id)
                return False
            
            # Получаем информацию о ноде
            node_result = await self.db.execute(
                select(VPNNode).where(VPNNode.id == key.node_id)
            )
            node = node_result.scalar_one_or_none()
            
            if not node:
                logger.warning("Node not found", key_id=key.id, node_id=key.node_id)
                return False
            
            # Создаем клиент для ноды
            x3ui_client = X3UIClient(
                base_url=node.x3ui_url,
                username=node.x3ui_username,
                password=node.x3ui_password
            )
            
            # Деактивируем клиента по email
            success = await x3ui_client.disable_client_by_email(key.xui_email)
            
            if success:
                logger.info("✅ Key disabled in 3xUI successfully", 
                           key_id=key.id,
                           email=key.xui_email,
                           node=node.name)
            else:
                logger.warning("⚠️ Failed to disable key in 3xUI", 
                             key_id=key.id,
                             email=key.xui_email,
                             node=node.name)
            
            return success
            
        except Exception as e:
            logger.error("💥 Error disabling key in 3xUI", 
                        key_id=key.id,
                        error=str(e))
            return False
    
    async def _enable_key_in_x3ui(self, key: VPNKey) -> bool:
        """Реактивировать ключ в 3xUI панели"""
        try:
            if not key.node_id:
                logger.warning("No node assigned to key", key_id=key.id)
                return False
            
            # Получаем информацию о ноде
            node_result = await self.db.execute(
                select(VPNNode).where(VPNNode.id == key.node_id)
            )
            node = node_result.scalar_one_or_none()
            
            if not node:
                logger.warning("Node not found", key_id=key.id, node_id=key.node_id)
                return False
            
            # Создаем клиент для ноды
            x3ui_client = X3UIClient(
                base_url=node.x3ui_url,
                username=node.x3ui_username,
                password=node.x3ui_password
            )
            
            # Реактивируем клиента по email
            success = await x3ui_client.enable_client_by_email(key.xui_email)
            
            if success:
                logger.info("✅ Key enabled in 3xUI successfully", 
                           key_id=key.id,
                           email=key.xui_email,
                           node=node.name)
            else:
                logger.warning("⚠️ Failed to enable key in 3xUI", 
                             key_id=key.id,
                             email=key.xui_email,
                             node=node.name)
            
            return success
            
        except Exception as e:
            logger.error("💥 Error enabling key in 3xUI", 
                        key_id=key.id,
                        error=str(e))
            return False
    
    async def _update_key_status(self, key_id: int, new_status: str) -> bool:
        """Обновить статус ключа в БД"""
        try:
            await self.db.execute(
                update(VPNKey)
                .where(VPNKey.id == key_id)
                .values(
                    status=new_status,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            
            logger.debug("📝 Key status updated in database", 
                        key_id=key_id,
                        new_status=new_status)
            
            return True
            
        except Exception as e:
            logger.error("💥 Error updating key status in database", 
                        key_id=key_id,
                        new_status=new_status,
                        error=str(e))
            return False

# Функция-хелпер для использования в других частях системы
async def deactivate_user_vpn_keys(db_session: AsyncSession, user_id: int) -> Dict[str, Any]:
    """
    Быстрая деактивация VPN ключей пользователя (функция-хелпер)
    
    Args:
        db_session: Сессия базы данных
        user_id: ID пользователя
        
    Returns:
        Dict с результатом деактивации
    """
    service = VPNKeyLifecycleService(db_session)
    return await service.deactivate_user_keys(user_id)

async def reactivate_user_vpn_keys(db_session: AsyncSession, user_id: int) -> Dict[str, Any]:
    """
    Быстрая реактивация VPN ключей пользователя (функция-хелпер)
    
    Args:
        db_session: Сессия базы данных
        user_id: ID пользователя
        
    Returns:
        Dict с результатом реактивации
    """
    service = VPNKeyLifecycleService(db_session)
    return await service.reactivate_user_keys(user_id) 