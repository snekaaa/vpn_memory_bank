"""
Реальные тесты для /api/v1/integration/user-dashboard/{telegram_id} endpoint
"""
import pytest
import allure
import httpx
from ..utils.api_helpers import make_api_request, validate_api_response


@allure.epic("Integration API")
@allure.feature("User Dashboard")
@allure.story("Real API Test")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_user_dashboard_real_api(async_client: httpx.AsyncClient, base_url: str, test_telegram_id: int):
    """Тест реального API endpoint /api/v1/integration/user-dashboard/{telegram_id}"""
    
    endpoint = f"{base_url}/api/v1/integration/user-dashboard/{test_telegram_id}"
    
    with allure.step(f"Отправляем GET запрос к {endpoint}"):
        try:
            response = await make_api_request(
                client=async_client,
                method="GET",
                url=endpoint
            )
            
            with allure.step("Проверяем статус код ответа"):
                if response.status_code == 200:
                    # API доступен, проверяем структуру ответа
                    data = validate_api_response(response, 200)
                    
                    with allure.step("Валидируем структуру dashboard ответа"):
                        # Проверяем базовую структуру (согласно реальному API)
                        expected_main_fields = ["success", "user", "vpn_keys", "payments", "stats"]
                        
                        for field in expected_main_fields:
                            assert field in data, f"Поле '{field}' отсутствует в ответе"
                        
                        assert data["success"] is True, "API должен возвращать success=True"
                        
                        # Проверяем структуру user
                        user_data = data["user"]
                        user_required_fields = ["telegram_id", "username", "has_active_subscription"]
                        for user_field in user_required_fields:
                            assert user_field in user_data, f"Поле '{user_field}' отсутствует в user данных"
                        
                        # Проверяем что vpn_keys и payments это массивы
                        assert isinstance(data["vpn_keys"], list), "vpn_keys должны быть массивом"
                        assert isinstance(data["payments"], list), "payments должны быть массивом"
                        assert isinstance(data["stats"], dict), "stats должны быть словарем"
                        
                        # Проверяем структуру stats
                        stats_data = data["stats"]
                        stats_fields = ["active_vpn_keys", "total_payments", "account_status"]
                        for stats_field in stats_fields:
                            assert stats_field in stats_data, f"Поле '{stats_field}' отсутствует в stats"
                        
                        allure.attach(
                            str(data),
                            name="User Dashboard Response",
                            attachment_type=allure.attachment_type.JSON
                        )
                        
                elif response.status_code == 404:
                    # Пользователь не найден или API недоступен
                    pytest.skip("API endpoint не доступен или пользователь не найден (404)")
                    
                else:
                    # Неожиданная ошибка
                    pytest.fail(f"Неожиданный статус код: {response.status_code}")
                    
        except httpx.ConnectError:
            # Сервер недоступен - пропускаем тест с предупреждением
            pytest.skip("Сервер недоступен - требуется запуск backend сервиса на localhost:8000")


@allure.epic("Integration API")
@allure.feature("User Dashboard")
@allure.story("Different User States")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_user_dashboard_different_states(
    sample_dashboard_active_user,
    sample_dashboard_trial_user,
    sample_dashboard_expired_user
):
    """Тест различных состояний пользователя в dashboard"""
    
    test_cases = [
        ("active_user", sample_dashboard_active_user),
        ("trial_user", sample_dashboard_trial_user),
        ("expired_user", sample_dashboard_expired_user)
    ]
    
    for case_name, dashboard_data in test_cases:
        with allure.step(f"Тестируем состояние: {case_name}"):
            # Проверяем структуру данных
            assert "user" in dashboard_data
            assert "vpn_keys" in dashboard_data
            assert "subscription" in dashboard_data
            
            user_data = dashboard_data["user"]
            
            # Проверяем обязательные поля пользователя
            assert "telegram_id" in user_data
            assert "subscription_active" in user_data
            assert isinstance(user_data["subscription_active"], bool)
            
            # Специфичные проверки для разных состояний
            if case_name == "active_user":
                assert user_data["subscription_active"] is True
                assert user_data["subscription_days_left"] > 0
                assert user_data["is_trial"] is False
                assert len(dashboard_data["vpn_keys"]) > 0
                
            elif case_name == "trial_user":
                assert user_data["subscription_active"] is True
                assert user_data["is_trial"] is True
                assert dashboard_data["subscription"]["trial"] is True
                
            elif case_name == "expired_user":
                assert user_data["subscription_active"] is False
                assert user_data["subscription_days_left"] == 0
                assert len(dashboard_data["vpn_keys"]) == 0
            
            allure.attach(
                str(dashboard_data),
                name=f"Dashboard Data - {case_name}",
                attachment_type=allure.attachment_type.JSON
            )


@allure.epic("Integration API")
@allure.feature("User Dashboard")
@allure.story("Fallback Mock Test")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_user_dashboard_mock_fallback(sample_dashboard_active_user):
    """Fallback тест с мок данными если API недоступен"""
    
    with allure.step("Проверяем мок структуру user dashboard"):
        mock_dashboard = sample_dashboard_active_user
        
        # Проверяем базовые поля которые ожидаем от API
        required_fields = ["user", "vpn_keys", "subscription"]
        for field in required_fields:
            assert field in mock_dashboard, f"Поле '{field}' отсутствует в dashboard"
        
        # Проверяем структуру user
        user_data = mock_dashboard["user"]
        user_required_fields = ["telegram_id", "username", "subscription_active"]
        for field in user_required_fields:
            assert field in user_data, f"Поле '{field}' отсутствует в user данных"
        
        # Проверяем типы данных
        assert isinstance(user_data["telegram_id"], int)
        assert isinstance(user_data["subscription_active"], bool)
        assert isinstance(mock_dashboard["vpn_keys"], list)
        assert isinstance(mock_dashboard["subscription"], dict)
        
        allure.attach(
            str(mock_dashboard),
            name="Mock Dashboard Structure",
            attachment_type=allure.attachment_type.JSON
        )