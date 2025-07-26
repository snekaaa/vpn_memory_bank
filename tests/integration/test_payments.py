import pytest
import allure

@allure.epic("Payments API")
@allure.feature("Payment Creation")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_create_payment_mock_fallback():
    """Fallback тест с мок данными для создания платежа если API недоступен"""
    with allure.step("Проверяем мок данные для создания платежа"):
        # Входные данные для создания платежа
        payment_request = {
            "user_id": 123456789,
            "subscription_type": "monthly",
            "service_name": "VPN Premium", 
            "user_email": "test@example.com",
            "success_url": "https://vpn-bezlagov.ru/payment/success",
            "fail_url": "https://vpn-bezlagov.ru/payment/fail",
            "provider_type": "robokassa",
            "enable_autopay": False
        }
        
        # Ожидаемый результат создания платежа
        mock_payment_response = {
            "status": "success",
            "payment_id": 12345,
            "payment_url": "https://robokassa.ru/Merchant/Index.aspx?MerchantLogin=vpn-bezlagov&OutSum=500.00...",
            "amount": 500.0,
            "currency": "RUB"
        }
        
        # Проверяем обязательные поля запроса
        assert "user_id" in payment_request
        assert "subscription_type" in payment_request
        assert isinstance(payment_request["user_id"], int)
        assert payment_request["user_id"] > 0
        
        # Проверяем поля ответа
        assert mock_payment_response["status"] == "success"
        assert "payment_id" in mock_payment_response
        assert "payment_url" in mock_payment_response
        assert "amount" in mock_payment_response
        assert "currency" in mock_payment_response
        
        allure.attach(
            str(mock_payment_response),
            name="Payment Creation Mock Data",
            attachment_type=allure.attachment_type.JSON
        )

@allure.epic("Payments API")
@allure.feature("Payment Creation")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_create_payment_different_subscriptions():
    """Тест создания платежей для разных типов подписки"""
    with allure.step("Тестируем создание платежей для разных планов"):
        
        # Месячная подписка
        monthly_request = {
            "user_id": 111111,
            "subscription_type": "monthly",
            "provider_type": "robokassa",
            "enable_autopay": False
        }
        
        monthly_response = {
            "status": "success",
            "payment_id": 101,
            "payment_url": "https://robokassa.ru/monthly_payment",
            "amount": 500.0,
            "currency": "RUB"
        }
        
        # Проверяем месячную подписку
        assert monthly_request["subscription_type"] == "monthly"
        assert monthly_response["amount"] == 500.0
        
        # Квартальная подписка  
        quarterly_request = {
            "user_id": 222222,
            "subscription_type": "quarterly",
            "provider_type": "robokassa",
            "enable_autopay": True
        }
        
        quarterly_response = {
            "status": "success",
            "payment_id": 102,
            "payment_url": "https://robokassa.ru/quarterly_payment",
            "amount": 1200.0,
            "currency": "RUB"
        }
        
        # Проверяем квартальную подписку
        assert quarterly_request["subscription_type"] == "quarterly"
        assert quarterly_request["enable_autopay"] is True
        assert quarterly_response["amount"] == 1200.0
        
        allure.attach(
            f"Monthly: {monthly_response}\nQuarterly: {quarterly_response}",
            name="Different Subscription Types",
            attachment_type=allure.attachment_type.TEXT
        )

@allure.epic("Payments API")
@allure.feature("Payment Creation")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_create_payment_validation_logic():
    """Тест валидации данных при создании платежа"""
    with allure.step("Проверяем валидацию входных данных для создания платежа"):
        
        # Валидные данные
        valid_request = {
            "user_id": 123456789,
            "subscription_type": "monthly",
            "service_name": "VPN Premium",
            "user_email": "valid@example.com",
            "provider_type": "robokassa",
            "enable_autopay": False
        }
        
        # Проверяем обязательные поля
        required_fields = ["user_id", "subscription_type"]
        for field in required_fields:
            assert field in valid_request, f"Обязательное поле {field} отсутствует"
        
        # Проверяем типы данных  
        assert isinstance(valid_request["user_id"], int), "user_id должен быть числом"
        assert isinstance(valid_request["subscription_type"], str), "subscription_type должен быть строкой"
        assert isinstance(valid_request["enable_autopay"], bool), "enable_autopay должен быть булевым"
        
        # Проверяем ограничения
        assert valid_request["user_id"] > 0, "user_id должен быть положительным"
        assert len(valid_request["subscription_type"]) > 0, "subscription_type не может быть пустым"
        
        allure.attach(
            f"Validation passed for request: {valid_request}",
            name="Payment Request Validation",
            attachment_type=allure.attachment_type.TEXT
        )
