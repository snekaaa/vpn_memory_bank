"""
HealthChecker Service - Мониторинг здоровья VPN нод
"""

import structlog
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import joinedload
import json

from models.vpn_node import VPNNode
from models.user_node_assignment import UserNodeAssignment
from services.x3ui_client import X3UIClient
from services.x3ui_client_pool import X3UIClientPool
from services.load_balancer import LoadBalancer
from config.database import get_db

logger = structlog.get_logger(__name__)

class HealthStatus:
    """Статус здоровья ноды"""
    def __init__(self, node_id: int, is_healthy: bool, response_time_ms: Optional[int] = None,
                 error_message: Optional[str] = None):
        self.node_id = node_id
        self.is_healthy = is_healthy
        self.response_time_ms = response_time_ms
        self.error_message = error_message
        self.checked_at = datetime.utcnow()

class HealthChecker:
    """Мониторинг здоровья серверных нод"""
    
    def __init__(self, db_session: AsyncSession = None):
        self.db = db_session
        self.client_pool = X3UIClientPool(db_session)
        self.load_balancer = LoadBalancer(db_session)
        self.check_interval = timedelta(minutes=5)  # Проверка каждые 5 минут
    
    async def check_node_health_by_id(self, node_id: int) -> HealthStatus:
        """Проверка состояния конкретной ноды"""
        try:
            # Получаем ноду
            result = await self.db.execute(
                select(VPNNode).where(VPNNode.id == node_id)
            )
            node = result.scalar_one_or_none()
            
            if not node:
                logger.error("Node not found for health check", node_id=node_id)
                return HealthStatus(node_id, False, error_message="Node not found")
            
            start_time = datetime.utcnow()
            
            # Создаем временный клиент для проверки
            client = X3UIClient()
            client.base_url = node.x3ui_url
            client.username = node.x3ui_username
            client.password = node.x3ui_password
            
            # Проверяем соединение
            login_success = await client._login()
            
            # Если успешно - проверяем доступность inbounds
            is_healthy = False
            if login_success:
                inbounds = await client.get_inbounds()
                is_healthy = inbounds is not None
            
            end_time = datetime.utcnow()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Обновляем статус ноды в БД
            health_status = 'healthy' if is_healthy else 'unhealthy'
            node.health_status = health_status
            node.last_health_check = datetime.utcnow()
            node.response_time_ms = response_time
            
            await self.db.commit()
            
            logger.info("Node health check completed", 
                       node_id=node_id, 
                       is_healthy=is_healthy,
                       response_time=response_time)
            
            return HealthStatus(
                node_id=node_id,
                is_healthy=is_healthy,
                response_time_ms=response_time,
                error_message=None if is_healthy else "Connection failed"
            )
            
        except Exception as e:
            logger.error("Error checking node health", 
                        node_id=node_id, 
                        error=str(e))
            
            # Обновляем статус ноды в БД
            try:
                result = await self.db.execute(
                    select(VPNNode).where(VPNNode.id == node_id)
                )
                node = result.scalar_one_or_none()
                
                if node:
                    node.health_status = 'unhealthy'
                    node.last_health_check = datetime.utcnow()
                    await self.db.commit()
            except:
                pass
            
            return HealthStatus(
                node_id=node_id,
                is_healthy=False,
                error_message=str(e)
            )
    
    async def check_node_health(self, node: VPNNode) -> tuple[bool, Optional[str], Optional[int], int, int]:
        """Проверка состояния ноды - возвращает (is_healthy, error_msg, response_time, inbounds_count, active_inbounds_count)"""
        try:
            start_time = datetime.utcnow()
            
            # Создаем клиент с параметрами ноды
            client = X3UIClient(
                base_url=node.x3ui_url,
                username=node.x3ui_username,
                password=node.x3ui_password
            )
            
            # Проверяем авторизацию
            login_success = await client._login()
            
            if not login_success:
                end_time = datetime.utcnow()
                response_time = int((end_time - start_time).total_seconds() * 1000)
                return False, "Authentication failed", response_time, 0, 0
            
            # Получаем inbounds
            inbounds = await client.get_inbounds()
            
            if inbounds is None:
                end_time = datetime.utcnow()
                response_time = int((end_time - start_time).total_seconds() * 1000)
                return False, "Failed to get inbounds", response_time, 0, 0
            
            # Подсчитываем активные inbounds
            active_count = sum(1 for inbound in inbounds if inbound.get('enable', False))
            
            end_time = datetime.utcnow()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Нода здорова, если есть хотя бы один активный inbound
            is_healthy = active_count > 0
            error_msg = None if is_healthy else "No active inbounds"
            
            logger.info("Node health check completed", 
                       node_name=node.name,
                       is_healthy=is_healthy,
                       response_time=response_time,
                       inbounds_total=len(inbounds),
                       inbounds_active=active_count)
            
            return is_healthy, error_msg, response_time, len(inbounds), active_count
            
        except Exception as e:
            logger.error("Error checking node health", 
                        node_name=node.name, 
                        error=str(e))
            
            return False, f"Connection error: {str(e)}", None, 0, 0
    
    async def check_all_nodes(self) -> Dict[int, HealthStatus]:
        """Проверка всех нод"""
        try:
            # Получаем все ноды
            result = await self.db.execute(select(VPNNode))
            nodes = result.scalars().all()
            
            # Проверяем каждую ноду
            health_statuses = {}
            for node in nodes:
                status = await self.check_node_health_by_id(node.id)
                health_statuses[node.id] = status
            
            return health_statuses
            
        except Exception as e:
            logger.error("Error checking all nodes", error=str(e))
            return {}
    
    async def handle_unhealthy_node(self, node_id: int) -> bool:
        """Обработка недоступной ноды"""
        try:
            # Получаем ноду
            result = await self.db.execute(
                select(VPNNode).where(VPNNode.id == node_id)
            )
            node = result.scalar_one_or_none()
            
            if not node:
                logger.error("Node not found for handling", node_id=node_id)
                return False
            
            # Если нода уже помечена как неактивная - ничего не делаем
            if node.status != 'active':
                logger.info("Node already inactive, skipping handling", node_id=node_id)
                return True
            
            # Помечаем ноду как неактивную
            node.status = 'inactive'
            node.health_status = 'unhealthy'
            await self.db.commit()
            
            # Получаем пользователей на этой ноде
            users_result = await self.db.execute(
                select(User)
                .join(UserNodeAssignment)
                .where(UserNodeAssignment.node_id == node_id)
                .where(UserNodeAssignment.is_active == True)
            )
            users = users_result.scalars().all()
            
            # Мигрируем пользователей на другие ноды
            migrated_count = 0
            failed_count = 0
            
            for user in users:
                # Выбираем оптимальную ноду для миграции
                optimal_node = await self.load_balancer.select_optimal_node()
                
                if not optimal_node:
                    logger.error("No healthy nodes available for migration")
                    break
                
                # Мигрируем пользователя
                success = await self.load_balancer.migrate_user(user.id, optimal_node.id)
                
                if success:
                    migrated_count += 1
                else:
                    failed_count += 1
            
            logger.info("Unhealthy node handled", 
                       node_id=node_id, 
                       migrated_users=migrated_count,
                       failed_migrations=failed_count)
            
            return True
            
        except Exception as e:
            logger.error("Error handling unhealthy node", 
                        node_id=node_id, 
                        error=str(e))
            return False
    
    async def start_monitoring(self, check_interval_seconds: int = 300):
        """Запуск фонового мониторинга нод"""
        logger.info("Starting node health monitoring", 
                   interval_seconds=check_interval_seconds)
        
        while True:
            try:
                # Проверяем все ноды
                health_statuses = await self.check_all_nodes()
                
                # Обрабатываем недоступные ноды
                for node_id, status in health_statuses.items():
                    if not status.is_healthy:
                        await self.handle_unhealthy_node(node_id)
                
                # Обновляем кэш клиентов
                await self.client_pool.clear_cache()
                
            except Exception as e:
                logger.error("Error in monitoring cycle", error=str(e))
            
            # Ждем до следующей проверки
            await asyncio.sleep(check_interval_seconds)
    
    async def get_health_report(self) -> Dict[str, Any]:
        """Получение отчета о состоянии системы"""
        try:
            # Получаем статистику по нодам
            nodes_result = await self.db.execute(
                select(VPNNode)
                .order_by(VPNNode.priority.desc())
            )
            nodes = nodes_result.scalars().all()
            
            # Считаем статистику
            total_nodes = len(nodes)
            active_nodes = sum(1 for n in nodes if n.status == 'active')
            healthy_nodes = sum(1 for n in nodes if n.health_status == 'healthy')
            total_capacity = sum(n.max_users for n in nodes)
            total_users = sum(n.current_users for n in nodes)
            
            # Формируем отчет
            report = {
                "total_nodes": total_nodes,
                "active_nodes": active_nodes,
                "healthy_nodes": healthy_nodes,
                "inactive_nodes": total_nodes - active_nodes,
                "unhealthy_nodes": total_nodes - healthy_nodes,
                "total_capacity": total_capacity,
                "total_users": total_users,
                "system_load_percentage": (total_users / total_capacity * 100) if total_capacity > 0 else 0,
                "generated_at": datetime.utcnow().isoformat(),
                "nodes": []
            }
            
            # Добавляем детали по каждой ноде
            for node in nodes:
                report["nodes"].append({
                    "id": node.id,
                    "name": node.name,
                    "location": node.location,
                    "status": node.status,
                    "health_status": node.health_status,
                    "current_users": node.current_users,
                    "max_users": node.max_users,
                    "load_percentage": node.load_percentage,
                    "last_health_check": node.last_health_check.isoformat() if node.last_health_check else None,
                    "response_time_ms": node.response_time_ms
                })
            
            return report
            
        except Exception as e:
            logger.error("Error generating health report", error=str(e))
            return {
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }
    
    async def get_node_stats(self, node_id: int) -> Dict[str, Any]:
        """Получение детальной статистики по конкретной ноде"""
        try:
            # Получаем ноду
            result = await self.db.execute(
                select(VPNNode)
                .where(VPNNode.id == node_id)
            )
            node = result.scalar_one_or_none()
            
            if not node:
                logger.error("Node not found for stats", node_id=node_id)
                return {"error": "Node not found"}
            
            # Получаем дополнительную статистику через X3UI
            client = X3UIClient()
            client.base_url = node.x3ui_url
            client.username = node.x3ui_username
            client.password = node.x3ui_password
            
            x3ui_stats = {
                "connected": False,
                "inbounds": 0,
                "total_clients": 0,
                "active_clients": 0,
                "server_status": {}
            }
            
            # Пробуем подключиться
            if await client._login():
                x3ui_stats["connected"] = True
                
                # Получаем inbounds
                inbounds = await client.get_inbounds()
                if inbounds:
                    x3ui_stats["inbounds"] = len(inbounds)
                    
                    # Считаем клиентов
                    total_clients = 0
                    active_clients = 0
                    for inbound in inbounds:
                        settings = json.loads(inbound.get('settings', '{}'))
                        clients = settings.get('clients', [])
                        total_clients += len(clients)
                        active_clients += sum(1 for c in clients if c.get('enable', True))
                    
                    x3ui_stats["total_clients"] = total_clients
                    x3ui_stats["active_clients"] = active_clients
                
                # Получаем статус сервера
                server_status = await client.get_server_status()
                if server_status:
                    x3ui_stats["server_status"] = server_status
            
            # Формируем статистику
            stats = {
                "node_info": {
                    "id": node.id,
                    "name": node.name,
                    "location": node.location,
                    "description": node.description,
                    "status": node.status,
                    "health_status": node.health_status,
                    "created_at": node.created_at.isoformat() if node.created_at else None,
                    "updated_at": node.updated_at.isoformat() if node.updated_at else None
                },
                "load_stats": {
                    "current_users": node.current_users,
                    "max_users": node.max_users,
                    "load_percentage": node.load_percentage,
                    "priority": node.priority,
                    "weight": node.weight
                },
                "health_stats": {
                    "last_check": node.last_health_check.isoformat() if node.last_health_check else None,
                    "response_time_ms": node.response_time_ms,
                    "is_healthy": node.health_status == "healthy"
                },
                "x3ui_stats": x3ui_stats,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error("Error getting node stats", node_id=node_id, error=str(e))
            return {
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            } 