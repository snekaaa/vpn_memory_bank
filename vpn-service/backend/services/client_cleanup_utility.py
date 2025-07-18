"""
Утилита для массового удаления клиентов из 3xui панели.
Используется для очистки панели от старых/неиспользуемых клиентов.
"""

import asyncio
import structlog
import json
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime

from services.x3ui_client import X3UIClient
from models.vpn_node import VPNNode
from models.vpn_key import VPNKey, VPNKeyStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

logger = structlog.get_logger(__name__)

class ClientCleanupUtility:
    """
    Утилита для массового удаления клиентов из 3xui панели
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_active_nodes(self) -> List[VPNNode]:
        """Получение списка активных нод"""
        node_result = await self.session.execute(
            select(VPNNode).where(VPNNode.status == "active")
        )
        return list(node_result.scalars().all())
    
    async def get_clients_on_node(self, node: VPNNode) -> List[Dict]:
        """Получение списка всех клиентов на ноде"""
        x3ui_client = X3UIClient(
            base_url=node.x3ui_url,
            username=node.x3ui_username,
            password=node.x3ui_password
        )
        
        if not await x3ui_client._login():
            logger.error("Не удалось подключиться к X3UI панели", node_id=node.id)
            return []
            
        inbounds = await x3ui_client.get_inbounds()
        if not inbounds:
            logger.error("Не удалось получить список inbound'ов", node_id=node.id)
            return []
            
        all_clients = []
        for inbound in inbounds:
            inbound_id = inbound.get("id")
            try:
                settings = json.loads(inbound.get("settings", "{}"))
                clients = settings.get("clients", [])
                
                for client in clients:
                    client["inbound_id"] = inbound_id
                    all_clients.append(client)
            except Exception as e:
                logger.error("Ошибка при обработке inbound'а", 
                            node_id=node.id, 
                            inbound_id=inbound_id,
                            error=str(e))
        
        return all_clients
    
    async def get_active_keys_from_db(self) -> List[VPNKey]:
        """Получение списка активных ключей из базы данных"""
        key_result = await self.session.execute(
            select(VPNKey).where(VPNKey.status.in_(["active", "ACTIVE", VPNKeyStatus.ACTIVE.value]))
        )
        return list(key_result.scalars().all())
    
    async def find_orphaned_clients(self, node: VPNNode) -> Tuple[List[Dict], List[Dict]]:
        """Поиск осиротевших клиентов на ноде (которых нет в базе данных)"""
        # Получаем всех клиентов с ноды
        node_clients = await self.get_clients_on_node(node)
        if not node_clients:
            return [], []
            
        # Получаем активные ключи из базы данных
        active_keys = await self.get_active_keys_from_db()
        
        # Собираем ID клиентов и email из базы данных
        db_client_ids = set([key.xui_client_id for key in active_keys if key.xui_client_id])
        db_client_emails = set([key.xui_email for key in active_keys if key.xui_email])
        
        # Находим клиентов, которых нет в базе данных
        orphaned_clients = []
        duplicate_clients = []
        email_count = {}
        
        for client in node_clients:
            client_id = client.get("id")
            email = client.get("email", "")
            
            # Подсчитываем количество клиентов с одинаковым email
            email_count[email] = email_count.get(email, 0) + 1
            
            # Если клиента нет в базе данных
            if client_id not in db_client_ids and email not in db_client_emails:
                orphaned_clients.append(client)
                
        # Находим дубликаты (клиенты с одинаковым email)
        for client in node_clients:
            email = client.get("email", "")
            if email_count.get(email, 0) > 1:
                # Проверяем, есть ли активный ключ с этим email в базе
                is_in_db = email in db_client_emails
                
                if is_in_db:
                    # Если клиент есть в базе, но есть дубликаты, находим самый свежий
                    duplicate_clients.append({
                        **client,
                        "in_database": is_in_db
                    })
        
        return orphaned_clients, duplicate_clients
    
    async def delete_orphaned_clients(self, node: VPNNode) -> Dict:
        """Удаление осиротевших клиентов с ноды"""
        orphaned_clients, duplicate_clients = await self.find_orphaned_clients(node)
        
        if not orphaned_clients and not duplicate_clients:
            return {
                "success": True,
                "deleted_orphaned": 0,
                "deleted_duplicates": 0,
                "message": "Нет осиротевших клиентов или дубликатов для удаления"
            }
        
        x3ui_client = X3UIClient(
            base_url=node.x3ui_url,
            username=node.x3ui_username,
            password=node.x3ui_password
        )
        
        if not await x3ui_client._login():
            return {
                "success": False,
                "error": "Не удалось подключиться к X3UI панели"
            }
        
        # Удаляем осиротевших клиентов
        deleted_orphaned = 0
        for client in orphaned_clients:
            client_id = client.get("id")
            inbound_id = client.get("inbound_id")
            email = client.get("email", "")
            
            logger.info("Удаление осиротевшего клиента", 
                      client_id=client_id,
                      inbound_id=inbound_id,
                      email=email)
            
            delete_result = await x3ui_client.delete_client(inbound_id, client_id)
            
            if delete_result:
                deleted_orphaned += 1
                logger.info("Осиротевший клиент успешно удален", 
                          client_id=client_id,
                          email=email)
            else:
                logger.error("Не удалось удалить осиротевшего клиента", 
                           client_id=client_id,
                           email=email)
        
        # Удаляем дубликаты (оставляя самый свежий, если он в базе данных)
        processed_emails = set()
        deleted_duplicates = 0
        
        # Сортируем дубликаты так, чтобы записи из базы были первыми
        duplicate_clients.sort(key=lambda c: (c.get("in_database", False), c.get("email", "")), reverse=True)
        
        for client in duplicate_clients:
            email = client.get("email", "")
            client_id = client.get("id")
            inbound_id = client.get("inbound_id")
            in_database = client.get("in_database", False)
            
            # Пропускаем первое вхождение для каждого email (оставляем его)
            if email in processed_emails:
                logger.info("Удаление дубликата клиента", 
                          client_id=client_id,
                          inbound_id=inbound_id,
                          email=email,
                          in_database=in_database)
                
                delete_result = await x3ui_client.delete_client(inbound_id, client_id)
                
                if delete_result:
                    deleted_duplicates += 1
                    logger.info("Дубликат клиента успешно удален", 
                              client_id=client_id,
                              email=email)
                else:
                    logger.error("Не удалось удалить дубликат клиента", 
                               client_id=client_id,
                               email=email)
            else:
                processed_emails.add(email)
                logger.info("Оставляем клиента (не дубликат или первое вхождение)", 
                          client_id=client_id,
                          email=email,
                          in_database=in_database)
        
        return {
            "success": True,
            "deleted_orphaned": deleted_orphaned,
            "deleted_duplicates": deleted_duplicates,
            "total_deleted": deleted_orphaned + deleted_duplicates,
            "message": f"Удалено {deleted_orphaned} осиротевших клиентов и {deleted_duplicates} дубликатов"
        }
    
    async def cleanup_all_nodes(self) -> Dict:
        """Очистка всех нод от осиротевших клиентов"""
        nodes = await self.get_active_nodes()
        if not nodes:
            return {
                "success": False,
                "error": "Не найдено активных нод"
            }
        
        total_results = {
            "success": True,
            "nodes_processed": 0,
            "total_deleted": 0,
            "deleted_orphaned": 0,
            "deleted_duplicates": 0,
            "node_results": []
        }
        
        for node in nodes:
            try:
                logger.info("Очистка ноды от осиротевших клиентов", 
                          node_id=node.id, 
                          node_name=node.name)
                
                result = await self.delete_orphaned_clients(node)
                
                if result.get("success"):
                    total_results["nodes_processed"] += 1
                    total_results["total_deleted"] += result.get("total_deleted", 0)
                    total_results["deleted_orphaned"] += result.get("deleted_orphaned", 0)
                    total_results["deleted_duplicates"] += result.get("deleted_duplicates", 0)
                
                total_results["node_results"].append({
                    "node_id": node.id,
                    "node_name": node.name,
                    "result": result
                })
                
            except Exception as e:
                logger.error("Ошибка при очистке ноды", 
                           node_id=node.id, 
                           node_name=node.name,
                           error=str(e))
                
                total_results["node_results"].append({
                    "node_id": node.id,
                    "node_name": node.name,
                    "error": str(e)
                })
        
        total_results["message"] = (
            f"Обработано {total_results['nodes_processed']} нод. "
            f"Удалено {total_results['total_deleted']} клиентов "
            f"({total_results['deleted_orphaned']} осиротевших, "
            f"{total_results['deleted_duplicates']} дубликатов)."
        )
        
        return total_results

async def cleanup_clients(session: AsyncSession) -> Dict:
    """Функция для очистки всех нод от осиротевших клиентов"""
    utility = ClientCleanupUtility(session)
    return await utility.cleanup_all_nodes() 