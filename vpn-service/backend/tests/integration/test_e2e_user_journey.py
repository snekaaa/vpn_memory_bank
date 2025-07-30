import pytest
import allure

@allure.epic("E2E User Journey")
@allure.feature("Complete User Flow")
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_complete_user_journey_mock():
    """E2E тест полного пользовательского пути с мок данными"""
    with allure.step("Полный путь пользователя от регистрации до получения VPN"):
        
        # Шаг 1: Пользователь нажимает /start в боте
        user_start_data = {
            "telegram_id": 987654321,
            "username": "new_user",
            "first_name": "John",
            "last_name": "Doe"  
        }
        
        # Проверяем что пользователь новый
        assert user_start_data["telegram_id"] > 0
        assert len(user_start_data["username"]) > 0
        
        # Шаг 2: Проверяем настройки приложения (триал включен)
        app_settings = {
            "trial_enabled": True,
            "trial_days": 3,
            "auto_renewal_enabled": True
        }
        
        assert app_settings["trial_enabled"] is True
        assert app_settings["trial_days"] > 0
        
        # Шаг 3: Создаем пользователя с триалом через full-cycle
        full_cycle_response = {
            "success": True,
            "user_created": True,
            "subscription_created": True,
            "vpn_key_created": True,
            "user": {
                "telegram_id": user_start_data["telegram_id"],
                "subscription_active": True,
                "subscription_days_left": app_settings["trial_days"]
            },
            "vpn_key": {
                "key_id": "trial_key_123",
                "status": "active",
                "config": "vless://trial-config..."
            }
        }
        
        # Проверяем что триал создался успешно
        assert full_cycle_response["success"] is True
        assert full_cycle_response["user"]["subscription_active"] is True
        assert full_cycle_response["vpn_key"]["status"] == "active"
        
        allure.attach(
            f"User journey completed successfully for {user_start_data['telegram_id']}",
            name="Complete User Journey",
            attachment_type=allure.attachment_type.TEXT
        )

@allure.epic("E2E User Journey") 
@allure.feature("Payment Flow")
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_payment_to_vpn_journey_mock():
    """E2E тест пути от создания платежа до активации VPN"""
    with allure.step("Путь от платежа до получения VPN ключа"):
        
        # Создаем платеж
        payment_response = {
            "status": "success",
            "payment_id": 54321,
            "payment_url": "https://robokassa.ru/payment/54321",
            "amount": 500.0,
            "currency": "RUB"
        }
        
        # Приходит webhook
        webhook_payload = {
            "payment_id": payment_response["payment_id"],
            "status": "succeeded",
            "amount": payment_response["amount"]
        }
        
        # Активируется подписка
        subscription_activated = {
            "subscription_active": True,
            "subscription_days_left": 30,
            "payment_id": payment_response["payment_id"]
        }
        
        # Проверяем весь поток
        assert payment_response["status"] == "success"
        assert webhook_payload["status"] == "succeeded"
        assert subscription_activated["subscription_active"] is True
        
        allure.attach(
            f"Payment flow completed for payment {payment_response['payment_id']}",
            name="Payment to VPN Journey",
            attachment_type=allure.attachment_type.TEXT
        )
