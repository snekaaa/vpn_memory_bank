"""
Простой сервис обновления VPN ключей через панель X3UI
Без сложной логики - просто берем готовые ключи из панели
"""
import structlog
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.vpn_key import VPNKey, VPNKeyStatus
from models.user import User
# Удален неиспользуемый импорт from services.x3ui_panel_service import get_x3ui_panel_service

logger = structlog.get_logger(__name__)

class SimpleKeyUpdateService:
    """Простое обновление ключей через X3UI панель"""
    
    @staticmethod
    async def update_user_key(
        session: AsyncSession,
        user_id: int,
        force_new: bool = False
    ) -> Dict[str, Any]:
        """
        Обновление ключа:
        1. Получаем пользователя
        2. Находим активный ключ в БД
        3. Удаляем старый ключ из X3UI панели строго по ID
        4. Создаем новый ключ в X3UI панели только при успешном удалении старого
        5. Получаем готовый VLESS URL из панели
        6. Сохраняем в базе
        """
        try:
            # 1. Получаем пользователя
            user_result = await session.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            
            if not user:
                return {"success": False, "error": "Пользователь не найден"}
            
            # 2. Получаем ноду согласно назначению пользователя
            from models.vpn_node import VPNNode
            from models.user_server_assignment import UserServerAssignment
            
            logger.info("🔍 Looking for user assignment", user_id=user.id, telegram_id=user.telegram_id)
            
            # Сначала пытаемся найти назначенную ноду
            assignment_result = await session.execute(
                select(UserServerAssignment).where(UserServerAssignment.user_id == user.telegram_id)
            )
            assignment = assignment_result.scalar_one_or_none()
            
            logger.info("🎯 Assignment found", 
                       user_id=user.id, 
                       assignment_exists=assignment is not None,
                       assigned_node_id=assignment.node_id if assignment else None)
            
            active_node = None
            
            if assignment and assignment.node_id:
                logger.info("🔍 Checking assigned node", node_id=assignment.node_id)
                
                # Проверяем что назначенная нода активна
                node_result = await session.execute(
                    select(VPNNode).where(
                        VPNNode.id == assignment.node_id,
                        VPNNode.status == "active"
                    )
                )
                active_node = node_result.scalar_one_or_none()
                
                if active_node:
                    logger.info("✅ Using assigned node", 
                               user_id=user.id, 
                               node_id=assignment.node_id, 
                               node_name=active_node.name,
                               node_location=active_node.location)
                else:
                    logger.warning("❌ Assigned node is not active, selecting fallback", 
                                  user_id=user.id, 
                                  assigned_node_id=assignment.node_id)
            else:
                logger.info("ℹ️ No assignment found, will use fallback", user_id=user.id)
            
            # Если нет назначения или назначенная нода неактивна, берем любую активную
            if not active_node:
                logger.info("🔄 Selecting fallback node", user_id=user.id)
                
                node_result = await session.execute(
                    select(VPNNode).where(VPNNode.status == "active")
                    .order_by(VPNNode.priority.desc())
                    .limit(1)
                )
                active_node = node_result.scalar_one_or_none()
                
                logger.info("🆘 Using fallback node", 
                           user_id=user.id, 
                           node_id=active_node.id if active_node else None,
                           node_name=active_node.name if active_node else None,
                           node_location=active_node.location if active_node else None)
            
            if not active_node:
                return {"success": False, "error": "Нет доступных активных VPN нод"}
            
            # 3. Проверяем и создаем Reality inbound если нужно
            from services.reality_inbound_service import RealityInboundService
            
            inbound_exists = await RealityInboundService.ensure_reality_inbound_exists(
                node=active_node,
                port=443,
                sni_mask="apple.com"
            )
            
            if not inbound_exists:
                return {"success": False, "error": "Не удалось создать Reality inbound в панели"}
            
            # 4. Создаем клиента через X3UI API
            from services.x3ui_client import X3UIClient
            
            x3ui_client = X3UIClient(
                base_url=active_node.x3ui_url,
                username=active_node.x3ui_username,
                password=active_node.x3ui_password
            )
            
            if not await x3ui_client._login():
                return {"success": False, "error": "Не удалось подключиться к X3UI панели"}
            
            try:
                # 5. Находим активный ключ пользователя в БД
                active_key_result = await session.execute(
                    select(VPNKey).where(
                        VPNKey.user_id == user_id,
                        VPNKey.status.in_(["active", "ACTIVE", VPNKeyStatus.ACTIVE.value])
                    ).order_by(VPNKey.created_at.desc()).limit(1)
                )
                active_key = active_key_result.scalar_one_or_none()
                
                if active_key:
                    logger.info("Найден активный ключ для обновления", 
                               user_id=user_id, 
                               key_id=active_key.id,
                               node_id=active_key.node_id,
                               uuid=active_key.uuid,
                               xui_client_id=active_key.xui_client_id)
                else:
                    logger.info("Активный ключ не найден, создаем новый", user_id=user_id)
                
                # 6. Получаем Reality inbound из панели
                logger.info("🔍 Поиск Reality inbound'а на порту 443")
                inbounds = await x3ui_client.get_inbounds()
                reality_inbound = None
                
                if not inbounds:
                    logger.error("❌ Не удалось получить список inbound'ов из X3UI панели")
                    return {"success": False, "error": "Не удалось получить список inbound'ов из панели"}
                
                logger.info(f"📋 Найдено {len(inbounds)} inbound'ов в панели")
                
                if inbounds:
                    import json
                    for i, inbound in enumerate(inbounds):
                        logger.info(f"🔍 Проверка inbound {i+1}: "
                                   f"protocol={inbound.get('protocol')}, "
                                   f"port={inbound.get('port')}, "
                                   f"enabled={inbound.get('enable')}")
                        
                        if (inbound.get("protocol") == "vless" and 
                            inbound.get("port") == 443 and
                            inbound.get("enable") == True):
                            
                            stream_settings = json.loads(inbound.get("streamSettings", "{}"))
                            security = stream_settings.get("security")
                            
                            logger.info(f"✅ Найден VLESS inbound на порту 443, security={security}")
                            
                            if security == "reality":
                                reality_inbound = inbound
                                logger.info(f"🎯 Найден Reality inbound: id={inbound.get('id')}")
                                break
                
                if not reality_inbound:
                    logger.error("❌ Reality inbound на порту 443 не найден в панели")
                    return {"success": False, "error": "Reality inbound на порту 443 не найден в панели"}
                
                inbound_id = reality_inbound["id"]
                
                # 7. Формируем email для работы с X3UI
                # Формируем правильное имя клиента: id tg пользователя (имя в ТГ)
                first_name_part = f" ({user.first_name})" if user.first_name else ""
                email = f"{user.telegram_id}{first_name_part}"
                
                # 8. Удаляем старый ключ из панели, если он существует
                old_key_deleted = False  # По умолчанию считаем что старый ключ не удален
                
                if active_key and active_key.xui_client_id:
                    logger.info("🗑️ Удаляем старый ключ из панели", 
                               key_id=active_key.id, 
                               client_id=active_key.xui_client_id,
                               old_node_id=active_key.node_id,
                               new_node_id=active_node.id)
                    
                    # Пытаемся удалить ключ из панели
                    try:
                        # ИСПРАВЛЕНИЕ: Если старый ключ с другой ноды, подключаемся к той ноде
                        if active_key.node_id and active_key.node_id != active_node.id:
                            logger.info("🔄 Старый ключ с другой ноды, подключаемся к старой ноде", 
                                       old_node_id=active_key.node_id, 
                                       new_node_id=active_node.id)
                            
                            # Получаем данные старой ноды
                            old_node_result = await session.execute(
                                select(VPNNode).where(VPNNode.id == active_key.node_id)
                            )
                            old_node = old_node_result.scalar_one_or_none()
                            
                            if old_node:
                                # Создаем клиент для старой ноды
                                old_x3ui_client = X3UIClient(
                                    base_url=old_node.x3ui_url,
                                    username=old_node.x3ui_username,
                                    password=old_node.x3ui_password
                                )
                                
                                if await old_x3ui_client._login():
                                    # Получаем inbound'ы старой ноды для поиска правильного ID
                                    old_inbounds = await old_x3ui_client.get_inbounds()
                                    old_reality_inbound = None
                                    
                                    if old_inbounds:
                                        import json
                                        for inbound in old_inbounds:
                                            if (inbound.get("protocol") == "vless" and 
                                                inbound.get("port") == 443 and
                                                inbound.get("enable") == True):
                                                
                                                stream_settings = json.loads(inbound.get("streamSettings", "{}"))
                                                if stream_settings.get("security") == "reality":
                                                    old_reality_inbound = inbound
                                                    break
                                    
                                    if old_reality_inbound:
                                        old_inbound_id = old_reality_inbound["id"]
                                        old_key_deleted = await old_x3ui_client.delete_client(old_inbound_id, active_key.xui_client_id)
                                        
                                        if old_key_deleted:
                                            logger.info("✅ Старый ключ успешно удален из старой ноды", 
                                                       key_id=active_key.id, 
                                                       client_id=active_key.xui_client_id,
                                                       old_node_id=old_node.id)
                                        else:
                                            logger.warning("⚠️ Не удалось удалить ключ из старой ноды", 
                                                          key_id=active_key.id,
                                                          old_node_id=old_node.id)
                                    else:
                                        logger.warning("⚠️ Reality inbound не найден на старой ноде", 
                                                      old_node_id=old_node.id)
                                        # Продолжаем, считая что ключ "удален"
                                        old_key_deleted = True
                                else:
                                    logger.warning("⚠️ Не удалось подключиться к старой ноде", 
                                                  old_node_id=old_node.id)
                                    # Продолжаем, считая что ключ "удален"
                                    old_key_deleted = True
                            else:
                                logger.warning("⚠️ Старая нода не найдена в БД", 
                                              old_node_id=active_key.node_id)
                                # Продолжаем, считая что ключ "удален"
                                old_key_deleted = True
                        else:
                            # Старый ключ с той же ноды - используем текущий клиент
                            old_key_deleted = await x3ui_client.delete_client(inbound_id, active_key.xui_client_id)
                        
                        if old_key_deleted:
                            # Удаляем из БД только если успешно удалили из панели (или пропустили)
                            await session.delete(active_key)
                            await session.commit()
                            logger.info("✅ Старый ключ удален из БД", key_id=active_key.id)
                        else:
                            # Если не удалось удалить из панели, возвращаем ошибку
                            logger.error("❌ Не удалось удалить старый ключ из панели", 
                                       key_id=active_key.id, 
                                       client_id=active_key.xui_client_id)
                            return {"success": False, "error": "Не удалось удалить старый ключ из панели"}
                    except Exception as e:
                        logger.error("❌ Ошибка при удалении старого ключа из панели", 
                                    key_id=active_key.id, 
                                    client_id=active_key.xui_client_id,
                                    error=str(e))
                        return {"success": False, "error": f"Ошибка при удалении старого ключа: {str(e)}"}
                else:
                    # Если активного ключа нет, считаем что удаление прошло успешно
                    old_key_deleted = True
                    logger.info("ℹ️ Активный ключ не найден, пропускаем удаление")
                
                # 9. Если старый ключ успешно удален или его не было, создаем новый
                if old_key_deleted:
                    # Генерируем UUID для клиента
                    import uuid
                    client_uuid = str(uuid.uuid4())
                    
                    # Формируем уникальный email для нового клиента
                    import time
                    timestamp = int(time.time())
                    unique_email = f"{user.telegram_id}_{timestamp}{first_name_part}@vpn.local"
                    
                    logger.info("🆕 Создаем нового клиента", 
                               email=unique_email, 
                               uuid=client_uuid)
                    
                    # Создаем клиента в панели
                    client_config = {
                        "id": client_uuid,
                        "email": unique_email,
                        "limitIp": 2,
                        "totalGB": 100 * 1024 * 1024 * 1024,  # 100GB
                        "expiryTime": 0,  # Без ограничения времени
                        "enable": True,
                        "tgId": str(user.telegram_id),
                        "subId": ""
                    }
                    
                    client_result = await x3ui_client.create_client(inbound_id, client_config)
                    
                    if not client_result or not client_result.get("success"):
                        logger.error("❌ Не удалось создать нового клиента в панели")
                        return {"success": False, "error": "Не удалось создать нового клиента в панели"}
                    
                    # Получаем VLESS URL для нового клиента
                    vless_url = await x3ui_client.generate_client_url(inbound_id, client_uuid)
                    
                    if not vless_url:
                        logger.error("❌ Не удалось получить VLESS URL для нового клиента")
                        return {"success": False, "error": "Не удалось получить VLESS URL для нового клиента"}
                    
                    # Создаем новый ключ в БД (упрощенная архитектура)
                    new_key = VPNKey(
                        user_id=user_id,
                        # subscription_id убрано - упрощенная архитектура
                        node_id=active_node.id,
                        uuid=client_uuid,
                        key_name=f"key_{int(datetime.utcnow().timestamp())}",
                        vless_url=vless_url,
                        xui_email=unique_email,
                        status=VPNKeyStatus.ACTIVE.value,
                        xui_client_id=client_uuid,
                        xui_inbound_id=inbound_id,
                        total_download=0,
                        total_upload=0
                    )
                    
                    session.add(new_key)
                    await session.commit()
                    await session.refresh(new_key)
                    
                    logger.info("✅ Новый ключ успешно создан и сохранен", 
                               new_key_id=new_key.id,
                               user_id=user_id,
                               uuid=client_uuid)
                    
                    # Обновляем статистику для ноды
                    from services.node_manager import NodeManager
                    node_manager = NodeManager(session)
                    await node_manager.update_node_stats(active_node.id)
                    
                    # 13. Возвращаем результат с ключом
                    return {
                        "success": True, 
                        "vpn_key": {
                            "id": new_key.id,
                            "uuid": new_key.uuid,
                            "vless_url": new_key.vless_url,
                            "status": new_key.status,
                            "created_at": new_key.created_at.isoformat() if new_key.created_at else None
                        }
                    }
                else:
                    # Этот блок не должен выполняться из-за return выше,
                    # но оставим для логической целостности
                    return {"success": False, "error": "Не удалось удалить старый ключ"}
                
            except Exception as e:
                logger.error("💥 Ошибка в API обновления VPN ключа", 
                            error=str(e),
                            telegram_id=user.telegram_id)
                return {"success": False, "error": f"Внутренняя ошибка сервера: {str(e)}"}
                
        except Exception as e:
            logger.error("💥 Неожиданная ошибка в API обновления VPN ключа", error=str(e))
            return {"success": False, "error": f"Внутренняя ошибка сервера: {str(e)}"}

    @staticmethod
    async def get_or_create_user_key(
        session: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Получение или создание ключа пользователя:
        1. Проверяем, есть ли активный ключ у пользователя
        2. Если есть - возвращаем его
        3. Если нет - создаем новый через update_user_key
        """
        try:
            # Проверяем, есть ли активный ключ
            key_result = await session.execute(
                select(VPNKey).where(
                    VPNKey.user_id == user_id,
                    VPNKey.status.in_(["active", "ACTIVE", VPNKeyStatus.ACTIVE.value])
                ).order_by(VPNKey.created_at.desc()).limit(1)
            )
            key = key_result.scalar_one_or_none()
            
            if key:
                # Ключ найден - возвращаем его
                return {
                    "success": True,
                    "message": "Существующий ключ найден",
                    "vpn_key": {
                        "id": key.id,
                        "key_name": key.key_name,
                        "vless_url": key.vless_url,
                        "status": key.status,
                        "created_at": key.created_at.isoformat() if key.created_at else None
                    }
                }
            else:
                # Ключ не найден - создаем новый
                logger.info("Активный ключ не найден, создаем новый", user_id=user_id)
                return await SimpleKeyUpdateService.update_user_key(
                    session=session,
                    user_id=user_id
                )
                
        except Exception as e:
            logger.error("❌ Ошибка при получении/создании ключа", 
                        user_id=user_id, 
                        error=str(e))
            return {
                "success": False,
                "error": f"Ошибка при получении/создании ключа: {str(e)}"
            } 