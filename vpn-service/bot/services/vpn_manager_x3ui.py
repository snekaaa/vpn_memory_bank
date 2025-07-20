"""
VPN Manager с прямой интеграцией X3UI
Решение проблемы "обновить ключ" через использование оригинального X3UI клиента
"""
import structlog
import aiohttp
import os
import json
from typing import Dict, Any, Optional, List

logger = structlog.get_logger(__name__)

class VPNManagerX3UI:
    """VPN Manager с прямой интеграцией X3UI для исправления 'обновить ключ'"""
    
    def __init__(self):
        # Используем localhost для локального тестирования, backend:8000 для Docker
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self._session = None
        logger.info("VPN Manager X3UI initialized", 
                   backend_url=self.backend_url)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить HTTP сессию"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Закрыть HTTP сессию"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Выполнить HTTP запрос к backend API"""
        try:
            session = await self._get_session()
            url = f"{self.backend_url}{endpoint}"
            
            if method.upper() == "GET":
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error("Backend API error", 
                                   method=method, 
                                   url=url, 
                                   status=response.status)
                        return None
            else:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error("Backend API error", 
                                   method=method, 
                                   url=url, 
                                   status=response.status)
                        return None
                        
        except Exception as e:
            logger.error("Request error", 
                        method=method, 
                        endpoint=endpoint, 
                        error=str(e))
            return None

    async def update_user_key(self, telegram_id: int, username: str = "", first_name: str = "") -> Dict:
        """
        Обновить ключ пользователя через простой backend API
        """
        try:
            logger.info("🔄 Updating user key via simple backend API", 
                       telegram_id=telegram_id, 
                       username=username)
            
            # Используем новый простой API для обновления ключей с force_new=True
            vpn_result = await self._make_request(
                "POST",
                "/api/v1/integration/update-vpn-key",
                {
                    "telegram_id": telegram_id,
                    "force_new": True  # Всегда создаем новый ключ при обновлении
                }
            )
            
            if vpn_result and vpn_result.get("success"):
                # Проверяем формат ответа - он может быть в двух вариантах:
                # 1. С полем vpn_key (новый формат)
                # 2. С полями vless_url, id и т.д. на верхнем уровне (старый формат)
                
                if "vpn_key" in vpn_result:
                    # Новый формат
                    vpn_key = vpn_result.get("vpn_key", {})
                    
                    logger.info("✅ Key updated successfully via simple API (new format)", 
                               telegram_id=telegram_id,
                               key_id=vpn_key.get("id"),
                               force_new=True)
                    
                    return {
                        "success": True,
                        "message": vpn_result.get("message", "VPN ключ обновлен"),
                        "vless_url": vpn_key.get("vless_url"),
                        "id": vpn_key.get("id"),
                        "created_at": vpn_key.get("created_at"),
                        "status": vpn_key.get("status", "active"),
                        "is_new": True,
                        "x3ui_connected": True,
                        "source": "SIMPLE_BACKEND_API_FORCE_NEW"
                    }
                else:
                    # Старый формат или прямые поля
                    logger.info("✅ Key updated successfully via simple API (direct fields)", 
                               telegram_id=telegram_id,
                               key_id=vpn_result.get("id"),
                               force_new=True)
                    
                    return {
                        "success": True,
                        "message": vpn_result.get("message", "VPN ключ обновлен"),
                        "vless_url": vpn_result.get("vless_url"),
                        "id": vpn_result.get("id"),
                        "created_at": vpn_result.get("created_at"),
                        "status": vpn_result.get("status", "active"),
                        "is_new": True,
                        "x3ui_connected": True,
                        "source": "SIMPLE_BACKEND_API_FORCE_NEW"
                    }
            else:
                error_msg = vpn_result.get("error", "Unknown error") if vpn_result else "API unavailable"
                logger.error("❌ Failed to update key via simple API", 
                            telegram_id=telegram_id,
                            error=error_msg)
                return {"success": False, "error": error_msg}
            
        except Exception as e:
            logger.error("❌ Failed to update key via simple API", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return {"success": False, "error": str(e)}

    async def create_key_for_user_country(self, telegram_id: int, username: str = "", first_name: str = "") -> Dict:
        """Создать VPN ключ для пользователя с учетом назначенной страны"""
        try:
            logger.info("🌍 Creating VPN key for user country", 
                       telegram_id=telegram_id)
            
            # Используем новый API endpoint
            result = await self._make_request(
                "POST",
                f"/api/v1/vpn-keys/user/{telegram_id}/create-for-country"
            )
            
            if result and result.get("success"):
                vpn_key = result.get("vpn_key", {})
                
                logger.info("✅ Created key for user country", 
                           telegram_id=telegram_id,
                           key_id=vpn_key.get("id"),
                           node_id=vpn_key.get("node_id"),
                           country=vpn_key.get("country"))
                
                return {
                    "success": True,
                    "message": result.get("message", "VPN key created"),
                    "vless_url": vpn_key.get("vless_url"),
                    "id": vpn_key.get("id"),
                    "created_at": vpn_key.get("created_at"),
                    "status": "active",
                    "is_new": True,
                    "node_id": vpn_key.get("node_id"),
                    "node_name": vpn_key.get("node_name"),
                    "country": vpn_key.get("country"),
                    "source": "COUNTRY_AWARE_CREATION"
                }
            else:
                logger.error("Failed to create key for country", 
                           telegram_id=telegram_id,
                           result=result)
                
                # Fallback к обычному методу
                return await self.update_user_key(telegram_id, username, first_name)
                
        except Exception as e:
            logger.error("Error creating key for user country", 
                        telegram_id=telegram_id, 
                        error=str(e))
            
            # Fallback к обычному методу
            return await self.update_user_key(telegram_id, username, first_name)

    async def get_or_create_user_key_with_node(self, telegram_id: int, node_id: int, username: str = "", first_name: str = "") -> Dict:
        """Получить ключ пользователя с конкретной ноды или создать новый"""
        try:
            logger.info("🔍 Getting user key for specific node", 
                       telegram_id=telegram_id, node_id=node_id)
            
            # Проверяем, есть ли у пользователя ключ с этой ноды
            dashboard_result = await self._make_request(
                "GET", 
                f"/api/v1/integration/user-dashboard/{telegram_id}"
            )
            
            if dashboard_result and dashboard_result.get("success"):
                # Пользователь существует, ищем ключ с нужной ноды
                vpn_keys = dashboard_result.get("vpn_keys", [])
                node_keys = [key for key in vpn_keys if key.get("node_id") == node_id and key.get("status") in ["active", "ACTIVE"]]
                
                if node_keys:
                    # Есть ключ с нужной ноды - возвращаем его
                    latest_key = sorted(node_keys, key=lambda k: k.get("id", 0), reverse=True)[0]
                    
                    logger.info("✅ Found existing key for node", 
                               telegram_id=telegram_id,
                               key_id=latest_key.get("id"),
                               node_id=node_id)
                    
                    return {
                        "success": True,
                        "message": f"Получен ключ с ноды {node_id}",
                        "vless_url": latest_key.get("vless_url"),
                        "id": latest_key.get("id"),
                        "created_at": latest_key.get("created_at"),
                        "status": "active",
                        "is_new": False,
                        "node_id": node_id,
                        "source": "EXISTING_KEY_SPECIFIC_NODE"
                    }
            
            # Нет ключа с нужной ноды - создаем новый через обычный метод
            # Предполагаем что ноды правильно назначены через country assignment
            logger.info("🆕 No key for specific node, creating new one", 
                       telegram_id=telegram_id, node_id=node_id)
            
            result = await self.update_user_key(telegram_id, username, first_name)
            
            if result and result.get("vless_url"):
                logger.info("✅ Created new key (should be on correct node via assignment)", 
                           telegram_id=telegram_id)
                return result
            
            # Fallback к обычному методу
            logger.warning("Failed to create key, using fallback", 
                          telegram_id=telegram_id, node_id=node_id)
            return await self.get_or_create_user_key(telegram_id, username, first_name)
            
        except Exception as e:
            logger.error("Error getting key for specific node", 
                        telegram_id=telegram_id, 
                        node_id=node_id,
                        error=str(e))
            # Fallback к обычному методу
            return await self.get_or_create_user_key(telegram_id, username, first_name)

    async def get_or_create_user_key(self, telegram_id: int, username: str = "", first_name: str = "") -> Dict:
        """Получить или создать ключ пользователя через простой backend API"""
        try:
            logger.info("🔍 Getting or creating user key via simple backend API", 
                       telegram_id=telegram_id)
            
            # Сначала проверяем, есть ли пользователь в системе
            dashboard_result = await self._make_request(
                "GET", 
                f"/api/v1/integration/user-dashboard/{telegram_id}"
            )
            
            if dashboard_result and dashboard_result.get("success"):
                # Пользователь существует, проверяем активные ключи
                vpn_keys = dashboard_result.get("vpn_keys", [])
                active_keys = [key for key in vpn_keys if key.get("status") in ["active", "ACTIVE"]]
                
                if active_keys:
                    # Есть активный ключ - возвращаем последний
                    latest_key = sorted(active_keys, key=lambda k: k.get("id", 0), reverse=True)[0]
                    
                    logger.info("✅ Found existing active key", 
                               telegram_id=telegram_id,
                               key_id=latest_key.get("id"))
                    
                    return {
                        "success": True,
                        "message": "Получен существующий VPN ключ",
                        "vless_url": latest_key.get("vless_url"),
                        "id": latest_key.get("id"),
                        "created_at": latest_key.get("created_at"),
                        "status": "active",
                        "is_new": False,
                        "x3ui_connected": False,
                        "source": "EXISTING_KEY"
                    }
                else:
                    # Пользователь есть, но нет активных ключей - создаем новый
                    logger.info("🔄 User exists but no active keys - updating", 
                               telegram_id=telegram_id)
                    return await self.update_user_key(telegram_id, username, first_name)
            
            # Пользователя нет - создаем через full-cycle
            logger.info("🆕 Creating new user via full-cycle", 
                       telegram_id=telegram_id)
            
            user_data = {
                "username": username,
                "first_name": first_name or f"User_{telegram_id}",
                "language_code": "ru"
            }
            
            cycle_result = await self._make_request(
                "POST",
                "/api/v1/integration/full-cycle",
                {
                    "telegram_id": telegram_id,
                    "user_data": user_data,
                    "subscription_type": "trial"
                }
            )
            
            if cycle_result and cycle_result.get("success"):
                # Получаем VPN ключ из результата создания пользователя
                final_data = cycle_result.get("final_data", {})
                vpn_key = final_data.get("vpn_key", {})
                
                if vpn_key and vpn_key.get("vless_url"):
                    logger.info("✅ Created user and key via full-cycle", 
                               telegram_id=telegram_id,
                               key_id=vpn_key.get("id"))
                    
                    return {
                        "success": True,
                        "message": "Создан новый пользователь и VPN ключ",
                        "vless_url": vpn_key.get("vless_url"),
                        "id": vpn_key.get("id"),
                        "created_at": vpn_key.get("created_at"),
                        "status": "active",
                        "is_new": True,
                        "x3ui_connected": True,
                        "source": "FULL_CYCLE_NEW_USER"
                    }
                else:
                    logger.error("❌ Full-cycle completed but no VPN key", 
                                telegram_id=telegram_id)
                    return {"success": False, "error": "No VPN key after user creation"}
            else:
                error_msg = cycle_result.get("error", "Unknown error") if cycle_result else "API unavailable"
                logger.error("❌ Failed to create user via full-cycle", 
                            telegram_id=telegram_id,
                            error=error_msg)
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            logger.error("❌ Failed to create user and key", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return {"success": False, "error": str(e)}
    
    async def get_user_keys(self, telegram_id: int) -> List[Dict]:
        """Получить все ключи пользователя"""
        try:
            dashboard_result = await self._make_request(
                "GET", 
                f"/api/v1/integration/user-dashboard/{telegram_id}"
            )
            
            if dashboard_result and dashboard_result.get("success"):
                vpn_keys = dashboard_result.get("vpn_keys", [])
                
                result = []
                for key in vpn_keys:
                    result.append({
                        "id": key.get("id"),
                        "config": key.get("vless_url"),
                        "created_at": key.get("created_at"),
                        "is_active": key.get("status") == "active",
                        "subscription_type": "api",
                        "node_info": key.get("node_info", {})
                    })
                
                return result
            
            return []
            
        except Exception as e:
            logger.error("Error getting user keys", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return []
    
    async def deactivate_key(self, key_id: int) -> bool:
        """
        Правильная деактивация ключа:
        1. Вызываем backend API для удаления ключа из X3UI панели
        2. Backend сам обеспечит правильную последовательность операций
        3. Возвращаем результат операции
        """
        try:
            logger.info("🗑️ Deactivating VPN key via backend API", key_id=key_id)
            
            # Вызываем специальный endpoint для удаления ключа
            # Этот endpoint должен обеспечить правильную последовательность:
            # удаление из X3UI панели → деактивация в БД
            result = await self._make_request(
                "DELETE",
                f"/api/v1/integration/vpn-key/{key_id}",
                {"ensure_x3ui_deletion": True}
            )
            
            if result and result.get("success"):
                logger.info("✅ VPN key successfully deactivated", 
                          key_id=key_id,
                          message=result.get("message"))
                return True
            else:
                error_msg = result.get("error", "Unknown error") if result else "API unavailable"
                logger.error("❌ Failed to deactivate VPN key", 
                           key_id=key_id,
                           error=error_msg)
                return False
                
        except Exception as e:
            logger.error("💥 Error deactivating VPN key", 
                        key_id=key_id, 
                        error=str(e))
            return False

# Создаем экземпляр для использования
vpn_manager_x3ui = VPNManagerX3UI() 