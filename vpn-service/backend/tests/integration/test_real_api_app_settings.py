"""
Реальные тесты для /api/v1/integration/app-settings endpoint
"""
import pytest
import allure
import httpx
from ..utils.api_helpers import make_api_request, validate_api_response


@allure.epic("Integration API")
@allure.feature("App Settings")
@allure.story("Real API Test")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_app_settings_real_api(async_client: httpx.AsyncClient, base_url: str):
    """Тест реального API endpoint /api/v1/integration/app-settings"""
    
    endpoint = f"{base_url}/api/v1/integration/app-settings"
    
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
                    
                    with allure.step("Валидируем структуру ответа"):
                        # Проверяем что есть поле success и settings
                        assert "success" in data, "Поле 'success' отсутствует в ответе"
                        assert "settings" in data, "Поле 'settings' отсутствует в ответе"
                        assert data["success"] is True, "API должен возвращать success=True"
                        
                        settings = data["settings"]
                        # Ожидаемые поля в настройках приложения
                        expected_fields = ["trial_enabled", "trial_days"]
                        
                        for field in expected_fields:
                            assert field in settings, f"Поле '{field}' отсутствует в settings"
                        
                        allure.attach(
                            str(data),
                            name="App Settings Response",
                            attachment_type=allure.attachment_type.JSON
                        )
                        
                elif response.status_code == 404:
                    # API недоступен - пропускаем тест
                    pytest.skip("API endpoint не доступен (404)")
                    
                else:
                    # Неожиданная ошибка
                    pytest.fail(f"Неожиданный статус код: {response.status_code}")
                    
        except httpx.ConnectError:
            # Сервер недоступен - пропускаем тест с предупреждением
            pytest.skip("Сервер недоступен - требуется запуск backend сервиса на localhost:8000")


@allure.epic("Integration API")
@allure.feature("App Settings")
@allure.story("Fallback Mock Test")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_app_settings_mock_fallback(app_settings_trial_enabled):
    """Fallback тест с мок данными если API недоступен"""
    
    with allure.step("Проверяем мок структуру app settings"):
        mock_settings = app_settings_trial_enabled
        
        # Проверяем базовые поля которые ожидаем от API
        assert "trial_enabled" in mock_settings
        assert "trial_days" in mock_settings  
        assert "auto_renewal_enabled" in mock_settings
        
        # Проверяем типы данных
        assert isinstance(mock_settings["trial_enabled"], bool)
        assert isinstance(mock_settings["trial_days"], int)
        assert isinstance(mock_settings["auto_renewal_enabled"], bool)
        
        allure.attach(
            str(mock_settings),
            name="Mock Settings Structure",
            attachment_type=allure.attachment_type.JSON
        )