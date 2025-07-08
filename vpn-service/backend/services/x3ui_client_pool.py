"""
X3UI Client Pool - Пул соединений к множественным X3UI панелям
"""

import structlog
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.x3ui_client import X3UIClient
from models.vpn_node import VPNNode
from config.database import get_db

logger = structlog.get_logger(__name__)

class X3UIClientPool:
    """Пул клиентов для множественных X3UI панелей"""
    
    def __init__(self, db_session: AsyncSession = None):
        self.db = db_session
        self.clients: Dict[int, X3UIClient] = {}
        self.last_refresh: Dict[int, datetime] = {}
        self.refresh_interval = timedelta(minutes=30)  # Обновлять соединения каждые 30 минут
    
    async def get_client(self, node_id: int) -> Optional[X3UIClient]:
        """Получить X3UI клиент для конкретной ноды"""
        try:
            # Проверяем есть ли клиент в кэше и не устарел ли он
            current_time = datetime.utcnow()
            cached_client = self.clients.get(node_id)
            last_refresh = self.last_refresh.get(node_id)
            
            if (cached_client and last_refresh and 
                current_time - last_refresh < self.refresh_interval):
                return cached_client
            
            # Если клиента нет или он устарел - создаем новый
            return await self.refresh_client(node_id)
            
        except Exception as e:
            logger.error("Error getting X3UI client", 
                        node_id=node_id, 
                        error=str(e))
            return None
    
    async def refresh_client(self, node_id: int) -> Optional[X3UIClient]:
        """Обновить или создать новый клиент для ноды"""
        try:
            # Получаем данные ноды из БД
            if not self.db:
                self.db = next(get_db())
                
            result = await self.db.execute(select(VPNNode).where(VPNNode.id == node_id))
            node = result.scalar_one_or_none()
            
            if not node:
                logger.error("Node not found for client creation", node_id=node_id)
                return None
            
            # Создаем новый клиент
            client = X3UIClient()
            client.base_url = node.x3ui_url
            client.username = node.x3ui_username
            client.password = node.x3ui_password
            
            # Проверяем соединение
            if not await client._login():
                logger.error("Failed to connect to X3UI", 
                           node_id=node_id, 
                           url=node.x3ui_url)
                return None
            
            # Сохраняем в кэш
            self.clients[node_id] = client
            self.last_refresh[node_id] = datetime.utcnow()
            
            logger.info("X3UI client refreshed successfully", 
                       node_id=node_id, 
                       url=node.x3ui_url)
            
            return client
            
        except Exception as e:
            logger.error("Error refreshing X3UI client", 
                        node_id=node_id, 
                        error=str(e))
            return None
    
    async def get_all_clients(self, only_healthy: bool = True) -> Dict[int, X3UIClient]:
        """Получить все клиенты для активных нод"""
        try:
            # Получаем все активные ноды
            if not self.db:
                self.db = next(get_db())
                
            query = select(VPNNode)
            if only_healthy:
                query = query.where(VPNNode.status == 'active')
                query = query.where(VPNNode.health_status == 'healthy')
            
            result = await self.db.execute(query)
            nodes = result.scalars().all()
            
            # Создаем клиентов для всех нод
            clients = {}
            for node in nodes:
                client = await self.get_client(node.id)
                if client:
                    clients[node.id] = client
            
            return clients
            
        except Exception as e:
            logger.error("Error getting all X3UI clients", error=str(e))
            return {}
    
    async def clear_cache(self) -> None:
        """Очистить кэш клиентов"""
        self.clients = {}
        self.last_refresh = {}
        logger.info("X3UI client cache cleared")
    
    async def check_all_connections(self) -> Dict[int, bool]:
        """Проверить соединения со всеми нодами"""
        try:
            # Получаем все ноды
            if not self.db:
                self.db = next(get_db())
                
            result = await self.db.execute(select(VPNNode))
            nodes = result.scalars().all()
            
            # Проверяем соединения
            connection_status = {}
            for node in nodes:
                client = X3UIClient()
                client.base_url = node.x3ui_url
                client.username = node.x3ui_username
                client.password = node.x3ui_password
                
                connection_ok = await client._login()
                connection_status[node.id] = connection_ok
                
                # Обновляем статус ноды
                node.health_status = 'healthy' if connection_ok else 'unhealthy'
                node.last_health_check = datetime.utcnow()
            
            await self.db.commit()
            
            return connection_status
            
        except Exception as e:
            logger.error("Error checking all X3UI connections", error=str(e))
            return {} 