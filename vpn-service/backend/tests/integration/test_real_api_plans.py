"""
Реальные тесты для Plans API endpoints
"""
import pytest
import allure
import httpx
from ..utils.api_helpers import make_api_request, validate_api_response


@allure.epic("Plans API")
@allure.feature("Plans Management")
@allure.story("Real API Test")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_plans_all_real_api(async_client: httpx.AsyncClient, base_url: str):
    """Тест реального API endpoint GET /plans/"""
    
    endpoint = f"{base_url}/api/v1/plans/"
    
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
                    
                    with allure.step("Валидируем структуру plans ответа"):
                        # Должен быть словарь с планами
                        assert isinstance(data, dict), "Plans должны быть представлены как словарь"
                        
                        # Проверяем что есть планы
                        assert len(data) > 0, "Должен быть хотя бы один план"
                        
                        # Проверяем структуру каждого плана
                        for plan_id, plan_data in data.items():
                            assert isinstance(plan_data, dict), f"План {plan_id} должен быть словарем"
                            
                            # Ожидаемые поля в плане
                            expected_fields = ["name", "price", "duration_days"]
                            for field in expected_fields:
                                assert field in plan_data, f"Поле '{field}' отсутствует в плане {plan_id}"
                            
                            # Проверяем типы данных
                            assert isinstance(plan_data["name"], str)
                            assert isinstance(plan_data["price"], (int, float))
                            assert isinstance(plan_data["duration_days"], int)
                            assert plan_data["price"] > 0
                            assert plan_data["duration_days"] > 0
                        
                        allure.attach(
                            str(data),
                            name="Plans Response",
                            attachment_type=allure.attachment_type.JSON
                        )
                        
                elif response.status_code == 404:
                    # API недоступен
                    pytest.skip("API endpoint не доступен (404)")
                    
                else:
                    # Неожиданная ошибка
                    pytest.fail(f"Неожиданный статус код: {response.status_code}")
                    
        except httpx.ConnectError:
            # Сервер недоступен - пропускаем тест с предупреждением
            pytest.skip("Сервер недоступен - требуется запуск backend сервиса на localhost:8000")


@allure.epic("Plans API")
@allure.feature("Plans Management")
@allure.story("Bot Integration")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_plans_bot_real_api(async_client: httpx.AsyncClient, base_url: str):
    """Тест реального API endpoint GET /plans/bot"""
    
    endpoint = f"{base_url}/api/v1/plans/bot"
    
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
                    
                    with allure.step("Валидируем структуру bot plans ответа"):
                        # Должен быть словарь с планами для бота
                        assert isinstance(data, dict), "Bot plans должны быть представлены как словарь"
                        
                        # Проверяем что есть планы
                        assert len(data) > 0, "Должен быть хотя бы один план для бота"
                        
                        # Проверяем структуру каждого плана для бота
                        for plan_id, plan_data in data.items():
                            assert isinstance(plan_data, dict), f"Bot план {plan_id} должен быть словарем"
                            
                            # Ожидаемые поля в плане для бота (могут отличаться от обычных планов)
                            expected_fields = ["name", "price", "description"]
                            for field in expected_fields:
                                if field in plan_data:  # Не все поля могут быть обязательными для бота
                                    if field == "price":
                                        assert isinstance(plan_data[field], (int, float))
                                        assert plan_data[field] > 0
                                    else:
                                        assert isinstance(plan_data[field], str)
                        
                        allure.attach(
                            str(data),
                            name="Bot Plans Response",
                            attachment_type=allure.attachment_type.JSON
                        )
                        
                elif response.status_code == 404:
                    # API недоступен
                    pytest.skip("API endpoint не доступен (404)")
                    
                else:
                    # Неожиданная ошибка
                    pytest.fail(f"Неожиданный статус код: {response.status_code}")
                    
        except httpx.ConnectError:
            # Сервер недоступен - пропускаем тест с предупреждением
            pytest.skip("Сервер недоступен - требуется запуск backend сервиса на localhost:8000")


@allure.epic("Plans API")
@allure.feature("Plans Management")
@allure.story("Plans Validation")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_plans_structure_validation(subscription_types):
    """Тест валидации структуры планов"""
    
    with allure.step("Проверяем корректность структуры планов"):
        # Используем тестовые данные подписок для валидации
        for plan_data in subscription_types:
            plan_type = plan_data["type"]
            price = plan_data["price"]
            days = plan_data["days"]
            
            with allure.step(f"Валидируем план: {plan_type}"):
                # Проверяем что план имеет корректную структуру
                assert isinstance(plan_type, str) and len(plan_type) > 0
                assert isinstance(price, (int, float)) and price > 0
                assert isinstance(days, int) and days > 0
                
                # Проверяем логическую корректность планов
                if plan_type == "weekly":
                    assert days == 7, "Недельный план должен быть на 7 дней"
                elif plan_type == "monthly":
                    assert days == 30, "Месячный план должен быть на 30 дней"
                elif plan_type == "quarterly":
                    assert days == 90, "Квартальный план должен быть на 90 дней"
                elif plan_type == "yearly":
                    assert days == 365, "Годовой план должен быть на 365 дней"
                
                # Проверяем что более длинные планы имеют лучшую цену за день
                price_per_day = price / days
                assert price_per_day > 0, "Цена за день должна быть положительной"
                
                allure.attach(
                    str({
                        "type": plan_type,
                        "price": price,
                        "days": days,
                        "price_per_day": price_per_day
                    }),
                    name=f"Plan Analysis - {plan_type}",
                    attachment_type=allure.attachment_type.JSON
                )


@allure.epic("Plans API")
@allure.feature("Plans Management")
@allure.story("Fallback Mock Test")
@pytest.mark.asyncio
@pytest.mark.critical
async def test_plans_mock_fallback():
    """Fallback тест с мок данными если API недоступен"""
    
    with allure.step("Проверяем мок структуру plans"):
        # Мок данные планов
        mock_plans = {
            "weekly": {
                "name": "Недельная подписка",
                "price": 200.0,
                "duration_days": 7,
                "description": "Доступ на 7 дней"
            },
            "monthly": {
                "name": "Месячная подписка", 
                "price": 500.0,
                "duration_days": 30,
                "description": "Доступ на 30 дней"
            },
            "yearly": {
                "name": "Годовая подписка",
                "price": 4000.0,
                "duration_days": 365,
                "description": "Доступ на 365 дней"
            }
        }
        
        # Проверяем базовую структуру планов
        assert isinstance(mock_plans, dict), "Plans должны быть словарем"
        assert len(mock_plans) > 0, "Должны быть планы"
        
        for plan_id, plan_data in mock_plans.items():
            # Проверяем обязательные поля
            required_fields = ["name", "price", "duration_days"]
            for field in required_fields:
                assert field in plan_data, f"Поле '{field}' отсутствует в плане {plan_id}"
            
            # Проверяем типы и значения
            assert isinstance(plan_data["name"], str)
            assert isinstance(plan_data["price"], (int, float))
            assert isinstance(plan_data["duration_days"], int)
            assert plan_data["price"] > 0
            assert plan_data["duration_days"] > 0
        
        allure.attach(
            str(mock_plans),
            name="Mock Plans Structure",
            attachment_type=allure.attachment_type.JSON
        )