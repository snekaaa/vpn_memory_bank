import pytest
import httpx
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from datetime import datetime, timedelta

# Real API client fixtures for HTTP requests
@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Фикстура для асинхронного HTTP клиента"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client

@pytest.fixture
def base_url() -> str:
    """Базовый URL для API тестов"""
    return "http://localhost:8000"

@pytest.fixture
def test_telegram_id() -> int:
    """Тестовый Telegram ID"""
    return 123456789

@pytest.fixture
def test_user_data() -> Dict[str, Any]:
    """Тестовые данные пользователя для реальных API вызовов"""
    return {
        "telegram_id": 123456789,
        "username": "test_user",
        "first_name": "Test",
        "last_name": "User",
        "language_code": "ru"
    }


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Базовые данные пользователя для тестов"""
    return {
        "telegram_id": 123456789,
        "username": "test_user",
        "first_name": "John",
        "last_name": "Doe",
        "language_code": "ru"
    }


@pytest.fixture
def sample_payment_data() -> Dict[str, Any]:
    """Базовые данные платежа для тестов"""
    return {
        "user_id": 123456789,
        "subscription_type": "monthly",
        "service_name": "VPN Premium",
        "user_email": "test@example.com",
        "success_url": "https://vpn-bezlagov.ru/payment/success",
        "fail_url": "https://vpn-bezlagov.ru/payment/fail",
        "provider_type": "robokassa",
        "enable_autopay": False
    }


@pytest.fixture
def sample_payment_response() -> Dict[str, Any]:
    """Стандартный ответ при создании платежа"""
    return {
        "status": "success",
        "payment_id": 12345,
        "payment_url": "https://robokassa.ru/Merchant/Index.aspx?MerchantLogin=vpn-bezlagov&OutSum=500.00...",
        "amount": 500.0,
        "currency": "RUB"
    }


@pytest.fixture
def subscription_types() -> List[Dict[str, Any]]:
    """Различные типы подписок с ценами"""
    return [
        {"type": "weekly", "price": 200.0, "days": 7},
        {"type": "monthly", "price": 500.0, "days": 30},
        {"type": "quarterly", "price": 1200.0, "days": 90},
        {"type": "yearly", "price": 4000.0, "days": 365}
    ]


@pytest.fixture
def payment_providers() -> List[Dict[str, Any]]:
    """Список поддерживаемых платежных провайдеров"""
    return [
        {
            "name": "robokassa",
            "base_url": "https://robokassa.ru",
            "supports_autopay": True,
            "currencies": ["RUB"]
        },
        {
            "name": "freekassa",
            "base_url": "https://freekassa.ru",
            "supports_autopay": False,
            "currencies": ["RUB"]
        },
        {
            "name": "yookassa",
            "base_url": "https://yookassa.ru",
            "supports_autopay": True,
            "currencies": ["RUB"]
        },
        {
            "name": "coingate",
            "base_url": "https://coingate.com",
            "supports_autopay": False,
            "currencies": ["RUB", "USD", "EUR", "BTC", "ETH"]
        }
    ]


@pytest.fixture
def yookassa_webhook_payload() -> Dict[str, Any]:
    """Стандартный webhook payload от YooKassa"""
    return {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": "25b94794-000f-5000-9000-145f6df21d6f",
            "status": "succeeded",
            "amount": {
                "value": "500.00",
                "currency": "RUB"
            },
            "description": "VPN подписка",
            "metadata": {
                "order_id": "12345",
                "user_id": "123456789"
            },
            "created_at": "2025-01-26T12:00:00.000Z",
            "captured_at": "2025-01-26T12:00:05.000Z"
        }
    }


@pytest.fixture
def freekassa_webhook_payload() -> Dict[str, Any]:
    """Стандартный webhook payload от FreeKassa"""
    return {
        "MERCHANT_ID": "12345",
        "AMOUNT": "500.00",
        "intid": "98765",
        "MERCHANT_ORDER_ID": "order_12345",
        "P_EMAIL": "user@example.com",
        "P_PHONE": "",
        "CUR_ID": "RUB",
        "SIGN": "calculated_signature_hash",
        "us_user_id": "123456789"
    }


@pytest.fixture
def coingate_webhook_payload() -> Dict[str, Any]:
    """Стандартный webhook payload от CoinGate"""
    return {
        "id": 12345,
        "status": "paid",
        "price_amount": "500.00",
        "price_currency": "RUB",
        "receive_amount": "0.000123",
        "receive_currency": "BTC",
        "created_at": "2025-01-26T12:00:00+00:00",
        "order_id": "order_12345",
        "payment_url": "https://coingate.com/invoice/abc123",
        "token": "webhook_verification_token"
    }


@pytest.fixture
def app_settings_trial_enabled() -> Dict[str, Any]:
    """Настройки приложения с включенным триалом"""
    return {
        "trial_enabled": True,
        "trial_days": 3,
        "auto_renewal_enabled": True,
        "auto_create_vpn_key": True,
        "max_vpn_keys_per_user": 5
    }


@pytest.fixture
def app_settings_trial_disabled() -> Dict[str, Any]:
    """Настройки приложения с отключенным триалом"""
    return {
        "trial_enabled": False,
        "trial_days": 0,
        "auto_renewal_enabled": True,
        "auto_create_vpn_key": False,
        "max_vpn_keys_per_user": 3
    }


@pytest.fixture
def sample_vpn_key() -> Dict[str, Any]:
    """Образец VPN ключа"""
    return {
        "key_id": "test_key_123456789",
        "user_id": 123456789,
        "status": "active",
        "country": "US",
        "config": "vless://test-config-data-here...",
        "created_at": "2025-01-26T12:00:00Z",
        "expires_at": "2025-02-26T12:00:00Z"
    }


@pytest.fixture
def sample_dashboard_active_user() -> Dict[str, Any]:
    """Dashboard активного пользователя"""
    return {
        "user": {
            "telegram_id": 123456789,
            "username": "active_user",
            "subscription_active": True,
            "subscription_days_left": 25,
            "is_trial": False
        },
        "vpn_keys": [
            {
                "key_id": "active_key_1",
                "country": "US",
                "status": "active",
                "expires_at": "2025-02-20T12:00:00Z"
            }
        ],
        "subscription": {
            "plan_name": "Monthly",
            "auto_renewal": True,
            "next_payment_date": "2025-02-20"
        }
    }


@pytest.fixture
def sample_dashboard_trial_user() -> Dict[str, Any]:
    """Dashboard пользователя с триалом"""
    return {
        "user": {
            "telegram_id": 987654321,
            "username": "trial_user",
            "subscription_active": True,
            "subscription_days_left": 2,
            "is_trial": True
        },
        "vpn_keys": [
            {
                "key_id": "trial_key_1",
                "country": "US",
                "status": "active",
                "expires_at": "2025-01-28T12:00:00Z"
            }
        ],
        "subscription": {
            "plan_name": "Trial",
            "auto_renewal": False,
            "trial": True
        }
    }


@pytest.fixture
def sample_dashboard_expired_user() -> Dict[str, Any]:
    """Dashboard пользователя с истекшей подпиской"""
    return {
        "user": {
            "telegram_id": 111222333,
            "username": "expired_user",
            "subscription_active": False,
            "subscription_days_left": 0,
            "is_trial": False
        },
        "vpn_keys": [],
        "subscription": {
            "plan_name": "Expired",
            "auto_renewal": False
        }
    }


@pytest.fixture
def payment_statuses() -> Dict[str, List[str]]:
    """Различные статусы платежей для разных провайдеров"""
    return {
        "success": ["succeeded", "paid", "completed"],
        "pending": ["pending", "confirming", "waiting_for_capture"],
        "failed": ["canceled", "expired", "failed", "invalid"]
    }


@pytest.fixture
def webhook_signatures() -> Dict[str, Dict[str, Any]]:
    """Данные для проверки подписей webhook'ов"""
    return {
        "yookassa": {
            "method": "basic_auth",
            "header": "Authorization",
            "value": "Basic base64_encoded_credentials"
        },
        "freekassa": {
            "method": "md5_hash",
            "fields": ["MERCHANT_ID", "AMOUNT", "secret_key", "MERCHANT_ORDER_ID"],
            "secret_key": "test_secret_key"
        },
        "coingate": {
            "method": "token_verification",
            "field": "token",
            "expected_token": "webhook_verification_token_here"
        }
    }


@pytest.fixture
def error_responses() -> Dict[str, Dict[str, Any]]:
    """Стандартные ответы ошибок"""
    return {
        "user_not_found": {
            "status": "error",
            "error_code": 404,
            "error_message": "Пользователь не найден"
        },
        "invalid_subscription": {
            "status": "error",
            "error_code": 400,
            "error_message": "Неверный тип подписки"
        },
        "unsupported_provider": {
            "status": "error",
            "error_code": 400,
            "error_message": "Провайдер не поддерживается"
        },
        "internal_error": {
            "status": "error",
            "error_code": 500,
            "error_message": "Внутренняя ошибка сервера"
        },
        "invalid_json": {
            "error_type": "invalid_json",
            "status_code": 400,
            "error_message": "Invalid JSON format"
        },
        "missing_signature": {
            "error_type": "missing_signature",
            "status_code": 401,
            "error_message": "Missing or invalid signature"
        }
    }


@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для сессии тестов"""
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_context():
    """Асинхронный контекст для тестов"""
    # Можно добавить инициализацию асинхронных ресурсов
    yield
    # Очистка ресурсов после тестов


# Utility fixtures для генерации данных
@pytest.fixture
def generate_user_data():
    """Функция для генерации данных пользователя"""
    def _generate(telegram_id: int = None, username: str = None) -> Dict[str, Any]:
        import random
        if telegram_id is None:
            telegram_id = random.randint(100000000, 999999999)
        if username is None:
            username = f"test_user_{telegram_id}"
        
        return {
            "telegram_id": telegram_id,
            "username": username,
            "first_name": "Test",
            "last_name": "User",
            "language_code": "ru"
        }
    return _generate


@pytest.fixture
def generate_payment_data():
    """Функция для генерации данных платежа"""
    def _generate(user_id: int, subscription_type: str = "monthly", 
                  provider: str = "robokassa") -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "subscription_type": subscription_type,
            "provider_type": provider,
            "service_name": "VPN Premium",
            "enable_autopay": False
        }
    return _generate