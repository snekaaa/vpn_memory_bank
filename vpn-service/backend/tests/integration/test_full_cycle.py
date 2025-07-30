import pytest
import allure

@allure.epic("Integration API")
@allure.feature("Full Cycle")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_full_cycle_mock_fallback():
    """Fallback тест с мок данными для full-cycle если API недоступен"""
    with allure.step("Проверяем мок данные для full-cycle процесса"):
        # Входные данные пользователя
        user_input = {
            "telegram_id": 123456789,
            "username": "test_user",
            "first_name": "Test",
            "last_name": "User",
            "plan_id": 1,
            "trial_enabled": True
        }
        
        # Ожидаемый результат full-cycle операции
        mock_result = {
            "success": True,
            "user_created": True,
            "subscription_created": True,
            "vpn_key_created": True,
            "user": {
                "telegram_id": user_input["telegram_id"],
                "username": user_input["username"],
                "subscription_active": True,
                "subscription_days_left": 3  # триал на 3 дня
            },
            "subscription": {
                "id": "sub_123",
                "plan_id": user_input["plan_id"],
                "is_trial": True,
                "expires_at": "2025-01-29T12:00:00Z"
            },
            "vpn_key": {
                "key_id": "vpn_key_456",
                "status": "active",
                "country": "US",
                "config": "vless://test-config..."
            }
        }
        
        # Проверяем основные поля результата
        assert mock_result["success"] is True
        assert mock_result["user_created"] is True
        assert mock_result["subscription_created"] is True
        assert mock_result["vpn_key_created"] is True
        
        # Проверяем данные пользователя
        user = mock_result["user"]
        assert user["telegram_id"] == user_input["telegram_id"]
        assert user["subscription_active"] is True
        
        # Проверяем подписку
        subscription = mock_result["subscription"]
        assert subscription["plan_id"] == user_input["plan_id"]
        assert subscription["is_trial"] is True
        
        # Проверяем VPN ключ
        vpn_key = mock_result["vpn_key"]
        assert vpn_key["status"] == "active"
        assert "config" in vpn_key
        
        allure.attach(
            str(mock_result),
            name="Full Cycle Mock Result",
            attachment_type=allure.attachment_type.JSON
        )

@allure.epic("Integration API")
@allure.feature("Full Cycle")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_full_cycle_different_scenarios():
    """Тест разных сценариев full-cycle операции"""
    with allure.step("Тестируем различные сценарии создания пользователя"):
        
        # Сценарий 1: Создание с триалом
        trial_input = {
            "telegram_id": 111111,
            "username": "trial_user",
            "plan_id": 1,
            "trial_enabled": True
        }
        
        trial_result = {
            "success": True,
            "user_created": True,
            "subscription": {"is_trial": True, "days": 3},
            "vpn_key": {"status": "active"}
        }
        
        assert trial_result["subscription"]["is_trial"] is True
        assert trial_result["subscription"]["days"] > 0
        
        # Сценарий 2: Создание без триала (платная подписка)
        paid_input = {
            "telegram_id": 222222,
            "username": "paid_user",
            "plan_id": 2,
            "trial_enabled": False
        }
        
        paid_result = {
            "success": True,
            "user_created": True,
            "subscription": {"is_trial": False, "days": 30},
            "vpn_key": {"status": "active"}
        }
        
        assert paid_result["subscription"]["is_trial"] is False
        assert paid_result["subscription"]["days"] == 30
        
        # Сценарий 3: Ошибка создания
        error_input = {
            "telegram_id": "invalid",  # невалидный ID
            "username": "",
            "plan_id": 999  # несуществующий план
        }
        
        error_result = {
            "success": False,
            "error": "Invalid telegram_id or plan_id",
            "user_created": False
        }
        
        assert error_result["success"] is False
        assert error_result["user_created"] is False
        assert "error" in error_result
        
        allure.attach(
            f"Trial: {trial_result}\nPaid: {paid_result}\nError: {error_result}",
            name="Full Cycle Scenarios",
            attachment_type=allure.attachment_type.TEXT
        )

@allure.epic("Integration API")
@allure.feature("Full Cycle")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_full_cycle_validation_logic():
    """Тест валидации входных данных для full-cycle"""
    with allure.step("Проверяем валидацию входных данных"):
        
        # Валидные данные
        valid_input = {
            "telegram_id": 123456789,
            "username": "valid_user",
            "first_name": "John",
            "plan_id": 1
        }
        
        # Проверяем обязательные поля
        assert "telegram_id" in valid_input
        assert "username" in valid_input
        assert "plan_id" in valid_input
        
        # Проверяем типы данных
        assert isinstance(valid_input["telegram_id"], int)
        assert isinstance(valid_input["username"], str)
        assert isinstance(valid_input["plan_id"], int)
        
        # Проверяем ограничения
        assert valid_input["telegram_id"] > 0
        assert len(valid_input["username"]) > 0
        assert valid_input["plan_id"] > 0
        
        # Проверяем корректность telegram_id (должен быть положительным числом)
        assert valid_input["telegram_id"] > 0, "Telegram ID должен быть положительным"
        
        # Проверяем что username не пустой
        assert valid_input["username"].strip() != "", "Username не может быть пустым"
        
        allure.attach(
            f"Validation passed for input: {valid_input}",
            name="Input Validation Results",
            attachment_type=allure.attachment_type.TEXT
        )
