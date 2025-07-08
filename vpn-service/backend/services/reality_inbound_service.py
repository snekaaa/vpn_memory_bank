"""
RealityInboundService - Универсальный сервис для создания VLESS-REALITY inbound'ов
Используется для автоматического и ручного создания нод
"""

import structlog
import json
import secrets
from typing import Optional, Dict, Any, Tuple
from models.vpn_node import VPNNode
from services.reality_key_generator import RealityKeyGenerator, RealityKeys

logger = structlog.get_logger(__name__)

class RealityInboundService:
    """Универсальный сервис для создания Reality inbound'ов"""
    
    @staticmethod
    def generate_reality_keys() -> Tuple[str, str]:
        """Генерация X25519 ключей для Reality через новый генератор"""
        try:
            keys = RealityKeyGenerator.generate_keys()
            if keys.generation_method != "failed":
                logger.info("Reality keys generated", 
                           method=keys.generation_method,
                           public_key=keys.public_key[:20] + "...")
                return keys.public_key, keys.private_key
            else:
                logger.error("RealityKeyGenerator failed to generate keys")
                raise Exception("Key generation failed")
            
        except Exception as e:
            logger.error("Critical error in key generation - NO FALLBACK AVAILABLE", error=str(e))
            # НЕТ FALLBACK! Генерация должна выполняться только правильными методами
            raise Exception(f"Reality key generation failed: {e}")
    
    # УДАЛЕН: _generate_fallback_keys() генерировал неправильные 44-символьные ключи
    
    @staticmethod
    def generate_short_id() -> str:
        """Генерация short ID для Reality"""
        # Short ID должен быть 8 hex символов
        return secrets.token_hex(4)
    
    @staticmethod
    async def create_reality_inbound(
        node: VPNNode,
        port: int = 443,
        sni_mask: str = "apple.com",
        remark: Optional[str] = None,
        private_key: Optional[str] = None,
        public_key: Optional[str] = None
    ) -> bool:
        """
        Создание Reality inbound'а для ноды
        
        Args:
            node: VPNNode объект
            port: Порт для inbound'а (по умолчанию 443)
            sni_mask: SNI маскировка (по умолчанию apple.com)
            remark: Комментарий к inbound'у
            private_key: Приватный Reality ключ (если передан, используется вместо генерации)
            public_key: Публичный Reality ключ (если передан, используется вместо генерации)
        
        Returns:
            bool: True если inbound успешно создан
        """
        try:
            from services.x3ui_client import X3UIClient
            
            logger.info("Creating Reality inbound for node", 
                       node_id=node.id, 
                       node_name=node.name,
                       port=port, 
                       sni_mask=sni_mask)
            
            # Создаем клиент для работы с X3UI API
            client = X3UIClient(
                base_url=node.x3ui_url,
                username=node.x3ui_username, 
                password=node.x3ui_password
            )
            
            # Проверяем подключение
            if not await client._login():
                logger.error("Failed to login to X3UI for inbound creation", node_id=node.id)
                return False
            
            # Используем переданные ключи или генерируем/используем существующие
            if private_key and public_key:
                # Используем переданные ключи (приоритет)
                logger.info("Using provided keys for Reality inbound", 
                           public_key=public_key[:20] + "...",
                           private_key=private_key[:20] + "...")
                temp_private_key = private_key
                final_public_key = public_key
                
                # Обновляем ноду если переданные ключи отличаются
                if node.public_key != public_key:
                    node.public_key = public_key
                    logger.info("Updated node public key with provided key", node_id=node.id)
                    
            elif node.public_key:
                # Используем существующие ключи ноды
                final_public_key = node.public_key
                # Для private_key генерируем новые, так как не храним их в БД
                _, temp_private_key = RealityInboundService.generate_reality_keys()
                logger.info("Using existing node public key", public_key=final_public_key[:20] + "...")
                
            else:
                # Генерируем новые ключи через X3UI клиент (как кнопка Get New Cert)
                keys = await client.generate_reality_keys()
                if keys:
                    final_public_key = keys["public_key"]
                    temp_private_key = keys["private_key"]
                    node.public_key = final_public_key
                    logger.info("Generated new keys via X3UI client (Get New Cert equivalent)", 
                               public_key=final_public_key[:20] + "...",
                               private_key=temp_private_key[:20] + "...")
                else:
                    # Fallback к старому методу
                    final_public_key, temp_private_key = RealityInboundService.generate_reality_keys()
                    node.public_key = final_public_key
                    logger.warning("Fallback to old key generation method")
            
            # Генерируем short_id если его нет
            short_id = node.short_id or RealityInboundService.generate_short_id()
            if not node.short_id:
                node.short_id = short_id

            # КРИТИЧЕСКИ ВАЖНО: Сохраняем обновления ноды в БД
            try:
                from config.database import get_db_session
                async with get_db_session() as session:
                    # Находим ноду в текущей сессии
                    from sqlalchemy import select
                    result = await session.execute(select(VPNNode).where(VPNNode.id == node.id))
                    db_node = result.scalar_one_or_none()
                    if db_node:
                        db_node.public_key = node.public_key
                        db_node.short_id = node.short_id
                        await session.commit()
                        logger.info("Reality keys saved to database", 
                                   node_id=node.id,
                                   public_key=node.public_key[:20] + "..." if node.public_key else None,
                                   short_id=node.short_id)
            except Exception as save_error:
                logger.error("Failed to save Reality keys to database", 
                           node_id=node.id, 
                           error=str(save_error))
            
            # Рамарк по умолчанию
            if not remark:
                remark = f"Reality-{node.name}"
            
            # Конфигурация Reality inbound'а с ВСЕМИ ПРАВИЛЬНЫМИ настройками
            inbound_config = {
                "enable": True,
                "remark": remark,
                "port": port,
                "protocol": "vless",
                "settings": json.dumps({
                    "clients": [],
                    "decryption": "none",
                    "fallbacks": []
                }),
                "streamSettings": json.dumps({
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "xver": 0,
                        "dest": f"{sni_mask}:443",
                        "serverNames": [sni_mask],
                        "privateKey": temp_private_key,
                        "publicKey": final_public_key,
                        "maxTimeDiff": 0,
                        "shortIds": [short_id, ""],
                        "fingerprint": "chrome",
                        "spiderX": "/"
                    },
                    "tcpSettings": {
                        "acceptProxyProtocol": False,
                        "header": {
                            "type": "none"
                        }
                    }
                }),
                "tag": f"inbound-{port}",
                "sniffing": json.dumps({
                    "enabled": False,  # ВЫКЛЮЧАЕМ SNIFFING как просил пользователь
                    "destOverride": []
                })
            }
            
            # Валидируем ключи перед созданием
            if not RealityKeyGenerator.validate_keys(temp_private_key, final_public_key):
                logger.error("Invalid Reality keys detected, regenerating",
                           private_key=temp_private_key[:20] + "...",
                           public_key=final_public_key[:20] + "...")
                
                # Генерируем новые валидные ключи
                fresh_keys = RealityKeyGenerator.generate_keys()
                temp_private_key = fresh_keys.private_key
                final_public_key = fresh_keys.public_key
                
                # Обновляем конфигурацию с валидными ключами
                inbound_config["streamSettings"] = json.dumps({
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "xver": 0,
                        "dest": f"{sni_mask}:443",
                        "serverNames": [sni_mask],
                        "privateKey": temp_private_key,
                        "publicKey": final_public_key,
                        "maxTimeDiff": 0,
                        "shortIds": [short_id, ""],
                        "fingerprint": "chrome",
                        "spiderX": "/"
                    },
                    "tcpSettings": {
                        "acceptProxyProtocol": False,
                        "header": {
                            "type": "none"
                        }
                    }
                })
                
                # Обновляем ноду с валидными ключами
                node.public_key = final_public_key
                logger.info("Regenerated valid Reality keys",
                           public_key=final_public_key[:20] + "...")
            
            # Логируем финальные ключи для отладки
            logger.info("Reality inbound configuration prepared with validated keys", 
                       private_key=temp_private_key[:20] + "...",
                       public_key=final_public_key[:20] + "...",
                       short_id=short_id,
                       port=port,
                       sniffing_disabled=True)
            
            logger.info("Sending Reality inbound configuration to X3UI", 
                       node_id=node.id,
                       port=port, 
                       sni=sni_mask)
            
            # Создаем inbound через API
            result = await client._make_request(
                "POST", 
                "/panel/api/inbounds/add",
                inbound_config
            )
            
            if result and result.get("success"):
                logger.info("Reality inbound created successfully with valid keys", 
                           node_id=node.id,
                           node_name=node.name,
                           port=port, 
                           remark=remark,
                           public_key=final_public_key[:20] + "...")
                
                return True
            else:
                logger.error("Failed to create Reality inbound", 
                           node_id=node.id,
                           result=result)
                return False
                
        except Exception as e:
            logger.error("Error creating Reality inbound", 
                        node_id=node.id if node else "unknown",
                        error=str(e), 
                        exc_info=True)
            return False
    
    @staticmethod 
    async def ensure_reality_inbound_exists(
        node: VPNNode,
        port: int = 443,
        sni_mask: str = "apple.com"
    ) -> bool:
        """
        Проверяет наличие Reality inbound'а и создает его если отсутствует
        
        Returns:
            bool: True если inbound существует или был создан успешно
        """
        try:
            from services.x3ui_client import X3UIClient
            
            # Создаем клиент для проверки
            client = X3UIClient(
                base_url=node.x3ui_url,
                username=node.x3ui_username, 
                password=node.x3ui_password
            )
            
            if not await client._login():
                logger.error("Failed to login to X3UI for inbound check", node_id=node.id)
                return False
            
            # Получаем список inbound'ов
            inbounds = await client.get_inbounds()
            
            if not inbounds:
                logger.info("No inbounds found, creating Reality inbound", node_id=node.id)
                return await RealityInboundService.create_reality_inbound(node, port, sni_mask)
            
            # Проверяем наличие Reality inbound'а ИМЕННО на порту 443 (для HTTPS маскировки)
            reality_inbound_exists = False
            for inbound in inbounds:
                if (inbound.get("protocol") == "vless" and 
                    inbound.get("port") == 443 and  # Требуем именно порт 443
                    inbound.get("enable") == True):
                    
                    # Проверяем что это Reality
                    stream_settings = json.loads(inbound.get("streamSettings", "{}"))
                    if stream_settings.get("security") == "reality":
                        reality_inbound_exists = True
                        logger.info("Reality inbound already exists on port 443", 
                                   node_id=node.id, 
                                   inbound_id=inbound.get("id"),
                                   port=443)
                        break
            
            if not reality_inbound_exists:
                logger.info("Reality inbound not found, creating new one", 
                           node_id=node.id, 
                           port=port)
                return await RealityInboundService.create_reality_inbound(node, port, sni_mask)
            
            return True
            
        except Exception as e:
            logger.error("Error checking Reality inbound existence", 
                        node_id=node.id,
                        error=str(e))
            return False
    
    @staticmethod
    async def update_reality_inbound_keys(
        node: VPNNode,
        private_key: str,
        public_key: str,
        inbound_id: Optional[int] = None,
        port: int = 443
    ) -> bool:
        """
        Обновление ключей существующего Reality inbound'а
        
        Args:
            node: VPNNode объект
            private_key: Новый приватный ключ
            public_key: Новый публичный ключ
            inbound_id: ID инбаунда (если не указан, ищется автоматически)
            port: Порт инбаунда для поиска
        
        Returns:
            bool: True если ключи успешно обновлены
        """
        try:
            from services.x3ui_client import X3UIClient
            
            logger.info("Updating Reality inbound keys", 
                       node_id=node.id,
                       public_key=public_key[:20] + "...",
                       private_key=private_key[:20] + "...")
            
            # Создаем клиент для работы с X3UI API
            client = X3UIClient(
                base_url=node.x3ui_url,
                username=node.x3ui_username,
                password=node.x3ui_password
            )
            
            # Проверяем подключение
            if not await client._login():
                logger.error("Failed to login to X3UI for key update", node_id=node.id)
                return False
            
            # Получаем список инбаундов
            inbounds_response = await client._make_request("GET", "/panel/api/inbounds/list")
            
            if not inbounds_response or not inbounds_response.get("success"):
                logger.error("Failed to get inbounds list", node_id=node.id)
                return False
            
            inbounds = inbounds_response.get("obj", [])
            
            # Ищем Reality инбаунд
            target_inbound = None
            if inbound_id:
                # Ищем по ID
                target_inbound = next((ib for ib in inbounds if ib.get("id") == inbound_id), None)
            else:
                # Ищем по порту и протоколу VLESS
                target_inbound = next((ib for ib in inbounds 
                                     if ib.get("port") == port and ib.get("protocol") == "vless"), None)
            
            if not target_inbound:
                logger.error("Reality inbound not found", node_id=node.id, port=port, inbound_id=inbound_id)
                return False
            
            # Получаем текущие настройки инбаунда
            stream_settings = target_inbound.get("streamSettings", "{}")
            if isinstance(stream_settings, str):
                stream_settings = json.loads(stream_settings)
            
            # Обновляем Reality ключи
            reality_settings = stream_settings.get("realitySettings", {})
            reality_settings["privateKey"] = private_key
            reality_settings["publicKey"] = public_key
            
            stream_settings["realitySettings"] = reality_settings
            
            # Подготавливаем данные для обновления
            update_data = {
                "id": target_inbound["id"],
                "remark": target_inbound["remark"],
                "enable": target_inbound["enable"],
                "port": target_inbound["port"],
                "protocol": target_inbound["protocol"],
                "settings": target_inbound["settings"],
                "streamSettings": json.dumps(stream_settings),
                "tag": target_inbound["tag"],
                "sniffing": target_inbound["sniffing"]
            }
            
            logger.info("Updating inbound with new Reality keys", 
                       inbound_id=target_inbound["id"],
                       public_key=public_key[:20] + "...",
                       private_key=private_key[:20] + "...")
            
            # Обновляем инбаунд
            update_response = await client._make_request(
                "POST",
                f"/panel/api/inbounds/update/{target_inbound['id']}",
                update_data
            )
            
            if update_response and update_response.get("success"):
                logger.info("Reality inbound keys updated successfully", 
                           node_id=node.id,
                           inbound_id=target_inbound["id"])
                
                # Обновляем публичный ключ в ноде
                node.public_key = public_key
                
                # КРИТИЧЕСКИ ВАЖНО: Сохраняем обновления ноды в БД
                try:
                    from config.database import get_db_session
                    async with get_db_session() as session:
                        # Находим ноду в текущей сессии
                        from sqlalchemy import select
                        result = await session.execute(select(VPNNode).where(VPNNode.id == node.id))
                        db_node = result.scalar_one_or_none()
                        if db_node:
                            db_node.public_key = public_key
                            await session.commit()
                            logger.info("Updated public key saved to database", 
                                       node_id=node.id,
                                       public_key=public_key[:20] + "...")
                except Exception as save_error:
                    logger.error("Failed to save updated public key to database", 
                               node_id=node.id, 
                               error=str(save_error))
                
                return True
            else:
                logger.error("Failed to update Reality inbound keys", 
                           node_id=node.id,
                           response=update_response)
                return False
                
        except Exception as e:
            logger.error("Error updating Reality inbound keys", 
                        node_id=node.id if node else "unknown",
                        error=str(e),
                        exc_info=True)
            return False 