import aiohttp
import structlog
import base64
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from config.settings import get_bot_settings
# from services.local_storage import local_storage  # Временно отключен
# from services.xui_client import xui_client  # Временно отключен

logger = structlog.get_logger(__name__)

# Заглушка для local_storage
class LocalStorageStub:
    def get_user(self, telegram_id):
        return None
    def create_or_update_user(self, telegram_id, data):
        return {"id": telegram_id, **data}
    def create_subscription(self, telegram_id, sub_type):
        return {"id": 1, "type": sub_type}
    def get_user_subscriptions(self, telegram_id):
        return []
    def get_user_vpn_keys(self, telegram_id):
        return []
    def get_vpn_key(self, key_id):
        return None
    def _save_data(self):
        pass

local_storage = LocalStorageStub()

@dataclass
class UserProfile:
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    referral_code: Optional[str]
    referred_by: Optional[int]
    is_premium: bool
    created_at: str
    notifications_enabled: bool = True
    notification_settings: Dict[str, bool] = None

@dataclass
class Subscription:
    id: int
    subscription_type: str
    status: str
    start_date: Optional[str]
    end_date: Optional[str]
    price: float
    is_active: bool

@dataclass
class Payment:
    id: int
    amount: float
    currency: str
    status: str
    payment_method: str
    description: Optional[str]
    created_at: str
    
@dataclass
class VPNKey:
    id: int
    key_name: str
    server_location: str
    traffic_used_bytes: int
    is_active: bool
    created_at: str

class APIClient:
    def __init__(self):
        self.settings = get_bot_settings()
        self.base_url = self.settings.backend_api_url
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает или создает HTTP сессию"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Закрывает HTTP сессию"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Выполняет HTTP запрос к API"""
        try:
            session = await self._get_session()
            url = f"{self.base_url}{endpoint}"
            
            async with session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None
                else:
                    response_text = await response.text()
                    logger.error(
                        "API request failed",
                        method=method,
                        endpoint=endpoint,
                        status=response.status,
                        response=response_text[:500]
                    )
                    return None
                    
        except Exception as e:
            logger.error(
                "API request error",
                method=method,
                endpoint=endpoint,
                error=str(e)
            )
            return None
    
    async def authenticate_user(
        self, 
        telegram_id: int, 
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Аутентификация пользователя через Telegram"""
        try:
            # Проверяем существует ли пользователь
            user_data = local_storage.get_user(telegram_id)
            
            if user_data:
                # Пользователь найден - обновляем информацию
                updated_data = {
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name
                }
                user = local_storage.create_or_update_user(telegram_id, updated_data)
                
                return {
                    "success": True,
                    "user": user,
                    "access_token": f"token_{telegram_id}"
                }
            else:
                # Пользователь не найден
                return {
                    "success": False,
                    "error": "Пользователь не найден. Требуется регистрация."
                }
                
        except Exception as e:
            logger.error("Failed to authenticate user", telegram_id=telegram_id, error=str(e))
            return {
                "success": False,
                "error": f"Ошибка аутентификации: {str(e)}"
            }

    async def register_user(self, registration_data: Dict[str, Any]) -> Dict[str, Any]:
        """Регистрация нового пользователя"""
        try:
            telegram_id = registration_data.get("telegram_id")
            
            if not telegram_id:
                return {
                    "success": False,
                    "error": "Telegram ID обязателен для регистрации"
                }
            
            # Проверяем что пользователь еще не зарегистрирован
            existing_user = local_storage.get_user(telegram_id)
            if existing_user:
                return {
                    "success": False,
                    "error": "Пользователь уже зарегистрирован"
                }
            
            # Создаем нового пользователя
            user_data = {
                "username": registration_data.get("username"),
                "first_name": registration_data.get("first_name"),
                "last_name": registration_data.get("last_name"),
                "phone": registration_data.get("phone"),
                "language_code": registration_data.get("language_code", "ru")
            }
            
            user = local_storage.create_or_update_user(telegram_id, user_data)
            
            # Создаем пробную подписку для нового пользователя
            trial_subscription = local_storage.create_subscription(telegram_id, "trial")
            
            logger.info("New user registered", 
                       telegram_id=telegram_id, 
                       username=user_data.get("username"),
                       trial_subscription_id=trial_subscription.get("id"))
            
            return {
                "success": True,
                "user": user,
                "access_token": f"token_{telegram_id}",
                "trial_subscription": trial_subscription
            }
            
        except Exception as e:
            logger.error("Failed to register user", 
                        telegram_id=registration_data.get("telegram_id"), 
                        error=str(e))
            return {
                "success": False,
                "error": f"Ошибка регистрации: {str(e)}"
            }
    
    async def get_user_profile(self, telegram_id: int) -> Optional[UserProfile]:
        """Получение профиля пользователя"""
        try:
            user_data = local_storage.get_user(telegram_id)
            if user_data:
                return UserProfile(
                    id=user_data["id"],
                    telegram_id=user_data["telegram_id"],
                    username=user_data.get("username"),
                    first_name=user_data.get("first_name"),
                    email=user_data.get("email"),
                    phone=user_data.get("phone"),
                    referral_code=user_data.get("referral_code"),
                    referred_by=user_data.get("referred_by"),
                    is_premium=user_data.get("is_premium", False),
                    created_at=user_data["created_at"],
                    notifications_enabled=user_data.get("notifications_enabled", True),
                    notification_settings=user_data.get("notification_settings", {})
                )
        except Exception as e:
            logger.error("Failed to get user profile", telegram_id=telegram_id, error=str(e))
        return None
    
    async def update_notification_settings(self, telegram_id: int, settings: Dict[str, bool]) -> bool:
        """Обновление настроек уведомлений"""
        response = await self._make_request(
            "PUT",
            f"/api/v1/users/{telegram_id}/notification-settings",
            data={"notification_settings": settings}
        )
        return response is not None
    
    async def get_user_subscriptions(self, telegram_id: int) -> List[Subscription]:
        """Получение подписок пользователя"""
        try:
            subscriptions_data = local_storage.get_user_subscriptions(telegram_id)
            return [
                Subscription(
                    id=sub["id"],
                    subscription_type=sub["subscription_type"],
                    status=sub["status"],
                    start_date=sub.get("start_date"),
                    end_date=sub.get("end_date"),
                    price=sub["price"],
                    is_active=sub["is_active"]
                )
                for sub in subscriptions_data
            ]
        except Exception as e:
            logger.error("Failed to get user subscriptions", telegram_id=telegram_id, error=str(e))
            return []
    
    async def get_user_payments(self, telegram_id: int) -> List[Payment]:
        """Получение платежей пользователя"""
        response = await self._make_request("GET", f"/api/v1/payments/user/telegram/{telegram_id}")
        
        if response and isinstance(response, list):
            return [
                Payment(
                    id=pay["id"],
                    amount=pay["amount"],
                    currency=pay["currency"],
                    status=pay["status"],
                    payment_method=pay["payment_method"],
                    description=pay.get("description"),
                    created_at=pay["created_at"]
                )
                for pay in response
            ]
        return []
    
    async def get_user_vpn_keys(self, telegram_id: int) -> List[VPNKey]:
        """Получение VPN ключей пользователя"""
        try:
            vpn_keys_data = local_storage.get_user_vpn_keys(telegram_id)
            return [
                VPNKey(
                    id=key["id"],
                    key_name=f"{key['server']['name']} - {key['subscription_type']}",
                    server_location=key["server"]["location"],
                    traffic_used_bytes=key.get("traffic_used_bytes", 0),
                    is_active=key["is_active"],
                    created_at=key["created_at"]
                )
                for key in vpn_keys_data
            ]
        except Exception as e:
            logger.error("Failed to get user VPN keys", telegram_id=telegram_id, error=str(e))
            return []
    
    async def create_subscription(self, telegram_id: int, subscription_type: str) -> Optional[Dict[str, Any]]:
        """Создание новой подписки"""
        try:
            # Создаем подписку локально
            subscription_data = local_storage.create_subscription(telegram_id, subscription_type)
            
            # Для пробной подписки сразу создаем реальный VPN ключ
            # if subscription_type == "trial" and subscription_data:
            #     # Получаем username пользователя
            #     user_data = local_storage.get_user(telegram_id)
            #     username = user_data.get('username', '') if user_data else ''
            #     vpn_user = await xui_client.create_vless_user(telegram_id, subscription_type, username)
            #     if vpn_user:
            #         logger.info("Real VLESS user created", telegram_id=telegram_id, uuid=vpn_user["uuid"])
            #         # Обновляем локальные данные с реальным UUID
            #         vpn_keys = local_storage.get_user_vpn_keys(telegram_id)
            #         if vpn_keys:
            #             latest_key = vpn_keys[-1]  # Последний созданный ключ
            #             latest_key["real_uuid"] = vpn_user["uuid"]
            #             latest_key["real_server"] = vpn_user["server_address"]
            #             latest_key["real_port"] = vpn_user["server_port"]
            #             local_storage._save_data()
            #     else:
            #         logger.warning("Failed to create real VLESS user, using local mock", telegram_id=telegram_id)
            
            return subscription_data
        except Exception as e:
            logger.error("Failed to create subscription", telegram_id=telegram_id, error=str(e))
            return None
    
    async def create_payment(self, payment_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Создание нового платежа"""
        try:
            result = await self._make_request("POST", "/api/v1/payments/create", data=payment_data)
            
            if result:
                logger.info("Payment created successfully", 
                           payment_id=result.get("payment_id"),
                           amount=result.get("amount"))
                return result
            else:
                logger.error("Failed to create payment")
                return None
                
        except Exception as e:
            logger.error("Error creating payment", error=str(e))
            return None

    async def get_payment_status(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """Получение статуса платежа"""
        try:
            result = await self._make_request("GET", f"/api/v1/payments/{payment_id}")
            
            if result:
                logger.info("Payment status retrieved", 
                           payment_id=payment_id,
                           status=result.get("payment_status"))
                return result
            else:
                logger.error("Failed to get payment status", payment_id=payment_id)
                return None
                
        except Exception as e:
            logger.error("Error getting payment status", payment_id=payment_id, error=str(e))
            return None

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получить пользователя по Telegram ID"""
        try:
            response = await self._make_request(
                method="GET",
                endpoint=f"/api/v1/users/telegram/{telegram_id}"
            )
            return response
        except Exception as e:
            logger.error("Failed to get user by telegram_id", telegram_id=telegram_id, error=str(e))
            return None

    async def get_user_pending_payments(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получить неоплаченные платежи пользователя"""
        try:
            response = await self._make_request(
                method="GET",
                endpoint=f"/api/v1/users/telegram/{telegram_id}/pending-payments"
            )
            return response
        except Exception as e:
            logger.error("Failed to get user pending payments", telegram_id=telegram_id, error=str(e))
            return None

    async def cancel_user_pending_payments(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Отменить все неоплаченные платежи пользователя"""
        try:
            response = await self._make_request(
                method="POST",
                endpoint=f"/api/v1/users/telegram/{telegram_id}/cancel-pending-payments"
            )
            return response
        except Exception as e:
            logger.error("Failed to cancel user pending payments", telegram_id=telegram_id, error=str(e))
            return None

    async def get_vpn_config(self, telegram_id: int, vpn_key_id: int) -> Optional[str]:
        """Получение конфигурации VPN"""
        try:
            vpn_key = local_storage.get_vpn_key(vpn_key_id)
            if vpn_key:
                return vpn_key.get("vless_url")
        except Exception as e:
            logger.error("Failed to get VPN config", vpn_key_id=vpn_key_id, error=str(e))
        return None
    
    async def get_vpn_qr_code(self, telegram_id: int, vpn_key_id: int) -> Optional[bytes]:
        """Получение QR-кода для VPN"""
        try:
            vpn_key = local_storage.get_vpn_key(vpn_key_id)
            if vpn_key and vpn_key.get("qr_code"):
                # Декодируем base64 QR код
                qr_data = base64.b64decode(vpn_key["qr_code"])
                return qr_data
        except Exception as e:
            logger.error("Error getting VPN QR code", vpn_key_id=vpn_key_id, error=str(e))
        return None
    
    async def get_vpn_statistics(self, telegram_id: int, vpn_key_id: int) -> Optional[Dict[str, Any]]:
        """Получение статистики VPN ключа"""
        try:
            vpn_key = local_storage.get_vpn_key(vpn_key_id)
            if vpn_key:
                return {
                    "traffic_used_bytes": vpn_key.get("traffic_used_bytes", 0),
                    "traffic_limit_bytes": vpn_key.get("traffic_limit_bytes", 0),
                    "connections_count": 0,  # Пока что статическое значение
                    "server_location": vpn_key["server"]["location"],
                    "last_connection": None
                }
        except Exception as e:
            logger.error("Failed to get VPN statistics", vpn_key_id=vpn_key_id, error=str(e))
        return None

    async def get_active_payment_providers(self) -> Optional[Dict[str, Any]]:
        """Получение списка активных провайдеров оплаты"""
        try:
            response = await self._make_request(
                method="GET",
                endpoint="/api/v1/payments/providers/active"
            )
            return response
        except Exception as e:
            logger.error("Failed to get active payment providers", error=str(e))
            return None

# Создаем глобальный экземпляр API клиента
api_client = APIClient() 