"""
NodeManager Service - Управление серверными нодами VPN
"""

import structlog
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import joinedload

from models.vpn_node import VPNNode, NodeMode
from models.user_node_assignment import UserNodeAssignment
from models.user import User
from services.x3ui_client import X3UIClient
from config.database import get_db
from models.vpn_key import VPNKey, VPNKeyStatus

logger = structlog.get_logger(__name__)

class NodeConfig:
    """Конфигурация ноды для создания/обновления"""
    def __init__(self, name: str, x3ui_url: str, x3ui_username: str, x3ui_password: str,
                 description: str = "", location: str = "", max_users: int = 1000,
                 priority: int = 100, weight: float = 1.0,
                 mode: NodeMode = NodeMode.default, reality_config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.x3ui_url = x3ui_url
        self.x3ui_username = x3ui_username
        self.x3ui_password = x3ui_password
        self.description = description
        self.location = location
        self.max_users = max_users
        self.priority = priority
        self.weight = weight
        self.mode = mode
        self.reality_config = reality_config

class NodeManager:
    """Управление серверными нодами VPN"""
    
    def __init__(self, db_session: AsyncSession = None):
        self.db = db_session
    
    async def create_node(self, node_config: NodeConfig, **additional_params) -> Optional[VPNNode]:
        """Создание новой ноды"""
        try:
            logger.info("Starting node creation", 
                       name=node_config.name, 
                       url=node_config.x3ui_url,
                       additional_params=list(additional_params.keys()))
            
            # Проверяем подключение к БД
            if not self.db:
                logger.error("Database session is None")
                return None
            
            # Сначала проверяем подключение к X3UI
            logger.info("Testing X3UI connection...")
            connection_result = await self._test_x3ui_connection(node_config)
            logger.info("X3UI connection test result", 
                       success=connection_result, 
                       url=node_config.x3ui_url)
            
            if not connection_result:
                logger.error("Failed to connect to X3UI", url=node_config.x3ui_url)
                return None
            
            logger.info("X3UI connection successful, proceeding to create node in DB")
            
            # Создаем новую ноду с базовыми параметрами
            node_data = {
                'name': node_config.name,
                'description': node_config.description,
                'location': node_config.location,
                'x3ui_url': node_config.x3ui_url,
                'x3ui_username': node_config.x3ui_username,
                'x3ui_password': node_config.x3ui_password,
                'max_users': node_config.max_users,
                'priority': node_config.priority,
                'weight': node_config.weight,
                'status': 'active',
                'health_status': 'unknown',
                'mode': node_config.mode,
                'reality_config': node_config.reality_config,
            }
            
            # Добавляем дополнительные параметры (для обратной совместимости или других случаев)
            node_data.update(additional_params)
            
            logger.info("Creating VPNNode object with data", node_data_keys=list(node_data.keys()))
            
            # Фильтруем None значения, чтобы не перезаписывать default значения в модели
            new_node = VPNNode(**{k: v for k, v in node_data.items() if v is not None})
            
            logger.info("Adding node to database session")
            self.db.add(new_node)
            
            logger.info("Committing to database")
            await self.db.commit()
            
            logger.info("Refreshing node from database")
            await self.db.refresh(new_node)
            
            # Проверка здоровья будет выполнена позже
            # await self._check_node_health(new_node.id)
            
            logger.info("VPN node created successfully", 
                       node_id=new_node.id, 
                       name=new_node.name,
                       location=new_node.location,
                       additional_params=list(additional_params.keys()))
            
            return new_node
            
        except Exception as e:
            logger.error("Error creating VPN node", 
                        name=node_config.name, 
                        error=str(e),
                        exc_info=True)
            if self.db:
                await self.db.rollback()
            return None
    
    async def update_node(self, node_id: int, updates: Dict[str, Any]) -> Optional[VPNNode]:
        """Обновление конфигурации ноды"""
        try:
            # Получаем ноду
            result = await self.db.execute(select(VPNNode).where(VPNNode.id == node_id))
            node = result.scalar_one_or_none()
            
            if not node:
                logger.error("Node not found for update", node_id=node_id)
                return None
            
            # Применяем обновления
            for key, value in updates.items():
                if hasattr(node, key):
                    setattr(node, key, value)
            
            node.updated_at = datetime.utcnow()
            
            # Если изменились X3UI настройки - проверяем соединение
            if any(key in updates for key in ['x3ui_url', 'x3ui_username', 'x3ui_password']):
                config = NodeConfig(
                    name=node.name,
                    x3ui_url=node.x3ui_url,
                    x3ui_username=node.x3ui_username,
                    x3ui_password=node.x3ui_password
                )
                if not await self._test_x3ui_connection(config):
                    logger.warning("Updated X3UI connection failed", node_id=node_id)
                    node.health_status = 'unhealthy'
            
            await self.db.commit()
            await self.db.refresh(node)
            
            logger.info("VPN node updated successfully", 
                       node_id=node.id, 
                       updates=list(updates.keys()))
            
            return node
            
        except Exception as e:
            logger.error("Error updating VPN node", 
                        node_id=node_id, 
                        error=str(e))
            await self.db.rollback()
            return None
    
    async def delete_node(self, node_id: int, migrate_users: bool = True) -> bool:
        """Удаление ноды (с опциональной миграцией пользователей)"""
        try:
            # Получаем ноду
            result = await self.db.execute(select(VPNNode).where(VPNNode.id == node_id))
            node = result.scalar_one_or_none()
            
            if not node:
                logger.error("Node not found for deletion", node_id=node_id)
                return False
            
            # Если нужно мигрировать пользователей
            if migrate_users:
                success = await self._migrate_users_from_node(node_id)
                if not success:
                    logger.warning("Failed to migrate some users from node", node_id=node_id)
            
            # Деактивируем все assignments
            await self.db.execute(
                update(UserNodeAssignment)
                .where(UserNodeAssignment.node_id == node_id)
                .values(is_active=False)
            )
            
            # Удаляем ноду
            await self.db.execute(delete(VPNNode).where(VPNNode.id == node_id))
            await self.db.commit()
            
            logger.info("VPN node deleted successfully", 
                       node_id=node_id, 
                       name=node.name,
                       migrated_users=migrate_users)
            
            return True
            
        except Exception as e:
            logger.error("Error deleting VPN node", 
                        node_id=node_id, 
                        error=str(e))
            await self.db.rollback()
            return False
    
    async def get_nodes(self, status: str = None, include_assignments: bool = False) -> List[VPNNode]:
        """Получение списка нод с опциональной фильтрацией"""
        try:
            query = select(VPNNode)
            
            # Опция include_assignments убрана - relationships закомментированы в модели
            # if include_assignments:
            #     query = query.options(joinedload(VPNNode.user_assignments))
            
            if status:
                query = query.where(VPNNode.status == status)
            
            query = query.order_by(VPNNode.priority.desc(), VPNNode.created_at)
            
            result = await self.db.execute(query)
            if include_assignments:
                return result.unique().scalars().all()
            else:
                return result.scalars().all()
            
        except Exception as e:
            logger.error("Error getting VPN nodes", status=status, error=str(e))
            return []
    
    async def get_node_by_id(self, node_id: int) -> Optional[VPNNode]:
        """Получение ноды по ID"""
        try:
            result = await self.db.execute(
                select(VPNNode)
                .where(VPNNode.id == node_id)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Error getting VPN node by ID", node_id=node_id, error=str(e))
            return None
    
    async def test_node_connection(self, node_id: int) -> bool:
        """Тестирование подключения к ноде"""
        try:
            node = await self.get_node_by_id(node_id)
            if not node:
                return False
            
            config = NodeConfig(
                name=node.name,
                x3ui_url=node.x3ui_url,
                x3ui_username=node.x3ui_username,
                x3ui_password=node.x3ui_password
            )
            
            return await self._test_x3ui_connection(config)
            
        except Exception as e:
            logger.error("Error testing node connection", node_id=node_id, error=str(e))
            return False
    
    async def update_node_stats(self, node_id: int) -> bool:
        """Обновление статистики ноды (количество активных VPN ключей)"""
        try:
            # Подсчитываем активные VPN ключи для данной ноды
            result = await self.db.execute(
                select(func.count(VPNKey.id))
                .where(VPNKey.node_id == node_id)
                .where(VPNKey.status.in_(["active", "ACTIVE", VPNKeyStatus.ACTIVE.value]))
            )
            current_users = result.scalar() or 0
            
            # Обновляем ноду
            await self.db.execute(
                update(VPNNode)
                .where(VPNNode.id == node_id)
                .values(current_users=current_users, updated_at=datetime.utcnow())
            )
            await self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error("Error updating node stats", node_id=node_id, error=str(e))
            return False
    
    async def _test_x3ui_connection(self, config: NodeConfig) -> bool:
        """Тестирование соединения с X3UI панелью"""
        try:
            # Логгируем для отладки
            logger.info("Testing X3UI connection", 
                       url=config.x3ui_url, 
                       username=config.x3ui_username)
                       
            # Проверяем формат URL
            if not config.x3ui_url.startswith("http://") and not config.x3ui_url.startswith("https://"):
                logger.error("Invalid X3UI URL format, must start with http:// or https://", 
                          url=config.x3ui_url)
                return False
                
            # Удаляем trailing slash если есть
            clean_url = config.x3ui_url.rstrip('/')
            
            logger.info("Creating X3UI client for connection test", 
                       clean_url=clean_url, 
                       username=config.x3ui_username)
            
            # Создаем временный клиент для тестирования с правильными параметрами
            client = X3UIClient(
                base_url=clean_url,
                username=config.x3ui_username,
                password=config.x3ui_password
            )
            
            # Пробуем подключиться
            logger.info("Attempting X3UI login...")
            login_success = await client._login()
            logger.info("X3UI login result", success=login_success)
            
            if login_success:
                # Для новых панелей достаточно успешного логина
                # Inbounds могут быть созданы позже
                logger.info("X3UI connection test successful - login OK")
                
                # Опционально пробуем получить inbounds, но не требуем их наличия
                try:
                    logger.info("Attempting to get inbounds list (optional)...")
                    inbounds = await client.get_inbounds()
                    if inbounds is not None:
                        logger.info("X3UI inbounds found", count=len(inbounds))
                    else:
                        logger.info("X3UI inbounds empty or not available - OK for new panel")
                except Exception as e:
                    logger.warning("Could not get inbounds, but login was successful", error=str(e))
                
                return True
            
            logger.warning("X3UI login failed for", url=clean_url)
            return False
            
        except Exception as e:
            logger.error("X3UI connection test failed", 
                        url=config.x3ui_url, 
                        error=str(e),
                        exc_info=True)
            return False
    
    async def _check_node_health(self, node_id: int) -> bool:
        """Проверка здоровья конкретной ноды"""
        try:
            start_time = datetime.utcnow()
            
            # Тестируем соединение
            connection_ok = await self.test_node_connection(node_id)
            
            end_time = datetime.utcnow()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Обновляем статус
            health_status = 'healthy' if connection_ok else 'unhealthy'
            
            await self.db.execute(
                update(VPNNode)
                .where(VPNNode.id == node_id)
                .values(
                    health_status=health_status,
                    last_health_check=datetime.utcnow(),
                    response_time_ms=response_time
                )
            )
            await self.db.commit()
            
            return connection_ok
            
        except Exception as e:
            logger.error("Error checking node health", node_id=node_id, error=str(e))
            return False
    
    async def _migrate_users_from_node(self, node_id: int) -> bool:
        """Миграция пользователей с удаляемой ноды на другие здоровые ноды"""
        try:
            # Получаем пользователей на этой ноде
            result = await self.db.execute(
                select(UserNodeAssignment)
                .where(UserNodeAssignment.node_id == node_id)
                .where(UserNodeAssignment.is_active == True)
            )
            assignments = result.scalars().all()
            
            if not assignments:
                return True  # Нет пользователей для миграции
            
            # Получаем здоровые ноды для миграции
            healthy_nodes = await self.get_nodes(status='active')
            healthy_nodes = [n for n in healthy_nodes if n.id != node_id and n.can_accept_users]
            
            if not healthy_nodes:
                logger.error("No healthy nodes available for migration", node_id=node_id)
                return False
            
            # Мигрируем пользователей
            migrated_count = 0
            for assignment in assignments:
                # Выбираем ноду с наименьшей нагрузкой
                target_node = min(healthy_nodes, key=lambda n: n.calculate_score())
                
                # Создаем новый assignment
                new_assignment = UserNodeAssignment(
                    user_id=assignment.user_id,
                    node_id=target_node.id,
                    is_active=True
                )
                self.db.add(new_assignment)
                
                # Деактивируем старый assignment
                assignment.is_active = False
                
                # Обновляем счетчики
                target_node.current_users += 1
                migrated_count += 1
            
            await self.db.commit()
            
            logger.info("Users migrated successfully", 
                       from_node=node_id, 
                       migrated_count=migrated_count)
            
            return True
            
        except Exception as e:
            logger.error("Error migrating users from node", 
                        node_id=node_id, 
                        error=str(e))
            await self.db.rollback()
            return False 