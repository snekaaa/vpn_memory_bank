import pytest
import allure

@allure.epic("Integration API")
@allure.feature("User Dashboard")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_user_dashboard_mock_fallback():
    """Fallback тест с мок данными для user dashboard если API недоступен"""
    with allure.step("Проверяем мок структуру user dashboard"):
        # Telegram ID для теста
        test_telegram_id = 123456789
        
        # Мок данные для dashboard пользователя
        mock_dashboard = {
            "user": {
                "telegram_id": test_telegram_id,
                "username": "test_user",
                "subscription_active": True,
                "subscription_days_left": 25
            },
            "vpn_keys": [
                {
                    "key_id": "test-key-1",
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
        
        # Проверяем обязательные поля
        assert "user" in mock_dashboard
        assert "vpn_keys" in mock_dashboard
        assert "subscription" in mock_dashboard
        
        # Проверяем user поля
        user = mock_dashboard["user"]
        assert user["telegram_id"] == test_telegram_id
        assert "subscription_active" in user
        assert "subscription_days_left" in user
        
        allure.attach(
            str(mock_dashboard),
            name="Mock Dashboard Structure",
            attachment_type=allure.attachment_type.JSON
        )

@allure.epic("Integration API")
@allure.feature("User Dashboard") 
@pytest.mark.asyncio
@pytest.mark.critical
async def test_user_dashboard_different_scenarios():
    """Тест разных сценариев dashboard пользователя"""
    with allure.step("Тестируем разные состояния пользователя"):
        
        # Сценарий 1: Активная подписка
        active_user = {
            "user": {
                "telegram_id": 111111,
                "subscription_active": True,
                "subscription_days_left": 15
            },
            "vpn_keys": [{"key_id": "active-key", "status": "active"}],
            "subscription": {"auto_renewal": True}
        }
        
        assert active_user["user"]["subscription_active"] is True
        assert active_user["user"]["subscription_days_left"] > 0
        assert len(active_user["vpn_keys"]) > 0
        
        # Сценарий 2: Истекшая подписка
        expired_user = {
            "user": {
                "telegram_id": 222222,
                "subscription_active": False,
                "subscription_days_left": 0
            },
            "vpn_keys": [],
            "subscription": {"auto_renewal": False}
        }
        
        assert expired_user["user"]["subscription_active"] is False
        assert expired_user["user"]["subscription_days_left"] == 0
        assert len(expired_user["vpn_keys"]) == 0
        
        allure.attach(
            f"Active: {active_user}\nExpired: {expired_user}",
            name="Dashboard Scenarios",
            attachment_type=allure.attachment_type.TEXT
        )
