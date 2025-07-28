"""
Тесты для утилит - проверяем рефакторинг
"""

import pytest
import allure
from utils import PaymentValidator, PaymentCalculator, PaymentUrlGenerator, PaymentService
from decimal import Decimal


@allure.epic("Utils Testing")
@allure.feature("Payment Validation")
@pytest.mark.unit
@pytest.mark.critical
def test_payment_validator_valid_data():
    """Тест валидации правильных данных платежа"""
    with allure.step("Проверяем валидацию корректных данных"):
        valid_data = {
            "user_id": 123456789,
            "subscription_type": "monthly",
            "provider_type": "robokassa",
            "enable_autopay": True,
            "user_email": "test@example.com"
        }
        
        is_valid, errors = PaymentValidator.validate_payment_data(valid_data)
        
        assert is_valid is True
        assert len(errors) == 0
        
        allure.attach(
            f"Valid data: {valid_data}",
            name="Valid Payment Data",
            attachment_type=allure.attachment_type.TEXT
        )


@pytest.mark.parametrize("invalid_data,expected_error_count", [
    ({"user_id": -1, "subscription_type": "monthly", "provider_type": "robokassa"}, 1),  # Negative user_id
    ({"user_id": "invalid", "subscription_type": "monthly", "provider_type": "robokassa"}, 1),  # Wrong type
    ({"user_id": 123, "subscription_type": "invalid", "provider_type": "robokassa"}, 1),  # Invalid subscription
    ({"user_id": 123, "subscription_type": "monthly", "provider_type": "invalid"}, 1),  # Invalid provider
    ({"user_id": 123, "subscription_type": "monthly", "provider_type": "freekassa", "enable_autopay": True}, 1),  # Autopay not supported
])
@allure.epic("Utils Testing")
@allure.feature("Payment Validation")
@pytest.mark.unit
def test_payment_validator_invalid_data(invalid_data, expected_error_count):
    """Параметризованный тест валидации неправильных данных"""
    with allure.step(f"Проверяем валидацию неправильных данных: {invalid_data}"):
        is_valid, errors = PaymentValidator.validate_payment_data(invalid_data)
        
        assert is_valid is False
        assert len(errors) >= expected_error_count
        
        error_messages = [error.message for error in errors]
        allure.attach(
            f"Invalid data: {invalid_data}\nErrors: {error_messages}",
            name="Validation Errors",
            attachment_type=allure.attachment_type.TEXT
        )


@allure.epic("Utils Testing")
@allure.feature("Payment Calculator")
@pytest.mark.unit
@pytest.mark.critical
def test_payment_calculator_amounts():
    """Тест расчета сумм платежей"""
    with allure.step("Проверяем расчет сумм для разных типов подписок"):
        # Тестируем все типы подписок
        expected_amounts = {
            "weekly": Decimal("200.00"),
            "monthly": Decimal("500.00"),
            "quarterly": Decimal("1200.00"),
            "yearly": Decimal("4000.00")
        }
        
        for subscription_type, expected_amount in expected_amounts.items():
            calculated_amount = PaymentCalculator.calculate_amount(subscription_type)
            assert calculated_amount == expected_amount
            
            # Тестируем получение полной информации
            info = PaymentCalculator.get_subscription_info(subscription_type)
            assert info["type"] == subscription_type
            assert info["price"] == float(expected_amount)
            assert info["currency"] == "RUB"
            assert info["days"] > 0
        
        allure.attach(
            f"Expected amounts: {expected_amounts}",
            name="Payment Calculator Results",
            attachment_type=allure.attachment_type.TEXT
        )


@allure.epic("Utils Testing")
@allure.feature("Payment Calculator")
@pytest.mark.unit
def test_payment_calculator_invalid_subscription():
    """Тест обработки неправильного типа подписки"""
    with allure.step("Проверяем обработку неправильного типа подписки"):
        with pytest.raises(ValueError) as exc_info:
            PaymentCalculator.calculate_amount("invalid_subscription")
        
        assert "Unknown subscription type" in str(exc_info.value)
        
        allure.attach(
            f"Error message: {exc_info.value}",
            name="Invalid Subscription Error",
            attachment_type=allure.attachment_type.TEXT
        )


@pytest.mark.parametrize("provider,expected_domain", [
    ("robokassa", "robokassa.ru"),
    ("freekassa", "freekassa.ru"),
    ("yookassa", "yookassa.ru"),
    ("coingate", "coingate.com")
])
@allure.epic("Utils Testing")
@allure.feature("Payment URL Generator")
@pytest.mark.unit
def test_payment_url_generator(provider, expected_domain):
    """Параметризованный тест генерации URL платежей"""
    with allure.step(f"Проверяем генерацию URL для {provider}"):
        payment_id = 12345
        amount = Decimal("500.00")
        
        url = PaymentUrlGenerator.generate_url(provider, payment_id, amount)
        
        assert expected_domain in url
        assert str(payment_id) in url
        assert url.startswith("https://")
        
        allure.attach(
            f"Provider: {provider}\nGenerated URL: {url}",
            name=f"URL Generation - {provider}",
            attachment_type=allure.attachment_type.TEXT
        )


@allure.epic("Utils Testing")  
@allure.feature("Payment URL Generator")
@pytest.mark.unit
def test_payment_url_generator_invalid_provider():
    """Тест обработки неправильного провайдера"""
    with allure.step("Проверяем обработку неправильного провайдера"):
        with pytest.raises(ValueError) as exc_info:
            PaymentUrlGenerator.generate_url("invalid_provider", 123, Decimal("500"))
        
        assert "Unknown payment provider" in str(exc_info.value)


@allure.epic("Utils Testing")
@allure.feature("Payment Service Integration")
@pytest.mark.integration
@pytest.mark.critical
def test_payment_service_integration():
    """Интеграционный тест PaymentService"""
    with allure.step("Проверяем интеграцию всех компонентов PaymentService"):
        service = PaymentService()
        
        payment_data = {
            "user_id": 123456789,
            "subscription_type": "monthly",
            "provider_type": "robokassa",
            "enable_autopay": True,
            "user_email": "test@example.com"
        }
        
        result = service.create_payment(payment_data)
        
        # Проверяем результат
        assert "payment_id" in result
        assert "amount" in result
        assert "payment_url" in result
        assert "subscription_info" in result
        assert "provider" in result
        
        # Проверяем корректность данных
        assert result["amount"] == 500.0  # monthly price
        assert result["provider"] == "robokassa"
        assert "robokassa.ru" in result["payment_url"]
        
        # Проверяем информацию о подписке
        sub_info = result["subscription_info"]
        assert sub_info["type"] == "monthly"
        assert sub_info["days"] == 30
        
        allure.attach(
            f"Payment result: {result}",
            name="Payment Service Integration Result",
            attachment_type=allure.attachment_type.TEXT
        )


@allure.epic("Utils Testing")
@allure.feature("Payment Service Error Handling")
@pytest.mark.integration
def test_payment_service_error_handling():
    """Тест обработки ошибок в PaymentService"""
    with allure.step("Проверяем обработку ошибок в PaymentService"):
        service = PaymentService()
        
        # Невалидные данные
        invalid_data = {
            "user_id": -1,  # Invalid user_id
            "subscription_type": "invalid",  # Invalid subscription
            "provider_type": "unknown"  # Invalid provider
        }
        
        with pytest.raises(ValueError) as exc_info:
            service.create_payment(invalid_data)
        
        error_message = str(exc_info.value)
        assert "Validation failed" in error_message
        
        allure.attach(
            f"Invalid data: {invalid_data}\nError: {error_message}",
            name="Error Handling Test",
            attachment_type=allure.attachment_type.TEXT
        )


@allure.epic("Utils Testing")
@allure.feature("Email Validation")
@pytest.mark.unit
@pytest.mark.parametrize("email,should_be_valid", [
    ("test@example.com", True),
    ("user123@domain.org", True),
    ("invalid-email", False),
    ("@domain.com", False),
    ("user@", False),
    ("user@domain", False),
])
def test_email_validation(email, should_be_valid):
    """Параметризованный тест валидации email"""
    with allure.step(f"Проверяем валидацию email: {email}"):
        test_data = {
            "user_id": 123,
            "subscription_type": "monthly",
            "provider_type": "robokassa",
            "user_email": email
        }
        
        is_valid, errors = PaymentValidator.validate_payment_data(test_data)
        
        if should_be_valid:
            # Не должно быть ошибок email валидации
            email_errors = [error for error in errors if error.field == "user_email"]
            assert len(email_errors) == 0
        else:
            # Должна быть ошибка email валидации
            email_errors = [error for error in errors if error.field == "user_email"]
            assert len(email_errors) > 0
        
        allure.attach(
            f"Email: {email}\nValid: {should_be_valid}\nErrors: {[e.message for e in errors]}",
            name=f"Email Validation - {email}",
            attachment_type=allure.attachment_type.TEXT
        )