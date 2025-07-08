"""
Простой сервис для работы с X3UI панелью - получение готовых ключей
"""
import structlog
import aiohttp
import json
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.vpn_node import VPNNode

logger = structlog.get_logger(__name__)

class X3UIPanelService:
    """Простой сервис для получения готовых ключей из X3UI панели"""
    
    def __init__(self, node: VPNNode):
        self.node = node
        self.base_url = node.x3ui_url.rstrip('/')
        self.username = node.x3ui_username
        self.password = node.x3ui_password
        self.session = None

    async def _get_session(self):
        """Получить HTTP сессию"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def login(self) -> bool:
        """Авторизация в X3UI панели"""
        try:
            session = await self._get_session()
            
            login_data = {
                "username": self.username,
                "password": self.password
            }
            
            async with session.post(
                f"{self.base_url}/login",
                data=login_data
            ) as response:
                if response.status == 200:
                    logger.info("X3UI panel login successful", node=self.node.name)
                    return True
                else:
                    logger.error("X3UI panel login failed", 
                               node=self.node.name, 
                               status=response.status)
                    return False
                    
        except Exception as e:
            logger.error("X3UI panel login error", 
                        node=self.node.name, 
                        error=str(e))
            return False

    async def get_client_vless_key(self, email: str) -> Optional[str]:
        """
        Получить готовый VLESS ключ клиента из X3UI панели
        Возвращает готовую VLESS строку как она есть в панели
        """
        try:
            if not await self.login():
                return None
                
            session = await self._get_session()
            
            # Получаем список всех inbound'ов
            async with session.get(f"{self.base_url}/panel/api/inbounds/list") as response:
                if response.status != 200:
                    logger.error("Failed to get inbounds", status=response.status)
                    return None
                    
                data = await response.json()
                if not data.get("success"):
                    logger.error("Inbounds API error", msg=data.get("msg"))
                    return None
                
                inbounds = data.get("obj", [])
                
                # Ищем клиента по email во всех inbound'ах
                for inbound in inbounds:
                    if not inbound.get("enable", False):
                        continue
                        
                    settings = inbound.get("settings", "{}")
                    if isinstance(settings, str):
                        try:
                            settings = json.loads(settings)
                        except:
                            continue
                    
                    clients = settings.get("clients", [])
                    
                    for client in clients:
                        if client.get("email") == email and client.get("enable", False):
                            # Нашли клиента! Генерируем VLESS URL из настроек inbound'а
                            vless_url = self._generate_vless_from_inbound_client(inbound, client)
                            
                            logger.info("Found client VLESS key in X3UI panel",
                                      email=email,
                                      inbound_id=inbound.get("id"),
                                      port=inbound.get("port"))
                            
                            return vless_url
                
                logger.warning("Client not found in X3UI panel", email=email)
                return None
                
        except Exception as e:
            logger.error("Error getting client VLESS key", 
                        email=email, 
                        error=str(e))
            return None

    def _generate_vless_from_inbound_client(self, inbound: Dict, client: Dict) -> str:
        """
        Генерирует VLESS URL на основе настроек inbound'а и клиента
        Точно так же, как это делает X3UI панель
        """
        try:
            # Базовые параметры
            uuid = client.get("id", "")
            email = client.get("email", "")
            port = inbound.get("port", 443)
            
            # Получаем хост из URL ноды
            host = self.node.x3ui_url.replace("http://", "").replace("https://", "").split(":")[0]
            
            # Парсим stream settings
            stream_settings = inbound.get("streamSettings", {})
            if isinstance(stream_settings, str):
                try:
                    stream_settings = json.loads(stream_settings)
                except:
                    stream_settings = {}
            
            network = stream_settings.get("network", "tcp")
            security = stream_settings.get("security", "none")
            
            # Базовая VLESS строка
            vless_url = f"vless://{uuid}@{host}:{port}?type={network}"
            
            # Добавляем security параметры
            if security == "tls":
                tls_settings = stream_settings.get("tlsSettings", {})
                sni = tls_settings.get("serverName", host)
                alpn_list = tls_settings.get("alpn", ["h2", "http/1.1"])
                alpn = "%2C".join(alpn_list)
                
                vless_url += f"&security=tls&sni={sni}&fp=chrome&alpn={alpn}"
                
            elif security == "reality":
                reality_settings = stream_settings.get("realitySettings", {})
                dest = reality_settings.get("dest", f"{host}:443")
                server_name = reality_settings.get("serverNames", [host])[0]
                public_key = reality_settings.get("publicKey", "")
                short_id = reality_settings.get("shortIds", [""])[0]
                
                vless_url += f"&security=reality&pbk={public_key}&fp=chrome&sni={server_name}&sid={short_id}"
            
            # Добавляем имя
            if email:
                vless_url += f"#{email}"
            
            return vless_url
            
        except Exception as e:
            logger.error("Error generating VLESS URL from inbound", error=str(e))
            return f"vless://{uuid}@{host}:{port}#{email}"

    async def create_new_client_and_get_key(self, telegram_id: int, username: str = "", email: str = "") -> Optional[str]:
        """
        Создать нового клиента в X3UI панели и получить готовый VLESS ключ
        """
        try:
            if not await self.login():
                return None
                
            # Используем переданный email или формируем новый в формате [telegram_id]_[timestamp]
            if not email:
                from datetime import datetime
                timestamp = int(datetime.utcnow().timestamp())
                email = f"{telegram_id}_{timestamp}"
            
            session = await self._get_session()
            
            # Получаем лучший inbound (с TLS и портом 443)
            best_inbound = await self._get_best_inbound()
            if not best_inbound:
                logger.error("No suitable inbound found")
                return None
            
            # Создаем клиента
            import uuid as uuid_lib
            client_uuid = str(uuid_lib.uuid4())
            
            client_data = {
                "id": client_uuid,
                "email": email,
                "limitIp": 0,
                "totalGB": 0,
                "expiryTime": 0,
                "enable": True,
                "tgId": str(telegram_id),
                "subId": str(telegram_id)
            }
            
            add_data = {
                "id": best_inbound["id"],
                "settings": json.dumps({"clients": [client_data]})
            }
            
            async with session.post(
                f"{self.base_url}/panel/api/inbounds/addClient",
                data=add_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        # Клиент создан! Теперь получаем его VLESS ключ
                        vless_key = await self.get_client_vless_key(email)
                        
                        logger.info("Created new client and got VLESS key",
                                  email=email,
                                  uuid=client_uuid,
                                  inbound_id=best_inbound["id"])
                        
                        return vless_key
                    else:
                        logger.error("Failed to create client", msg=result.get("msg"))
                        return None
                else:
                    logger.error("Failed to create client", status=response.status)
                    return None
                    
        except Exception as e:
            logger.error("Error creating new client", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return None

    async def _get_best_inbound(self) -> Optional[Dict]:
        """Получить лучший inbound (TLS + порт 443)"""
        try:
            session = await self._get_session()
            
            async with session.get(f"{self.base_url}/panel/api/inbounds/list") as response:
                if response.status != 200:
                    return None
                    
                data = await response.json()
                if not data.get("success"):
                    return None
                
                inbounds = data.get("obj", [])
                best_inbound = None
                best_score = 0
                
                for inbound in inbounds:
                    if not inbound.get("enable", False):
                        continue
                    if inbound.get("protocol") != "vless":
                        continue
                        
                    # Система оценки inbound'ов
                    score = 1
                    port = inbound.get("port", 0)
                    
                    # Проверяем security
                    stream_settings = inbound.get("streamSettings", {})
                    if isinstance(stream_settings, str):
                        try:
                            stream_settings = json.loads(stream_settings)
                        except:
                            stream_settings = {}
                    
                    security = stream_settings.get("security", "none")
                    if security == "tls":
                        score = 3
                    elif security == "reality":
                        score = 2
                    
                    # Бонус за порт 443
                    if port == 443:
                        score += 0.5
                    elif port == 80:
                        score += 0.3
                    
                    if score > best_score:
                        best_score = score
                        best_inbound = inbound
                
                return best_inbound
                
        except Exception as e:
            logger.error("Error getting best inbound", error=str(e))
            return None

    async def disable_client_by_email(self, email: str) -> bool:
        """Отключить клиента в X3UI панели по email (альтернатива удалению)"""
        try:
            if not await self.login():
                return False
                
            session = await self._get_session()
            
            # Находим клиента во всех inbound'ах
            async with session.get(f"{self.base_url}/panel/api/inbounds/list") as response:
                if response.status != 200:
                    return False
                    
                data = await response.json()
                if not data.get("success"):
                    return False
                
                inbounds = data.get("obj", [])
                
                for inbound in inbounds:
                    settings = inbound.get("settings", "{}")
                    if isinstance(settings, str):
                        try:
                            settings = json.loads(settings)
                        except:
                            continue
                    
                    clients = settings.get("clients", [])
                    
                    for i, client in enumerate(clients):
                        if client.get("email") == email:
                            # Найден! Отключаем (disable)
                            client["enable"] = False
                            
                            # Обновляем настройки inbound'а
                            updated_settings = {
                                "clients": clients
                            }
                            
                            update_data = {
                                "id": inbound["id"],
                                "settings": json.dumps(updated_settings),
                                "remark": inbound.get("remark", ""),
                                "protocol": inbound.get("protocol", ""),
                                "port": inbound.get("port", 443),
                                "listen": inbound.get("listen", ""),
                                "sniffing": json.dumps(inbound.get("sniffing", {})),
                                "streamSettings": json.dumps(inbound.get("streamSettings", {}))
                            }
                            
                            async with session.post(
                                f"{self.base_url}/panel/api/inbounds/update/{inbound['id']}",
                                data=update_data
                            ) as update_response:
                                if update_response.status == 200:
                                    result = await update_response.json()
                                    if result.get("success"):
                                        logger.info("✅ Client successfully disabled in X3UI panel",
                                                  email=email,
                                                  inbound_id=inbound["id"])
                                        return True
                                    else:
                                        logger.error("Failed to disable client",
                                                   email=email,
                                                   result=result)
                                        return False
                                else:
                                    logger.error("Failed to update inbound for client disable",
                                               email=email,
                                               status=update_response.status)
                                    return False
                
                logger.warning("Client not found for disable", email=email)
                return False
                
        except Exception as e:
            logger.error("Error disabling client", email=email, error=str(e))
            return False

    async def delete_client_by_email(self, email: str) -> bool:
        """Удалить клиента из X3UI панели по email с проверкой результата"""
        try:
            # Сначала пробуем отключить клиента (это работает лучше чем удаление)
            disable_result = await self.disable_client_by_email(email)
            if disable_result:
                logger.info("✅ Client disabled instead of deleted", email=email)
                return True
            
            # Если отключение не сработало, пробуем удаление
            if not await self.login():
                return False
                
            session = await self._get_session()
            
            # Сначала проверяем, есть ли клиент
            initial_check = await self.get_client_vless_key(email)
            if not initial_check:
                logger.info("Client not found for deletion", email=email)
                return True  # Уже удален
            
            # Находим клиента во всех inbound'ах
            async with session.get(f"{self.base_url}/panel/api/inbounds/list") as response:
                if response.status != 200:
                    return False
                    
                data = await response.json()
                if not data.get("success"):
                    return False
                
                inbounds = data.get("obj", [])
                deletion_attempted = False
                
                for inbound in inbounds:
                    settings = inbound.get("settings", "{}")
                    if isinstance(settings, str):
                        try:
                            settings = json.loads(settings)
                        except:
                            continue
                    
                    clients = settings.get("clients", [])
                    
                    for client in clients:
                        if client.get("email") == email:
                            # Найден! Удаляем
                            delete_data = {
                                "id": inbound["id"],
                                "uuid": client.get("id", "")
                            }
                            
                            async with session.post(
                                f"{self.base_url}/panel/api/inbounds/delClient",
                                data=delete_data
                            ) as del_response:
                                deletion_attempted = True
                                if del_response.status == 200:
                                    # Проверяем content-type ответа
                                    content_type = del_response.headers.get('content-type', '')
                                    if 'application/json' in content_type:
                                        result = await del_response.json()
                                        if result.get("success"):
                                            logger.info("Client deletion request sent",
                                                      email=email,
                                                      inbound_id=inbound["id"])
                                        else:
                                            logger.warning("Deletion request failed",
                                                         email=email,
                                                         result=result)
                                    else:
                                        # Если не JSON, но статус 200 - логируем
                                        text_response = await del_response.text()
                                        logger.info("Client deletion response (non-JSON)",
                                                  email=email,
                                                  response=text_response[:200])
                                else:
                                    logger.error("Deletion request failed",
                                               email=email,
                                               status=del_response.status)
                
                if not deletion_attempted:
                    logger.warning("Client not found for deletion", email=email)
                    return False
                
                # ✅ ВАЖНО: Проверяем, действительно ли клиент удален
                import asyncio
                await asyncio.sleep(1)  # Даем время панели обработать удаление
                
                verification_check = await self.get_client_vless_key(email)
                if verification_check:
                    logger.error("❌ Client still exists after deletion attempt", email=email)
                    return False
                else:
                    logger.info("✅ Client successfully deleted and verified", email=email)
                    return True
                
        except Exception as e:
            logger.error("Error deleting client", email=email, error=str(e))
            return False

    async def close(self):
        """Закрыть HTTP сессию"""
        if self.session:
            await self.session.close()
            self.session = None


async def get_x3ui_panel_service(session: AsyncSession) -> Optional[X3UIPanelService]:
    """Получить сервис для работы с X3UI панелью (лучшая нода)"""
    try:
        # Получаем лучшую активную ноду
        node_result = await session.execute(
            select(VPNNode).where(VPNNode.status == "active")
            .order_by(VPNNode.priority.desc())
            .limit(1)
        )
        best_node = node_result.scalar_one_or_none()
        
        if not best_node:
            logger.error("No active VPN nodes found")
            return None
        
        return X3UIPanelService(best_node)
        
    except Exception as e:
        logger.error("Error creating X3UI panel service", error=str(e))
        return None 