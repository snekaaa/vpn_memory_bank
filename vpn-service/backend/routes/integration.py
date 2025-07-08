from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import time
from services.integration_service import integration_service
from config.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from services.simple_key_update_service import SimpleKeyUpdateService
import structlog
from models.user import User
# from models.subscription import Subscription, SubscriptionStatus  # Убрано - упрощенная архитектура
from services.node_automation import NodeDeploymentConfig
import subprocess
import base64
from sqlalchemy.orm import joinedload
from models.vpn_key import VPNKey

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/integration", tags=["integration"])

class UserCreateRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str = "ru"

class SubscriptionCreateRequest(BaseModel):
    user_id: int
    subscription_type: str = "monthly"
    payment_method: str = "yookassa"

class VPNKeyCreateRequest(BaseModel):
    user_id: int
    subscription_id: int
    key_name: Optional[str] = None

class UpdateVPNKeyRequest(BaseModel):
    telegram_id: int
    force_new: bool = False

class UpdateUserDataRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

@router.post("/create-user")
async def create_user_endpoint(request: UserCreateRequest):
    """Создание пользователя через интеграционный сервис"""
    
    user_data = {
        "username": request.username,
        "first_name": request.first_name,
        "last_name": request.last_name,
        "language_code": request.language_code
    }
    
    result = await integration_service.create_user_with_subscription(
        telegram_id=request.telegram_id,
        user_data=user_data
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.post("/create-subscription")
async def create_subscription_endpoint(request: SubscriptionCreateRequest):
    """Создание подписки с платежом"""
    
    result = await integration_service.create_subscription_with_payment(
        user_id=request.user_id,
        subscription_type=request.subscription_type,
        payment_method=request.payment_method
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.post("/create-vpn-key")
async def create_vpn_key_endpoint(request: VPNKeyCreateRequest):
    """Создание VPN ключа через X3UI"""
    
    result = await integration_service.create_vpn_key_full_cycle(
        user_id=request.user_id,
        subscription_id=request.subscription_id,
        key_name=request.key_name
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result

@router.get("/user-dashboard/{telegram_id}")
async def get_user_dashboard_endpoint(telegram_id: int):
    """Получение полной информации о пользователе"""
    
    result = await integration_service.get_user_dashboard(telegram_id)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    
    return result

@router.post("/full-cycle")
async def full_cycle_endpoint(
    telegram_id: int = Body(...),
    user_data: Dict[str, Any] = Body(...),
    subscription_type: str = Body("monthly")
):
    """
    Полный цикл: создание пользователя -> подписка -> VPN ключ
    End-to-End интеграция всех компонентов
    """
    
    results = {
        "telegram_id": telegram_id,
        "steps": [],
        "success": True,
        "final_data": {}
    }
    
    try:
        # Шаг 1: Создание пользователя (с 7 днями триала)
        user_result = await integration_service.create_user_with_subscription(
            telegram_id=telegram_id,
            user_data=user_data
        )
        
        results["steps"].append({
            "step": "user_creation",
            "success": user_result["success"],
            "message": user_result["message"]
        })
        
        if not user_result["success"]:
            results["success"] = False
            return results
        
        user_id = user_result["user_id"]
        
        # Шаг 2: Создание VPN ключа (упрощенная архитектура без подписок)
        vpn_key_result = await integration_service.create_vpn_key_full_cycle(
            user_id=user_id
        )
        
        results["steps"].append({
            "step": "vpn_key_creation",
            "success": vpn_key_result["success"],
            "message": vpn_key_result["message"]
        })
        
        if not vpn_key_result["success"]:
            results["success"] = False
            return results
        
        # Шаг 3: Получение dashboard
        dashboard_result = await integration_service.get_user_dashboard(telegram_id)
        
        results["steps"].append({
            "step": "dashboard_generation",
            "success": dashboard_result["success"],
            "message": "Dashboard сгенерирован"
        })
        
        # Финальные данные (упрощенная архитектура)
        results["final_data"] = {
            "user": user_result["user"],
            "vpn_key": vpn_key_result["vpn_key"],
            "dashboard": dashboard_result if dashboard_result["success"] else None
        }
        
        results["message"] = "Пользователь создан с 7 днями триала и VPN ключом!"
        
        return results
        
    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        results["message"] = "Ошибка в полном цикле интеграции"
        
        return results

@router.post("/update-vpn-key")
async def update_vpn_key(
    request: UpdateVPNKeyRequest,
    session: AsyncSession = Depends(get_db)
):
    """Обновить VPN ключ пользователя через простой API"""
    try:
        logger.info("📝 Обновление VPN ключа через простой API", 
                   telegram_id=request.telegram_id,
                   force_new=getattr(request, 'force_new', False))
        
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == request.telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return {
                "success": False,
                "error": f"Пользователь с telegram_id {request.telegram_id} не найден"
            }
        
        # Проверяем действительность аккаунта (упрощенная архитектура)
        if not user.has_active_subscription:
            return {
                "success": False,
                "error": "Срок действия аккаунта истек"
            }
        
        # Обновляем ключ через integration service с поддержкой миграции между нодами
        result = await integration_service.update_vpn_key_with_node_migration(
            user_id=user.id
        )
        
        if result["success"]:
            logger.info("✅ VPN ключ успешно обновлен через migration service", 
                       telegram_id=request.telegram_id,
                       key_id=result.get("vpn_key_id"))
            
            # Преобразуем ответ integration_service для совместимости с ботом
            if "vpn_key" in result:
                vpn_key = result["vpn_key"]
                return {
                    "success": True,
                    "message": "VPN ключ успешно обновлен",
                    "vless_url": vpn_key.get("vless_url"),
                    "id": vpn_key.get("id"),
                    "created_at": vpn_key.get("created_at"),
                    "status": vpn_key.get("status")
                }
            else:
                # Если поля vpn_key нет, возвращаем ошибку
                logger.error("❌ Отсутствует поле vpn_key в результате обновления", 
                           telegram_id=request.telegram_id)
                return {
                    "success": False,
                    "error": "Внутренняя ошибка: отсутствует информация о ключе"
                }
        else:
            # Если обновление не удалось, возвращаем ошибку
            logger.error("❌ Ошибка при обновлении VPN ключа", 
                       telegram_id=request.telegram_id,
                       error=result.get("error"))
            return result
        
    except Exception as e:
        logger.error("💥 Ошибка в API обновления VPN ключа", 
                    telegram_id=request.telegram_id, 
                    error=str(e))
        return {
            "success": False,
            "error": f"Внутренняя ошибка сервера: {str(e)}"
        }

@router.get("/test-endpoint")
async def test_endpoint():
    """Простой тестовый endpoint для диагностики"""
    return {"message": "Test endpoint works!", "timestamp": time.time()}

@router.delete("/vpn-key/x3ui/{client_id}")
async def delete_x3ui_key_direct(
    client_id: str,
    inbound_id: int = Body(1),
    node_id: int = Body(None),
    session: AsyncSession = Depends(get_db)
):
    """
    СПЕЦИАЛЬНЫЙ ENDPOINT: Удаление ключа напрямую из X3UI панели
    
    Используется для удаления "призрачных" ключей, которые есть в X3UI панели,
    но отсутствуют в нашей БД из-за рассинхронизации
    """
    try:
        logger.info("🗑️ Direct X3UI key deletion", 
                   client_id=client_id, 
                   inbound_id=inbound_id,
                   node_id=node_id)
        
        # 1. Определяем ноду для подключения
        node = None
        if node_id:
            # Используем указанную ноду
            from models.vpn_node import VPNNode
            node_result = await session.execute(
                select(VPNNode).where(VPNNode.id == node_id)
            )
            node = node_result.scalar_one_or_none()
        else:
            # Ищем ноду по всем активным нодам
            from models.vpn_node import VPNNode
            nodes_result = await session.execute(
                select(VPNNode).where(VPNNode.status == "active")
                .order_by(VPNNode.priority.desc())
            )
            nodes = nodes_result.scalars().all()
            
            # Пробуем найти ключ на каждой ноде
            for test_node in nodes:
                try:
                    from services.x3ui_client import X3UIClient
                    test_client = X3UIClient(
                        base_url=test_node.x3ui_url,
                        username=test_node.x3ui_username,
                        password=test_node.x3ui_password
                    )
                    
                    if await test_client._login():
                        # Проверяем, есть ли этот client_id на этой ноде
                        resp = await test_client._make_request("GET", f"/panel/api/inbounds/get/{inbound_id}")
                        if resp and resp.get("success"):
                            import json
                            obj = resp.get("obj", {})
                            settings = json.loads(obj.get("settings", "{}"))
                            clients = settings.get("clients", [])
                            
                            # Проверяем есть ли наш client_id
                            client_found = any(c.get("id") == client_id for c in clients)
                            if client_found:
                                node = test_node
                                logger.info("✅ Found client on node", 
                                           client_id=client_id, 
                                           node_id=test_node.id,
                                           node_name=test_node.name)
                                break
                        
                        await test_client.close()
                except Exception as e:
                    logger.warning("Error checking node", node_id=test_node.id, error=str(e))
                    continue
        
        if not node:
            return {
                "success": False,
                "error": f"Не удалось найти ноду с клиентом {client_id}"
            }
        
        # 2. Подключаемся к найденной ноде и удаляем ключ
        try:
            from services.x3ui_client import X3UIClient
            
            x3ui_client = X3UIClient(
                base_url=node.x3ui_url,
                username=node.x3ui_username,
                password=node.x3ui_password
            )
            
            if await x3ui_client._login():
                logger.info("✅ Connected to X3UI panel for direct deletion", 
                           node_id=node.id,
                           client_id=client_id)
                
                # Удаляем клиента
                delete_result = await x3ui_client.delete_client(inbound_id, client_id)
                
                if delete_result:
                    logger.info("✅ Client successfully deleted from X3UI panel (direct)", 
                               client_id=client_id,
                               node_id=node.id,
                               inbound_id=inbound_id)
                    
                    # Пробуем найти и удалить из БД, если он там есть
                    vpn_key_result = await session.execute(
                        select(VPNKey).where(VPNKey.xui_client_id == client_id)
                    )
                    vpn_key = vpn_key_result.scalar_one_or_none()
                    
                    if vpn_key:
                        await session.delete(vpn_key)
                        await session.commit()
                        logger.info("✅ Also removed from database", key_id=vpn_key.id)
                        message = "Ключ удален из X3UI панели и базы данных"
                    else:
                        logger.info("ℹ️ Key was only in X3UI panel (ghost key)")
                        message = "Призрачный ключ удален из X3UI панели"
                    
                    await x3ui_client.close()
                    return {
                        "success": True,
                        "message": message,
                        "client_id": client_id,
                        "node": {"id": node.id, "name": node.name}
                    }
                else:
                    await x3ui_client.close()
                    return {
                        "success": False,
                        "error": f"Не удалось удалить клиента {client_id} из X3UI панели"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Не удалось подключиться к X3UI панели ноды {node.name}"
                }
                
        except Exception as e:
            logger.error("💥 Error during direct X3UI deletion",
                        client_id=client_id,
                        error=str(e))
            return {
                "success": False,
                "error": f"Ошибка при удалении из X3UI: {str(e)}"
            }
            
    except Exception as e:
        logger.error("💥 Critical error in direct X3UI deletion endpoint", 
                    client_id=client_id, 
                    error=str(e))
        return {
            "success": False,
            "error": f"Критическая ошибка: {str(e)}"
        }

@router.post("/update-user-data")
async def update_user_data_endpoint(request: UpdateUserDataRequest):
    """Обновление данных пользователя (username, first_name, last_name)"""
    
    try:
        # Получаем пользователя
        dashboard_result = await integration_service.get_user_dashboard(request.telegram_id)
        
        if not dashboard_result["success"]:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Обновляем данные пользователя
        user_update_result = await integration_service.update_user_data(
            telegram_id=request.telegram_id,
            username=request.username,
            first_name=request.first_name,
            last_name=request.last_name
        )
        
        if not user_update_result["success"]:
            raise HTTPException(status_code=400, detail=user_update_result["message"])
        
        return user_update_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления данных пользователя: {str(e)}")

@router.post("/test/reality-keys")
async def test_reality_keys():
    """Тестирование генерации Reality ключей"""
    try:
        # Создаем тестовый config
        config = NodeDeploymentConfig(
            ssh_host="test",
            ssh_password="test",
            name="Test Node"
        )
        
        # Тестируем fallback метод
        public_key, private_key = config._generate_fallback_keys()
        
        # Тестируем новый RealityKeyGenerator
        xray_test = None
        try:
            from services.reality_key_generator import RealityKeyGenerator
            
            # Генерируем ключи через новый генератор
            generator_keys = RealityKeyGenerator.generate_keys()
            
            xray_test = {
                "available": True,
                "method": generator_keys.generation_method,
                "public_key": generator_keys.public_key[:20] + "...",
                "private_key": generator_keys.private_key[:20] + "...",
                "validation": RealityKeyGenerator.validate_keys(
                    generator_keys.private_key, 
                    generator_keys.public_key
                )
            }
        except Exception as e:
            xray_test = {"available": False, "error": str(e)}
        
        # Проверим валидность ключей
        key_validation = {
            "public_key_valid": public_key is not None and len(public_key) > 0,
            "private_key_valid": private_key is not None and len(private_key) > 0,
            "public_key_length": len(public_key) if public_key else 0,
            "private_key_length": len(private_key) if private_key else 0
        }
        
        # Попробуем декодировать base64 ключи
        try:
            if public_key:
                decoded_public = base64.b64decode(public_key)
                key_validation["public_key_decoded_length"] = len(decoded_public)
                key_validation["public_key_is_32_bytes"] = len(decoded_public) == 32
                
            if private_key:
                decoded_private = base64.b64decode(private_key)
                key_validation["private_key_decoded_length"] = len(decoded_private)
                key_validation["private_key_is_32_bytes"] = len(decoded_private) == 32
        except Exception as e:
            key_validation["decode_error"] = str(e)
        
        return {
            "success": True,
            "keys": {
                "public_key": public_key,
                "private_key": private_key,
            },
            "xray_test": xray_test,
            "validation": key_validation,
            "message": "Reality keys test completed"
        }
    except Exception as e:
        logger.error("Error testing reality keys", error=str(e))
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/test/update-reality-keys/{node_id}")
async def update_reality_keys(node_id: int, session: AsyncSession = Depends(get_db)):
    """Обновление Reality ключей для существующей ноды"""
    try:
        from models.vpn_node import VPNNode
        from sqlalchemy import select, update
        
        # Находим ноду
        result = await session.execute(select(VPNNode).where(VPNNode.id == node_id))
        node = result.scalar_one_or_none()
        
        if not node:
            return {"success": False, "error": f"Нода с ID {node_id} не найдена"}
        
        # Генерируем новые Reality ключи
        config = NodeDeploymentConfig(ssh_host="test", ssh_password="test", name="Test")
        new_public_key, new_private_key = config._generate_fallback_keys()
        
        if not new_public_key or not new_private_key:
            return {"success": False, "error": "Не удалось сгенерировать Reality ключи"}
        
        # Обновляем ноду в БД
        await session.execute(
            update(VPNNode)
            .where(VPNNode.id == node_id)
            .values(public_key=new_public_key)
        )
        await session.commit()
        
        # Проверим валидность
        decoded_public = base64.b64decode(new_public_key)
        decoded_private = base64.b64decode(new_private_key)
        
        return {
            "success": True,
            "node_id": node_id,
            "old_public_key": node.public_key,
            "new_public_key": new_public_key,
            "new_private_key": new_private_key,
            "validation": {
                "public_key_length": len(decoded_public),
                "private_key_length": len(decoded_private),
                "keys_valid": len(decoded_public) == 32 and len(decoded_private) == 32
            },
            "message": "Reality ключи успешно обновлены"
        }
        
    except Exception as e:
        logger.error("Error updating reality keys", error=str(e))
        return {"success": False, "error": str(e)}

@router.delete("/vpn-key/{key_id}")
async def delete_vpn_key(
    key_id: int,
    session: AsyncSession = Depends(get_db)
):
    """
    Удаление VPN ключа по ID с правильной последовательностью:
    1. Удаление из X3UI панели
    2. Удаление из базы данных
    """
    try:
        logger.info("🗑️ Deleting VPN key", key_id=key_id)
        
        # 1. Получаем ключ из базы данных
        from models.vpn_key import VPNKey
        
        key_result = await session.execute(
            select(VPNKey).where(VPNKey.id == key_id)
        )
        vpn_key = key_result.scalar_one_or_none()
        
        if not vpn_key:
            return {
                "success": False,
                "error": f"VPN ключ с ID {key_id} не найден"
            }
        
        # 2. Получаем данные ноды
        from models.vpn_node import VPNNode
        
        node_result = await session.execute(
            select(VPNNode).where(VPNNode.id == vpn_key.node_id)
        )
        node = node_result.scalar_one_or_none()
        
        if not node:
            return {
                "success": False,
                "error": f"Нода не найдена для ключа {key_id}"
            }
        
        # 3. Подключаемся к X3UI панели и удаляем ключ
        deletion_from_x3ui_successful = False
        
        if vpn_key.xui_client_id and vpn_key.xui_inbound_id:
            try:
                from services.x3ui_client import X3UIClient
                
                x3ui_client = X3UIClient(
                    base_url=node.x3ui_url,
                    username=node.x3ui_username,
                    password=node.x3ui_password
                )
                
                if await x3ui_client._login():
                    logger.info("✅ Connected to X3UI panel for deletion", 
                               key_id=key_id,
                               node_id=node.id,
                               client_id=vpn_key.xui_client_id)
                    
                    # Удаляем клиента из X3UI панели
                    delete_result = await x3ui_client.delete_client(
                        vpn_key.xui_inbound_id, 
                        vpn_key.xui_client_id
                    )
                    
                    if delete_result:
                        deletion_from_x3ui_successful = True
                        logger.info("✅ VPN key successfully deleted from X3UI panel", 
                                   key_id=key_id,
                                   client_id=vpn_key.xui_client_id,
                                   node_id=node.id)
                    else:
                        logger.error("❌ Failed to delete VPN key from X3UI panel", 
                                    key_id=key_id,
                                    client_id=vpn_key.xui_client_id,
                                    node_id=node.id)
                    
                    await x3ui_client.close()
                else:
                    logger.error("❌ Failed to login to X3UI panel", 
                                node_id=node.id,
                                key_id=key_id)
            except Exception as e:
                logger.error("💥 Exception while deleting from X3UI panel", 
                            key_id=key_id,
                            error=str(e))
        else:
            # Если нет данных X3UI, считаем что удаление прошло успешно
            deletion_from_x3ui_successful = True
            logger.info("ℹ️ No X3UI data for key, proceeding with database deletion", 
                       key_id=key_id)
        
        # 4. Удаляем из базы данных ТОЛЬКО если успешно удалили из X3UI панели
        if deletion_from_x3ui_successful:
            await session.delete(vpn_key)
            await session.commit()
            
            logger.info("✅ VPN key successfully deleted from database", 
                       key_id=key_id)
            
            return {
                "success": True,
                "message": f"VPN ключ {key_id} успешно удален из X3UI панели и базы данных"
            }
        else:
            return {
                "success": False,
                "error": f"Не удалось удалить ключ {key_id} из X3UI панели. Ключ остается в базе данных."
            }
            
    except Exception as e:
        logger.error("💥 Error deleting VPN key", 
                    key_id=key_id,
                    error=str(e))
        return {
            "success": False,
            "error": f"Внутренняя ошибка при удалении ключа: {str(e)}"
        }

# Временный debug endpoint удален 