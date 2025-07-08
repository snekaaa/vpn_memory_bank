"""
End-to-End Integration Service
Координирует взаимодействие между Bot, Backend API и X3UI
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.database import get_db_session
from models.user import User
from models.subscription import Subscription
from models.payment import Payment
from models.vpn_key import VPNKey
from services.x3ui_client import x3ui_client

logger = structlog.get_logger(__name__)

class IntegrationService:
    """Сервис для End-to-End интеграции всех компонентов"""
    
    def __init__(self):
        self.x3ui = x3ui_client
        
    async def create_user_with_subscription(
        self, 
        telegram_id: int, 
        user_data: Dict[str, Any],
        subscription_type: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Полный цикл создания пользователя с подпиской
        Bot -> Backend -> Database
        """
        logger.info("Starting user creation cycle", telegram_id=telegram_id)
        
        try:
            async with get_db_session() as session:
                # 1. Проверяем существование пользователя
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    logger.info("User already exists", telegram_id=telegram_id)
                    return {
                        "success": True,
                        "user_id": existing_user.id,
                        "message": "Пользователь уже зарегистрирован",
                        "user": {
                            "id": existing_user.id,
                            "telegram_id": existing_user.telegram_id,
                            "username": existing_user.username
                        }
                    }
                
                # 2. Создаем нового пользователя с триальным периодом
                from models.user import UserSubscriptionStatus
                from datetime import datetime, timezone, timedelta
                from services.trial_automation_service import TrialAutomationService
                
                new_user = User(
                    telegram_id=telegram_id,
                    username=user_data.get("username"),
                    first_name=user_data.get("first_name"),
                    last_name=user_data.get("last_name"),
                    language_code=user_data.get("language_code", "ru"),
                    is_active=True,
                    is_blocked=False,
                    subscription_status=UserSubscriptionStatus.active,  # Устанавливаем активную подписку
                    valid_until=datetime.now(timezone.utc) + timedelta(days=7)  # 7 дней триала по умолчанию
                )
                
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                
                # 3. Создаем автоматический триальный платеж
                from services.payment_management_service import get_payment_management_service
                from services.trial_automation_service import get_trial_automation_service
                
                payment_service = get_payment_management_service(session)
                trial_service = await get_trial_automation_service(payment_service)
                trial_payment = await trial_service.create_trial_for_new_user(new_user, session)
                
                logger.info("User created successfully", 
                           user_id=new_user.id, 
                           telegram_id=telegram_id,
                           trial_payment_id=trial_payment.id if trial_payment else None)
                
                return {
                    "success": True,
                    "user_id": new_user.id,
                    "message": "Пользователь успешно зарегистрирован",
                    "user": {
                        "id": new_user.id,
                        "telegram_id": new_user.telegram_id,
                        "username": new_user.username,
                        "created_at": new_user.created_at.isoformat() if new_user.created_at else None
                    },
                    "trial_payment": {
                        "id": trial_payment.id,
                        "amount": trial_payment.amount,
                        "status": trial_payment.status.value,
                        "description": trial_payment.description
                    } if trial_payment else None
                }
                
        except Exception as e:
            logger.error("Error creating user", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "message": "Ошибка при создании пользователя"
            }
    
    async def create_subscription_with_payment(
        self,
        user_id: int,
        subscription_type: str = "monthly",
        payment_method: str = "yookassa"
    ) -> Dict[str, Any]:
        """
        Создание подписки с имитацией платежа
        Backend -> Database -> Payment simulation
        """
        logger.info("Creating subscription with payment", 
                   user_id=user_id, 
                   subscription_type=subscription_type)
        
        try:
            async with get_db_session() as session:
                # Проверяем пользователя
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                
                if not user:
                    return {
                        "success": False,
                        "error": "User not found",
                        "message": "Пользователь не найден"
                    }
                
                # Определяем параметры подписки
                subscription_params = self._get_subscription_params(subscription_type)
                
                # 1. Создаем подписку
                from models.subscription import SubscriptionType, SubscriptionStatus
                
                # Определяем subscription_type enum
                subscription_type_enum = SubscriptionType.MONTHLY
                if subscription_type == "monthly":
                    subscription_type_enum = SubscriptionType.MONTHLY
                elif subscription_type == "quarterly":
                    subscription_type_enum = SubscriptionType.QUARTERLY
                elif subscription_type == "semi_annual":
                    subscription_type_enum = SubscriptionType.SEMI_ANNUAL
                elif subscription_type == "yearly":
                    subscription_type_enum = SubscriptionType.YEARLY
                elif subscription_type == "trial":
                    subscription_type_enum = SubscriptionType.TRIAL
                
                subscription = Subscription(
                    user_id=user_id,
                    subscription_type=subscription_type_enum,  # Используем enum
                    price=subscription_params["price"],
                    currency="RUB",
                    start_date=datetime.utcnow(),
                    end_date=datetime.utcnow() + timedelta(days=subscription_params["days"]),
                    status=SubscriptionStatus.ACTIVE,  # Используем enum
                    auto_renewal=False
                )
                
                session.add(subscription)
                await session.commit()
                await session.refresh(subscription)
                
                # 2. Создаем платеж (имитация)
                from models.payment import PaymentStatus, PaymentMethod
                
                # Определяем payment_method enum
                payment_method_enum = PaymentMethod.YOOKASSA_CARD
                if payment_method == "yookassa":
                    payment_method_enum = PaymentMethod.YOOKASSA_CARD
                elif payment_method == "sbp":
                    payment_method_enum = PaymentMethod.YOOKASSA_SBP
                elif payment_method == "crypto":
                    payment_method_enum = PaymentMethod.COINGATE_CRYPTO
                    
                payment = Payment(
                    user_id=user_id,
                    subscription_id=subscription.id,
                    amount=subscription_params["price"],
                    currency="RUB",
                    status=PaymentStatus.SUCCEEDED,  # Используем правильный enum
                    payment_method=payment_method_enum,  # Используем enum
                    external_id=f"integration_payment_{int(datetime.utcnow().timestamp())}",
                    description=f"Подписка {subscription_type}",
                    paid_at=datetime.utcnow(),
                    processed_at=datetime.utcnow()
                )
                
                session.add(payment)
                await session.commit()
                await session.refresh(payment)
                
                logger.info("Subscription and payment created", 
                           subscription_id=subscription.id,
                           payment_id=payment.id)
                
                return {
                    "success": True,
                    "subscription_id": subscription.id,
                    "payment_id": payment.id,
                    "message": "Подписка успешно создана",
                    "subscription": {
                        "id": subscription.id,
                        "type": subscription.subscription_type,
                        "price": float(subscription.price),
                        "end_date": subscription.end_date.isoformat()
                    },
                    "payment": {
                        "id": payment.id,
                        "amount": payment.amount,
                        "status": payment.status,
                        "method": payment.payment_method
                    }
                }
                
        except Exception as e:
            logger.error("Error creating subscription with payment", 
                        user_id=user_id, 
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "message": "Ошибка при создании подписки"
            }
    
    async def create_vpn_key_full_cycle(
        self,
        user_id: int,
        key_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Полный цикл создания VPN ключа (упрощенная архитектура без подписок)
        Backend -> X3UI -> Database -> User
        """
        logger.info("Starting VPN key creation full cycle", 
                   user_id=user_id)
        
        try:
            async with get_db_session() as session:
                # Проверяем пользователя
                user_result = await session.execute(select(User).where(User.id == user_id))
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return {
                        "success": False,
                        "error": "User not found",
                        "message": "Пользователь не найден"
                    }
                
                # Проверяем, что у пользователя есть активная подписка
                if not user.has_active_subscription:
                    return {
                        "success": False,
                        "error": "User has no active subscription",
                        "message": "У пользователя нет активной подписки"
                    }
                
                # Генерируем имя ключа
                if not key_name:
                    key_name = f"vpn_key_user_{user.telegram_id}_{int(datetime.utcnow().timestamp())}"
                
                # 1. Создаем клиента в X3UI
                x3ui_config = {
                    "telegram_id": user.telegram_id,
                    "username": user.username or "",
                    "total_gb": 100 * 1024 * 1024 * 1024,  # 100GB
                    "expiry_days": 30
                }
                
                # Попытка интеграции с существующим пользователем в X3UI
                import sys
                import os
                
                # Добавляем bot директорию в Python path
                bot_path = os.path.join(os.path.dirname(__file__), '..', '..', 'bot')
                if bot_path not in sys.path:
                    sys.path.insert(0, bot_path)
                
                # ПРАВИЛЬНЫЙ ПОДХОД: Создаем VPN ключ через X3UI Reality inbound
                return await self._create_vpn_key_with_reality_inbound(
                    session=session,
                    user_id=user_id,
                    key_name=key_name,
                    user=user
                )
                
        except Exception as e:
            logger.error("Error in VPN key creation full cycle", 
                        user_id=user_id, 
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "message": "Ошибка при создании VPN ключа"
            }
    
    async def get_user_dashboard(self, telegram_id: int) -> Dict[str, Any]:
        """
        Получение полной информации о пользователе для Dashboard
        """
        logger.info("Getting user dashboard", telegram_id=telegram_id)
        
        try:
            async with get_db_session() as session:
                # Получаем пользователя
                user_result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return {
                        "success": False,
                        "error": "User not found",
                        "message": "Пользователь не найден"
                    }
                
                # Упрощенная архитектура - данные подписки берем из user
                from models.vpn_key import VPNKeyStatus
                
                # Получаем VPN ключи (сортируем по ID в убывающем порядке - новые первыми)
                vpn_keys_result = await session.execute(
                    select(VPNKey).where(
                        VPNKey.user_id == user.id,
                        VPNKey.status == VPNKeyStatus.ACTIVE.value
                    ).order_by(VPNKey.id.desc())
                )
                vpn_keys = vpn_keys_result.scalars().all()
                
                # Получаем последние платежи
                payments_result = await session.execute(
                    select(Payment).where(Payment.user_id == user.id)
                    .order_by(Payment.created_at.desc())
                    .limit(5)
                )
                payments = payments_result.scalars().all()
                
                return {
                    "success": True,
                    "user": {
                        "id": user.id,
                        "telegram_id": user.telegram_id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "is_active": user.is_active,
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                        # Упрощенная архитектура - показываем данные подписки из user
                        "subscription_status": user.subscription_status.value if user.subscription_status else "none",
                        "valid_until": user.valid_until.isoformat() if user.valid_until else None,
                        "has_active_subscription": user.has_active_subscription,
                        "days_remaining": user.subscription_days_remaining
                    },
                    "vpn_keys": [
                        {
                            "id": key.id,
                            "key_name": key.key_name,
                            "status": key.status,
                            "vless_url": key.vless_url  # Используем правильное поле
                        } for key in vpn_keys
                    ],
                    "payments": [
                        {
                            "id": payment.id,
                            "amount": payment.amount,
                            "status": payment.status,
                            "created_at": payment.created_at.isoformat() if payment.created_at else None
                        } for payment in payments
                    ],
                    "stats": {
                        "active_vpn_keys": len(vpn_keys),
                        "total_payments": len(payments),
                        "account_status": "active" if user.has_active_subscription else "expired"
                    }
                }
                
        except Exception as e:
            logger.error("Error getting user dashboard", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "message": "Ошибка при получении данных пользователя"
            }
    
    def _get_subscription_params(self, subscription_type: str) -> Dict[str, Any]:
        """Получить параметры подписки по типу"""
        
        params = {
            "trial": {
                "type": "trial",
                "price": 0.0,
                "days": 30
            },
            "monthly": {
                "type": "monthly",
                "price": 199.0,
                "days": 30
            },
            "quarterly": {
                "type": "quarterly", 
                "price": 499.0,
                "days": 90
            },
            "semi_annual": {
                "type": "semi_annual",
                "price": 899.0,
                "days": 180
            },
            "yearly": {
                "type": "yearly",
                "price": 1599.0,
                "days": 365
            }
        }
        
        return params.get(subscription_type, params["monthly"])

    async def update_vpn_key_with_node_migration(
        self,
        user_id: int,
        key_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обновление VPN ключа с миграцией на лучшую ноду (упрощенная архитектура)
        1. Найти текущий активный ключ пользователя
        2. Выбрать лучшую ноду по приоритету
        3. Создать новый ключ на новой ноде
        4. Удалить старый ключ из старой ноды
        """
        logger.info("Starting VPN key update with node migration", 
                   user_id=user_id)
        
        try:
            async with get_db_session() as session:
                # Проверяем пользователя
                user_result = await session.execute(select(User).where(User.id == user_id))
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return {
                        "success": False,
                        "error": "User not found",
                        "message": "Пользователь не найден"
                    }
                
                # Проверяем активную подписку
                if not user.has_active_subscription:
                    return {
                        "success": False,
                        "error": "User has no active subscription",
                        "message": "У пользователя нет активной подписки"
                    }
                
                # Найти текущий активный ключ пользователя
                from models.vpn_key import VPNKeyStatus
                current_key_result = await session.execute(
                    select(VPNKey).where(
                        VPNKey.user_id == user_id,
                        VPNKey.status == VPNKeyStatus.ACTIVE.value
                    ).order_by(VPNKey.created_at.desc()).limit(1)
                )
                current_key = current_key_result.scalar_one_or_none()
                
                # Выбрать лучшую ноду по приоритету
                from models.vpn_node import VPNNode
                best_node_result = await session.execute(
                    select(VPNNode).where(VPNNode.status == "active")
                    .order_by(VPNNode.priority.desc())
                    .limit(1)
                )
                best_node = best_node_result.scalar_one_or_none()
                
                if not best_node:
                    logger.error("No active nodes available for migration")
                    return {
                        "success": False,
                        "error": "No active nodes available",
                        "message": "Нет доступных активных нод"
                    }
                
                # Генерируем имя нового ключа
                if not key_name:
                    import time
                    unique_suffix = str(int(time.time()))
                    key_name = f"updated_key_{user.telegram_id}_{unique_suffix}"
                
                # Создаем клиента в X3UI на лучшей ноде
                x3ui_config = {
                    "telegram_id": user.telegram_id,
                    "username": user.username or "",
                    "total_gb": 100 * 1024 * 1024 * 1024,  # 100GB
                    "expiry_days": 30
                }
                
                # Инициализируем клиент для лучшей ноды с правильными параметрами
                from .x3ui_client import X3UIClient as BackendX3UIClient
                
                real_x3ui = BackendX3UIClient(
                    base_url=best_node.x3ui_url,
                    username=best_node.x3ui_username,
                    password=best_node.x3ui_password
                )
                
                # При ОБНОВЛЕНИИ всегда создаем НОВЫЙ ключ в X3UI
                # Формируем правильное имя клиента: telegram_id (first_name)
                first_name_part = f" ({user.first_name})" if user.first_name else ""
                existing_email = f"{user.telegram_id}{first_name_part}"
                logger.info("🔄 Creating NEW X3UI client for key UPDATE", email=existing_email)

                x3ui_connected = False  # Инициализируем переменную
                vless_url = None
                xui_client_id = None
                
                # Создаем нового пользователя в X3UI через правильный API
                logger.info("🔄 Creating NEW client during key update", email=existing_email)
                
                # Генерируем UUID для нового клиента
                import uuid
                xui_client_id = str(uuid.uuid4())
                
                # Получаем Reality inbound
                inbounds = await real_x3ui.get_inbounds()
                reality_inbound = None
                
                if inbounds:
                    import json
                    for inbound in inbounds:
                        if (inbound.get("protocol") == "vless" and 
                            inbound.get("port") == 443 and
                            inbound.get("enable") == True):
                            
                            stream_settings = json.loads(inbound.get("streamSettings", "{}"))
                            if stream_settings.get("security") == "reality":
                                reality_inbound = inbound
                                break
                
                if reality_inbound:
                    # Создаем клиента через правильный API
                    import time
                    timestamp = int(time.time())
                    unique_email = f"{user.telegram_id}_{timestamp}{' (' + user.first_name + ')' if user.first_name else ''}@vpn.local"
                    
                    client_config = {
                        "id": xui_client_id,
                        "email": unique_email,
                        "limitIp": 2,
                        "totalGB": 100 * 1024 * 1024 * 1024,  # 100GB
                        "expiryTime": 0,  # Без ограничений
                        "enable": True,
                        "tgId": "",
                        "subId": "",
                        "reset": 0
                    }
                    
                    create_result = await real_x3ui.create_client(reality_inbound["id"], client_config)
                    
                    if create_result:
                        # Генерируем VLESS URL
                        vless_url = await real_x3ui.generate_client_url(reality_inbound["id"], xui_client_id)
                        x3ui_connected = True
                        
                        logger.info("✅ NEW X3UI client created for UPDATE", 
                                   xui_client_id=xui_client_id,
                                   node_id=best_node.id,
                                   telegram_id=user.telegram_id)
                    else:
                        # Fallback к генератору
                        from services.vless_generator import vless_generator
                        
                        node_host = best_node.x3ui_url.split('//')[1].split(':')[0]
                        vless_config = vless_generator.generate_vless_for_node(
                            node_host=node_host,
                            node_port=443,
                            alias=f"VPN-UPDATE-{best_node.name}-{user.telegram_id}"
                        )
                        
                        vless_url = vless_config["vless_url"]
                        x3ui_connected = False
                else:
                    # X3UI недоступен, создаем реальную VLESS конфигурацию через генератор
                    from services.vless_generator import vless_generator
                    
                    # Извлекаем хост из URL ноды 
                    node_host = best_node.x3ui_url.split('//')[1].split(':')[0]
                    
                    # Генерируем реальную VLESS конфигурацию
                    vless_config = vless_generator.generate_vless_for_node(
                        node_host=node_host,
                        node_port=443,
                        alias=f"VPN-UPDATE-{best_node.name}-{user.telegram_id}"
                    )
                    
                    vless_url = vless_config["vless_url"]
                    x3ui_connected = False
                    
                    logger.info("❌ X3UI unavailable, generated NEW VLESS config for UPDATE", 
                               user_id=user_id,
                               node_id=best_node.id,
                               node_host=node_host,
                               new_uuid=xui_client_id)
                
                # Закрываем сессию X3UI клиента
                try:
                    await real_x3ui.close()
                except:
                    pass  # Игнорируем ошибки закрытия
                
                # Создаем новый VPN ключ в базе
                import uuid
                
                # Используем UUID из X3UI если найден, иначе генерируем новый
                if xui_client_id and x3ui_connected:
                    # Используем реальный UUID из X3UI
                    key_uuid = xui_client_id
                    logger.info("🎯 Using real X3UI UUID for database record", uuid=key_uuid)
                else:
                    # Генерируем новый UUID для fallback
                    key_uuid = str(uuid.uuid4())
                    logger.info("🔄 Generated new UUID for fallback", uuid=key_uuid)
                
                # Email для X3UI (используем существующий или создаем новый)
                if x3ui_connected:
                    xui_email = existing_email  # Используем существующий email
                else:
                    # Формируем правильное имя клиента: telegram_id (first_name)
                    first_name_part = f" ({user.first_name})" if user.first_name else ""
                    xui_email = f"{user.telegram_id}{first_name_part}"
                
                new_vpn_key = VPNKey(
                    user_id=user_id,
                    node_id=best_node.id,
                    uuid=key_uuid,
                    key_name=key_name,
                    vless_url=vless_url or f"vless://{key_uuid}@{best_node.x3ui_url.split('//')[1].split(':')[0]}:443",
                    xui_email=xui_email,
                    status=VPNKeyStatus.ACTIVE.value,
                    xui_client_id=xui_client_id or key_uuid,
                    xui_inbound_id=1,
                    total_download=0,
                    total_upload=0
                )
                
                # Сначала получаем все текущие активные ключи для удаления ИЗ ПАНЕЛИ
                old_active_keys_result = await session.execute(
                    select(VPNKey).where(
                        VPNKey.user_id == user_id,
                        VPNKey.status == VPNKeyStatus.ACTIVE.value
                    )
                )
                old_active_keys = old_active_keys_result.scalars().all()
                
                # ПРАВИЛЬНАЯ ЛОГИКА: Удаляем старый ключ ИЗ ПАНЕЛИ перед созданием нового
                # Нельзя создавать новый ключ пока не удалили старый из панели
                old_key_deleted = False
                deletion_error = None
                
                # Проверяем есть ли старый активный ключ для удаления
                if old_active_keys:
                    active_key = old_active_keys[0]  # Берем самый новый активный ключ
                    
                    if active_key and active_key.xui_client_id:
                        logger.info("🗑️ Удаляем старый ключ из панели", 
                                   key_id=active_key.id, 
                                   client_id=active_key.xui_client_id,
                                   node_id=active_key.node_id)
                        
                        try:
                            # Получаем ноду старого ключа
                            old_node_result = await session.execute(
                                select(VPNNode).where(VPNNode.id == active_key.node_id)
                            )
                            old_node = old_node_result.scalar_one_or_none()
                            
                            if old_node:
                                # Создаем клиент для старой ноды
                                old_x3ui = BackendX3UIClient(
                                    base_url=old_node.x3ui_url,
                                    username=old_node.x3ui_username,
                                    password=old_node.x3ui_password
                                )
                                
                                # ИСПРАВЛЕНИЕ: Добавляем таймаут для подключения к панели
                                panel_connected = False
                                try:
                                    panel_connected = await old_x3ui._login()
                                except Exception as login_error:
                                    logger.warning("❌ Не удалось подключиться к X3UI панели старой ноды", 
                                                   node_id=active_key.node_id,
                                                   error=str(login_error))
                                    panel_connected = False
                                
                                if panel_connected:
                                    # Находим Reality inbound в старой ноде
                                    old_inbounds = await old_x3ui.get_inbounds()
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
                                        
                                        # Удаляем клиента из панели по ID
                                        old_key_deleted = await old_x3ui.delete_client(old_inbound_id, active_key.xui_client_id)
                                        
                                        if old_key_deleted:
                                            logger.info("✅ Старый ключ успешно удален из панели", 
                                                       key_id=active_key.id, 
                                                       client_id=active_key.xui_client_id)
                                            
                                            # Удаляем из БД только если успешно удалили из панели
                                            await session.delete(active_key)
                                            logger.info("✅ Старый ключ удален из БД", key_id=active_key.id)
                                        else:
                                            # ИСПРАВЛЕНИЕ: Если не удалось удалить из панели - помечаем как неактивный
                                            logger.warning("⚠️ Не удалось удалить ключ из панели, помечаем как неактивный", 
                                                          key_id=active_key.id, 
                                                          client_id=active_key.xui_client_id,
                                                          node_id=old_node.id)
                                            
                                            # Меняем статус на inactive вместо возврата ошибки
                                            active_key.status = VPNKeyStatus.INACTIVE.value
                                            await session.commit()
                                            old_key_deleted = True  # Считаем "удаление" успешным
                                            
                                            logger.info("✅ Старый ключ помечен как неактивный (панель недоступна)", 
                                                       key_id=active_key.id)
                                    else:
                                        # ИСПРАВЛЕНИЕ: Если Reality inbound не найден - помечаем ключ как неактивный
                                        logger.warning("⚠️ Reality inbound не найден, помечаем ключ как неактивный", 
                                                      node_id=old_node.id,
                                                      key_id=active_key.id)
                                        
                                        # Меняем статус на inactive
                                        active_key.status = VPNKeyStatus.INACTIVE.value
                                        await session.commit()
                                        old_key_deleted = True  # Считаем "удаление" успешным
                                        
                                        logger.info("✅ Старый ключ помечен как неактивный (Reality inbound не найден)", 
                                                   key_id=active_key.id)
                                else:
                                    # ИСПРАВЛЕНИЕ: Если панель недоступна - помечаем старый ключ как неактивный
                                    logger.warning("⚠️ X3UI панель недоступна, помечаем старый ключ как неактивный", 
                                                   node_id=old_node.id,
                                                   key_id=active_key.id)
                                    
                                    # Меняем статус старого ключа на inactive вместо удаления
                                    active_key.status = VPNKeyStatus.INACTIVE.value
                                    await session.commit()
                                    
                                    old_key_deleted = True  # Считаем "удаление" успешным
                                    logger.info("✅ Старый ключ помечен как неактивный из-за недоступности панели", 
                                               key_id=active_key.id)
                                    
                                try:
                                    await old_x3ui.close()
                                except:
                                    pass
                            else:
                                # ИСПРАВЛЕНИЕ: Если старая нода не найдена - помечаем ключ как неактивный
                                logger.warning("⚠️ Старая нода не найдена, помечаем ключ как неактивный", 
                                              node_id=active_key.node_id,
                                              key_id=active_key.id)
                                
                                # Меняем статус на inactive
                                active_key.status = VPNKeyStatus.INACTIVE.value
                                await session.commit()
                                old_key_deleted = True  # Считаем "удаление" успешным
                                
                                logger.info("✅ Старый ключ помечен как неактивный (нода не найдена)", 
                                           key_id=active_key.id)
                        
                        except Exception as e:
                            # ИСПРАВЛЕНИЕ: Если произошла ошибка при удалении - также помечаем как неактивный
                            logger.warning("⚠️ Ошибка при удалении старого ключа, помечаем как неактивный", 
                                          key_id=active_key.id, 
                                          error=str(e))
                            
                            # Меняем статус старого ключа на inactive
                            try:
                                active_key.status = VPNKeyStatus.INACTIVE.value
                                await session.commit()
                                old_key_deleted = True  # Считаем "удаление" успешным
                                logger.info("✅ Старый ключ помечен как неактивный из-за ошибки удаления", 
                                           key_id=active_key.id)
                            except Exception as status_error:
                                deletion_error = f"Ошибка при изменении статуса ключа: {str(status_error)}"
                                logger.error("❌ Не удалось изменить статус старого ключа", 
                                           key_id=active_key.id, 
                                           error=str(status_error))
                    else:
                        # Если старого ключа нет или нет client_id, считаем удаление успешным
                        old_key_deleted = True
                        logger.info("ℹ️ Старый ключ не найден или нет client_id, продолжаем")
                else:
                    # Если активных ключей нет, считаем удаление успешным
                    old_key_deleted = True
                    logger.info("ℹ️ Активные ключи не найдены, создаем новый")
                
                # ИСПРАВЛЕНИЕ: Теперь мы ВСЕГДА продолжаем создание нового ключа
                # Либо старый ключ удален из панели, либо помечен как неактивный
                if not old_key_deleted:
                    logger.error("❌ НЕ УДАЛОСЬ ОБНОВИТЬ КЛЮЧ: критическая ошибка при обработке старого ключа", 
                               deletion_error=deletion_error)
                    return {
                        "success": False,
                        "error": f"Критическая ошибка при обработке старого ключа: {deletion_error}",
                        "message": "Ошибка при обработке старого ключа"
                    }
                
                # Создаем новый ключ ТОЛЬКО после успешного удаления старого
                session.add(new_vpn_key)
                await session.commit()
                await session.refresh(new_vpn_key)
                
                # Обновляем статистику нод (новой и старых)
                from services.node_manager import NodeManager
                node_manager = NodeManager(session)
                await node_manager.update_node_stats(best_node.id)
                
                # Обновляем статистику старых нод
                old_node_ids = set()
                for old_key in old_active_keys:
                    if old_key.node_id and old_key.node_id != best_node.id:
                        old_node_ids.add(old_key.node_id)
                
                for old_node_id in old_node_ids:
                    await node_manager.update_node_stats(old_node_id)
                
                logger.info("VPN key updated with node migration", 
                           new_key_id=new_vpn_key.id,
                           new_node_id=best_node.id,
                           old_key_id=current_key.id if current_key else None)
                
                return {
                    "success": True,
                    "vpn_key_id": new_vpn_key.id,
                    "message": f"VPN ключ обновлен и перемещен на ноду '{best_node.name}'",
                    "vpn_key": {
                        "id": new_vpn_key.id,
                        "key_name": new_vpn_key.key_name,
                        "vless_url": new_vpn_key.vless_url,
                        "status": new_vpn_key.status,
                        "node_info": {
                            "id": best_node.id,
                            "name": best_node.name,
                            "location": best_node.location,
                            "priority": best_node.priority
                        },
                        "x3ui_connected": x3ui_connected,
                        "created_at": new_vpn_key.created_at.isoformat() if new_vpn_key.created_at else None
                    }
                }
                
        except Exception as e:
            logger.error("Error in VPN key update with node migration", 
                        user_id=user_id, 
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "message": "Ошибка при обновлении VPN ключа"
            }

    async def update_user_data(
        self, 
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Обновление данных пользователя"""
        try:
            async with get_db_session() as session:
                # Находим пользователя
                user_result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return {
                        "success": False,
                        "error": "User not found",
                        "message": "Пользователь не найден"
                    }
                
                # Обновляем данные только если они переданы
                updated_fields = []
                
                if username is not None:
                    user.username = username
                    updated_fields.append("username")
                
                if first_name is not None:
                    user.first_name = first_name
                    updated_fields.append("first_name")
                
                if last_name is not None:
                    user.last_name = last_name
                    updated_fields.append("last_name")
                
                if updated_fields:
                    user.updated_at = datetime.utcnow()
                    await session.commit()
                    await session.refresh(user)
                    
                    logger.info("User data updated", 
                               telegram_id=telegram_id,
                               updated_fields=updated_fields)
                
                return {
                    "success": True,
                    "message": f"Данные пользователя обновлены: {', '.join(updated_fields)}",
                    "user": {
                        "id": user.id,
                        "telegram_id": user.telegram_id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "updated_at": user.updated_at.isoformat() if user.updated_at else None
                    }
                }
                
        except Exception as e:
            logger.error("Error updating user data", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "message": "Ошибка при обновлении данных пользователя"
            }

    async def _create_vpn_key_with_reality_inbound(
        self,
        session: AsyncSession,
        user_id: int,
        key_name: str,
        user
    ) -> Dict[str, Any]:
        """
        Правильное создание VPN ключа через Reality inbound:
        1. Найти активную ноду
        2. Проверить наличие Reality inbound'а
        3. Создать Reality inbound если его нет
        4. Создать клиента в Reality inbound'е
        5. Получить VLESS URL из панели
        """
        try:
            # 1. Находим активную ноду
            from models.vpn_node import VPNNode
            node_result = await session.execute(
                select(VPNNode).where(VPNNode.status == "active")
                .order_by(VPNNode.priority.desc())
                .limit(1)
            )
            active_node = node_result.scalar_one_or_none()
            
            if not active_node:
                return {
                    "success": False,
                    "error": "No active VPN nodes available",
                    "message": "Нет доступных активных VPN нод"
                }
            
            logger.info("Found active VPN node", 
                       node_id=active_node.id, 
                       node_name=active_node.name,
                       user_id=user_id)
            
            # 2. Проверяем и создаем Reality inbound если нужно
            from services.reality_inbound_service import RealityInboundService
            
            inbound_exists = await RealityInboundService.ensure_reality_inbound_exists(
                node=active_node,
                port=443,
                sni_mask="apple.com"
            )
            
            if not inbound_exists:
                logger.error("Failed to ensure Reality inbound exists", 
                           node_id=active_node.id,
                           user_id=user_id)
                return {
                    "success": False,
                    "error": "Failed to create Reality inbound",
                    "message": "Не удалось создать Reality inbound в панели"
                }
            
            logger.info("Reality inbound is available", 
                       node_id=active_node.id,
                       user_id=user_id)
            
            # 3. Создаем клиента в X3UI панели
            from services.x3ui_client import X3UIClient
            
            x3ui_client = X3UIClient(
                base_url=active_node.x3ui_url,
                username=active_node.x3ui_username,
                password=active_node.x3ui_password
            )
            
            # Логинимся в панель
            if not await x3ui_client._login():
                logger.error("Failed to login to X3UI panel", 
                           node_id=active_node.id,
                           user_id=user_id)
                return {
                    "success": False,
                    "error": "Failed to connect to X3UI panel",
                    "message": "Не удалось подключиться к X3UI панели"
                }
            
            # 4. Получаем Reality inbound'ы (ищем ИМЕННО на порту 443 для HTTPS маскировки)
            inbounds = await x3ui_client.get_inbounds()
            reality_inbound = None
            
            if inbounds:
                import json
                for inbound in inbounds:
                    if (inbound.get("protocol") == "vless" and 
                        inbound.get("port") == 443 and  # Требуем именно порт 443
                        inbound.get("enable") == True):
                        
                        stream_settings = json.loads(inbound.get("streamSettings", "{}"))
                        if stream_settings.get("security") == "reality":
                            reality_inbound = inbound
                            logger.info("Found Reality inbound on port 443", 
                                       inbound_id=inbound.get("id"),
                                       port=443,
                                       node_id=active_node.id)
                            break
            
            if not reality_inbound:
                logger.error("No Reality inbound found in panel", 
                           node_id=active_node.id,
                           user_id=user_id)
                return {
                    "success": False,
                    "error": "No Reality inbound found",
                    "message": "Reality inbound не найден в панели"
                }
            
            inbound_id = reality_inbound["id"]
            logger.info("Found Reality inbound", 
                       inbound_id=inbound_id,
                       port=reality_inbound.get("port"),
                       user_id=user_id)
            
            # 5. Создаем клиента в Reality inbound'е
            # Формируем email в формате [telegram_id]_[timestamp]
            from datetime import datetime
            timestamp = int(datetime.utcnow().timestamp())
            client_email = f"{user.telegram_id}_{timestamp}"
            
            # Генерируем UUID для клиента
            import uuid
            client_uuid = str(uuid.uuid4())
            
            # Формируем конфиг клиента с заданным email
            client_config = {
                "id": client_uuid,
                "email": client_email,
                "telegram_id": user.telegram_id,
                "limit_ip": 2,
                "total_gb": 100 * 1024 * 1024 * 1024,  # 100GB
                "expiry_time": 0,  # Без ограничения времени
                "enable": True,
                "sub_id": ""
            }
            
            # Создаем клиента через X3UI API
            create_result = await x3ui_client.create_client(inbound_id, client_config)
            
            if not create_result or not create_result.get("success"):
                logger.error("Failed to create client in X3UI panel", 
                           inbound_id=inbound_id,
                           user_id=user_id,
                           result=create_result)
                return {
                    "success": False,
                    "error": "Failed to create client in panel",
                    "message": "Не удалось создать клиента в панели"
                }
            
            logger.info("Client created successfully in X3UI panel", 
                       client_uuid=client_uuid,
                       client_email=client_email,
                       inbound_id=inbound_id,
                       user_id=user_id)
            
            # 6. Получаем РЕАЛЬНЫЙ VLESS URL из панели X3UI
            # ИСПРАВЛЕНИЕ БАГА: Используем реальные данные из панели вместо ручной генерации
            vless_url = await x3ui_client.generate_client_url(inbound_id, client_uuid)
            
            if not vless_url:
                logger.error("Failed to generate VLESS URL from X3UI panel", 
                           inbound_id=inbound_id,
                           client_uuid=client_uuid,
                           user_id=user_id)
                return {
                    "success": False,
                    "error": "Failed to generate VLESS URL from panel",
                    "message": "Не удалось получить VLESS URL из панели"
                }
            
            logger.info("Generated VLESS URL from X3UI panel", 
                       user_id=user_id,
                       url_length=len(vless_url),
                       panel_generated=True)
            
            # 7. Сохраняем ключ в базу данных
            from models.vpn_key import VPNKey, VPNKeyStatus
            
            vpn_key = VPNKey(
                user_id=user_id,
                node_id=active_node.id,
                uuid=client_uuid,
                key_name=key_name,
                vless_url=vless_url,
                xui_email=client_email,
                status=VPNKeyStatus.ACTIVE.value,
                xui_client_id=client_uuid,
                xui_inbound_id=inbound_id,
                total_download=0,
                total_upload=0
            )
            
            session.add(vpn_key)
            await session.commit()
            await session.refresh(vpn_key)
            
            # Обновляем статистику ноды
            from services.node_manager import NodeManager
            node_manager = NodeManager(session)
            await node_manager.update_node_stats(active_node.id)
            
            logger.info("VPN key saved to database", 
                       vpn_key_id=vpn_key.id,
                       user_id=user_id,
                       node_id=active_node.id)
            
            return {
                "success": True,
                "vpn_key_id": vpn_key.id,
                "message": "VPN ключ успешно создан через Reality inbound",
                "vpn_key": {
                    "id": vpn_key.id,
                    "key_name": vpn_key.key_name,
                    "vless_url": vpn_key.vless_url,
                    "status": vpn_key.status,
                    "x3ui_connected": True,
                    "x3ui_source": True,
                    "node_id": active_node.id,
                    "created_at": vpn_key.created_at.isoformat() if vpn_key.created_at else None
                }
            }
            
        except Exception as e:
            logger.error("Error in _create_vpn_key_with_reality_inbound", 
                        user_id=user_id,
                        error=str(e),
                        exc_info=True)
            return {
                "success": False,
                "error": f"Internal error: {str(e)}",
                "message": "Внутренняя ошибка при создании VPN ключа"
            }

# Глобальный экземпляр сервиса интеграции
integration_service = IntegrationService() 