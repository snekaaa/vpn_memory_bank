"""
User Deletion Service
Сервис для полного удаления пользователя из системы
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func
from sqlalchemy.orm import selectinload
import structlog

from models.user import User
from models.vpn_key import VPNKey, VPNKeyStatus
from models.vpn_node import VPNNode
from models.user_server_assignment import UserServerAssignment
from models.server_switch_log import ServerSwitchLog
from models.auto_payment import AutoPayment
from models.payment import Payment
from services.x3ui_client import X3UIClient
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class KeyDeletionResult(BaseModel):
    """Результат удаления VPN ключа"""
    vpn_key_id: int
    node_name: str
    x3ui_success: bool
    error_message: Optional[str] = None
    client_id: Optional[str] = None
    inbound_id: Optional[int] = None


class DeletionResult(BaseModel):
    """Результат удаления пользователя"""
    success: bool
    user_id: int
    user_telegram_id: Optional[int] = None
    username: Optional[str] = None
    vpn_keys_found: int
    vpn_keys_deleted: int
    x3ui_deletions: List[KeyDeletionResult]
    database_cleanup_success: bool
    errors: List[str]
    warnings: List[str]
    deletion_started_at: datetime
    deletion_completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None


class UserDeletionService:
    """Сервис полного удаления пользователя"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = structlog.get_logger(__name__)
    
    async def delete_user_completely(
        self, 
        user_id: int, 
        admin_user: str,
        force_delete: bool = False
    ) -> DeletionResult:
        """
        Полное удаление пользователя из системы
        
        Args:
            user_id: ID пользователя для удаления
            admin_user: Имя администратора, выполняющего удаление
            force_delete: Принудительное удаление игнорируя предупреждения
        
        Returns:
            DeletionResult с детальным отчетом об операции
        """
        deletion_start = datetime.utcnow()
        
        self.logger.info(
            "Starting complete user deletion",
            user_id=user_id,
            admin_user=admin_user,
            force_delete=force_delete
        )
        
        result = DeletionResult(
            success=False,
            user_id=user_id,
            vpn_keys_found=0,
            vpn_keys_deleted=0,
            x3ui_deletions=[],
            database_cleanup_success=False,
            errors=[],
            warnings=[],
            deletion_started_at=deletion_start
        )
        
        try:
            # 1. Получаем пользователя и проверяем его существование
            user = await self._get_user_with_details(user_id)
            if not user:
                result.errors.append(f"Пользователь с ID {user_id} не найден")
                return result
            
            result.user_telegram_id = user.telegram_id
            result.username = user.username
            
            self.logger.info(
                "User found for deletion",
                user_id=user_id,
                telegram_id=user.telegram_id,
                username=user.username
            )
            
            # 2. Получаем все VPN ключи пользователя
            vpn_keys = await self._get_user_vpn_keys(user_id)
            result.vpn_keys_found = len(vpn_keys)
            
            self.logger.info(
                "Found VPN keys for deletion",
                user_id=user_id,
                vpn_keys_count=len(vpn_keys)
            )
            
            # 3. Проверяем блокирующие условия (если не force_delete)
            if not force_delete:
                blocking_issues = await self._check_deletion_blockers(user_id)
                if blocking_issues:
                    result.warnings.extend(blocking_issues)
                    self.logger.warning(
                        "Deletion blockers found",
                        user_id=user_id,
                        blockers=blocking_issues
                    )
            
            # 4. Удаляем VPN ключи из X3UI панелей
            if vpn_keys:
                x3ui_results = await self._delete_vpn_keys_from_x3ui(vpn_keys)
                result.x3ui_deletions = x3ui_results
                result.vpn_keys_deleted = sum(1 for r in x3ui_results if r.x3ui_success)
                
                # Собираем ошибки X3UI
                x3ui_errors = [r.error_message for r in x3ui_results if r.error_message]
                if x3ui_errors:
                    result.warnings.extend([f"X3UI: {err}" for err in x3ui_errors])
            
            # 5. Удаляем данные пользователя из БД (транзакционно)
            try:
                await self._delete_user_data_from_db(user_id)
                result.database_cleanup_success = True
                self.logger.info("Database cleanup completed", user_id=user_id)
                
            except Exception as e:
                result.errors.append(f"Ошибка очистки БД: {str(e)}")
                self.logger.error(
                    "Database cleanup failed",
                    user_id=user_id,
                    error=str(e),
                    exc_info=True
                )
                # При ошибке БД откатываем транзакцию
                await self.db.rollback()
                return result
            
            # 6. Коммитим изменения
            await self.db.commit()
            
            # 7. Финализируем результат
            result.success = True
            result.deletion_completed_at = datetime.utcnow()
            result.total_duration_seconds = (
                result.deletion_completed_at - result.deletion_started_at
            ).total_seconds()
            
            self.logger.info(
                "User deletion completed successfully",
                user_id=user_id,
                telegram_id=user.telegram_id,
                admin_user=admin_user,
                vpn_keys_deleted=result.vpn_keys_deleted,
                duration_seconds=result.total_duration_seconds
            )
            
            return result
            
        except Exception as e:
            await self.db.rollback()
            error_msg = f"Критическая ошибка при удалении пользователя: {str(e)}"
            result.errors.append(error_msg)
            self.logger.error(
                "Critical error during user deletion",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            return result
    
    async def get_user_deletion_preview(self, user_id: int) -> Dict[str, Any]:
        """
        Получить превью удаления пользователя
        
        Returns:
            Словарь с информацией о том, что будет удалено
        """
        try:
            user = await self._get_user_with_details(user_id)
            if not user:
                return {"error": "Пользователь не найден"}
            
            vpn_keys = await self._get_user_vpn_keys(user_id)
            
            # Получаем связанные записи
            server_assignments_count = await self.db.scalar(
                select(func.count(UserServerAssignment.user_id))
                .where(UserServerAssignment.user_id == user.telegram_id)
            )
            
            switch_logs_count = await self.db.scalar(
                select(func.count(ServerSwitchLog.id))
                .where(ServerSwitchLog.user_id == user.telegram_id)
            )
            
            auto_payments_count = await self.db.scalar(
                select(func.count(AutoPayment.id))
                .where(AutoPayment.user_id == user_id)
            )
            
            payments_count = await self.db.scalar(
                select(func.count(Payment.id))
                .where(Payment.user_id == user_id)
            )
            
            # Проверяем блокирующие условия
            blockers = await self._check_deletion_blockers(user_id)
            
            return {
                "user": {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                },
                "deletion_preview": {
                    "vpn_keys": len(vpn_keys),
                    "server_assignments": server_assignments_count or 0,
                    "switch_logs": switch_logs_count or 0,
                    "auto_payments": auto_payments_count or 0,
                    "payments_to_update": payments_count or 0  # не удаляются, обнуляется user_id
                },
                "vpn_keys_details": [
                    {
                        "id": key.id,
                        "key_name": key.key_name,
                        "status": key.status,
                        "node_id": key.node_id,
                        "xui_client_id": key.xui_client_id,
                        "created_at": key.created_at.isoformat() if key.created_at else None
                    }
                    for key in vpn_keys
                ],
                "blockers": blockers,
                "can_delete": len(blockers) == 0
            }
            
        except Exception as e:
            self.logger.error("Error getting deletion preview", user_id=user_id, error=str(e))
            return {"error": f"Ошибка получения превью удаления: {str(e)}"}
    
    async def _get_user_with_details(self, user_id: int) -> Optional[User]:
        """Получить пользователя с деталями"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_vpn_keys(self, user_id: int) -> List[VPNKey]:
        """Получить все VPN ключи пользователя"""
        result = await self.db.execute(
            select(VPNKey)
            .where(VPNKey.user_id == user_id)
            .order_by(VPNKey.created_at.desc())
        )
        return result.scalars().all()
    
    async def _check_deletion_blockers(self, user_id: int) -> List[str]:
        """Проверить условия, блокирующие удаление"""
        blockers = []
        
        try:
            # Проверяем активные платежи в статусе PENDING
            from models.payment import PaymentStatus
            pending_payments_count = await self.db.scalar(
                select(func.count(Payment.id))
                .where(Payment.user_id == user_id)
                .where(Payment.status == PaymentStatus.PENDING)
            )
            
            if pending_payments_count and pending_payments_count > 0:
                blockers.append(f"У пользователя есть {pending_payments_count} активных платежей в обработке")
            
            # Можно добавить другие проверки по необходимости
            
        except Exception as e:
            self.logger.warning("Error checking deletion blockers", user_id=user_id, error=str(e))
        
        return blockers
    
    async def _delete_vpn_keys_from_x3ui(self, vpn_keys: List[VPNKey]) -> List[KeyDeletionResult]:
        """Удалить VPN ключи из X3UI панелей"""
        results = []
        
        # Группируем ключи по нодам для оптимизации
        keys_by_node = {}
        for key in vpn_keys:
            if key.node_id:
                if key.node_id not in keys_by_node:
                    keys_by_node[key.node_id] = []
                keys_by_node[key.node_id].append(key)
        
        # Получаем информацию о нодах
        if keys_by_node:
            nodes_result = await self.db.execute(
                select(VPNNode).where(VPNNode.id.in_(keys_by_node.keys()))
            )
            nodes = {node.id: node for node in nodes_result.scalars().all()}
        else:
            nodes = {}
        
        # Удаляем ключи с каждой ноды
        for node_id, node_keys in keys_by_node.items():
            node = nodes.get(node_id)
            if not node:
                for key in node_keys:
                    results.append(KeyDeletionResult(
                        vpn_key_id=key.id,
                        node_name=f"Unknown Node {node_id}",
                        x3ui_success=False,
                        error_message="Нода не найдена в БД",
                        client_id=key.xui_client_id,
                        inbound_id=key.xui_inbound_id
                    ))
                continue
            
            # Создаем X3UI клиент для ноды
            try:
                x3ui_client = X3UIClient(
                    base_url=node.x3ui_url,
                    username=node.x3ui_username,
                    password=node.x3ui_password
                )
                
                # Удаляем каждый ключ
                for key in node_keys:
                    result = await self._delete_single_key_from_x3ui(x3ui_client, key, node.name)
                    results.append(result)
                    
            except Exception as e:
                # Если не удалось подключиться к ноде
                for key in node_keys:
                    results.append(KeyDeletionResult(
                        vpn_key_id=key.id,
                        node_name=node.name,
                        x3ui_success=False,
                        error_message=f"Ошибка подключения к ноде: {str(e)}",
                        client_id=key.xui_client_id,
                        inbound_id=key.xui_inbound_id
                    ))
        
        # Обрабатываем ключи без ноды
        orphaned_keys = [key for key in vpn_keys if not key.node_id]
        for key in orphaned_keys:
            results.append(KeyDeletionResult(
                vpn_key_id=key.id,
                node_name="Нода не указана",
                x3ui_success=False,
                error_message="У ключа не указана нода",
                client_id=key.xui_client_id,
                inbound_id=key.xui_inbound_id
            ))
        
        return results
    
    async def _delete_single_key_from_x3ui(
        self, 
        x3ui_client: X3UIClient, 
        vpn_key: VPNKey, 
        node_name: str
    ) -> KeyDeletionResult:
        """Удалить один VPN ключ из X3UI панели"""
        try:
            if not vpn_key.xui_client_id or not vpn_key.xui_inbound_id:
                return KeyDeletionResult(
                    vpn_key_id=vpn_key.id,
                    node_name=node_name,
                    x3ui_success=False,
                    error_message="Отсутствует client_id или inbound_id",
                    client_id=vpn_key.xui_client_id,
                    inbound_id=vpn_key.xui_inbound_id
                )
            
            self.logger.info(
                "Deleting VPN key from X3UI",
                vpn_key_id=vpn_key.id,
                node_name=node_name,
                client_id=vpn_key.xui_client_id,
                inbound_id=vpn_key.xui_inbound_id
            )
            
            success = await x3ui_client.delete_client(
                vpn_key.xui_inbound_id, 
                vpn_key.xui_client_id
            )
            
            if success:
                self.logger.info(
                    "VPN key deleted from X3UI successfully",
                    vpn_key_id=vpn_key.id,
                    node_name=node_name
                )
                return KeyDeletionResult(
                    vpn_key_id=vpn_key.id,
                    node_name=node_name,
                    x3ui_success=True,
                    client_id=vpn_key.xui_client_id,
                    inbound_id=vpn_key.xui_inbound_id
                )
            else:
                return KeyDeletionResult(
                    vpn_key_id=vpn_key.id,
                    node_name=node_name,
                    x3ui_success=False,
                    error_message="X3UI API вернул ошибку при удалении",
                    client_id=vpn_key.xui_client_id,
                    inbound_id=vpn_key.xui_inbound_id
                )
                
        except Exception as e:
            self.logger.error(
                "Error deleting VPN key from X3UI",
                vpn_key_id=vpn_key.id,
                node_name=node_name,
                error=str(e),
                exc_info=True
            )
            return KeyDeletionResult(
                vpn_key_id=vpn_key.id,
                node_name=node_name,
                x3ui_success=False,
                error_message=f"Исключение при удалении: {str(e)}",
                client_id=vpn_key.xui_client_id,
                inbound_id=vpn_key.xui_inbound_id
            )
    
    async def _delete_user_data_from_db(self, user_id: int) -> None:
        """Удалить данные пользователя из БД транзакционно"""
        try:
            # Получаем telegram_id пользователя для связанных записей
            user_result = await self.db.execute(
                select(User.telegram_id).where(User.id == user_id)
            )
            user_telegram_id = user_result.scalar_one()
            
            self.logger.info(
                "Starting database cleanup",
                user_id=user_id,
                user_telegram_id=user_telegram_id
            )
            
            # 1. Удаляем VPN ключи пользователя
            await self.db.execute(
                delete(VPNKey).where(VPNKey.user_id == user_id)
            )
            self.logger.info("VPN keys deleted from database", user_id=user_id)
            
            # 2. Удаляем назначения серверов
            await self.db.execute(
                delete(UserServerAssignment).where(UserServerAssignment.user_id == user_telegram_id)
            )
            self.logger.info("Server assignments deleted", user_id=user_id)
            
            # 3. Удаляем логи переключений серверов
            await self.db.execute(
                delete(ServerSwitchLog).where(ServerSwitchLog.user_id == user_telegram_id)
            )
            self.logger.info("Server switch logs deleted", user_id=user_id)
            
            # 4. Удаляем автоплатежи
            await self.db.execute(
                delete(AutoPayment).where(AutoPayment.user_id == user_id)
            )
            self.logger.info("Auto payments deleted", user_id=user_id)
            
            # 5. Обнуляем user_id в платежах (НЕ удаляем платежи)
            await self.db.execute(
                update(Payment)
                .where(Payment.user_id == user_id)
                .values(user_id=None)
            )
            self.logger.info("Payment user_id set to NULL", user_id=user_id)
            
            # 6. Удаляем самого пользователя
            await self.db.execute(
                delete(User).where(User.id == user_id)
            )
            self.logger.info("User deleted from database", user_id=user_id)
            
        except Exception as e:
            self.logger.error(
                "Error during database cleanup",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            raise


# Dependency для получения сервиса
def get_user_deletion_service(db: AsyncSession) -> UserDeletionService:
    """Получить экземпляр сервиса удаления пользователя"""
    return UserDeletionService(db) 