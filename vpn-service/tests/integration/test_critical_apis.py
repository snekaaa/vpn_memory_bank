import pytest
from tests.utils.api_helpers import make_api_request, validate_api_response, validate_success_response

@pytest.mark.asyncio
@pytest.mark.critical
async def test_app_settings_endpoint(async_client, base_url):
    """Тест GET /api/v1/integration/app-settings"""
    url = f"{base_url}/api/v1/integration/app-settings"
    
    response = await make_api_request(async_client, "GET", url)
    data = validate_api_response(response)
    settings = validate_success_response(data)
    
    # Проверяем что settings содержит ожидаемые поля
    assert isinstance(settings, dict), "Settings should be a dictionary"

@pytest.mark.asyncio
@pytest.mark.critical
async def test_user_dashboard_endpoint(async_client, base_url, test_telegram_id):
    """Тест GET /api/v1/integration/user-dashboard/{telegram_id}"""
    url = f"{base_url}/api/v1/integration/user-dashboard/{test_telegram_id}"
    
    response = await make_api_request(async_client, "GET", url)
    data = validate_api_response(response)
    dashboard = validate_success_response(data)
    
    # Проверяем структуру dashboard
    assert isinstance(dashboard, dict), "Dashboard should be a dictionary"

@pytest.mark.asyncio
@pytest.mark.critical
async def test_full_cycle_endpoint(async_client, base_url, test_user_data):
    """Тест POST /api/v1/integration/full-cycle"""
    url = f"{base_url}/api/v1/integration/full-cycle"
    
    response = await make_api_request(async_client, "POST", url, data=test_user_data)
    data = validate_api_response(response)
    result = validate_success_response(data)
    
    # Проверяем результат full-cycle
    assert isinstance(result, dict), "Full cycle result should be a dictionary" 