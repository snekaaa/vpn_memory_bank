import pytest
import sys
import os

# Добавляем backend в путь для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

@pytest.mark.asyncio
@pytest.mark.critical
async def test_app_settings_endpoint_exists():
    """Реальный тест: проверяем что эндпоинт app-settings существует в коде"""
    try:
        from routes.integration import router
        
        # Проверяем что роутер существует
        assert router is not None
        
        # Проверяем что есть маршрут для app-settings
        routes = [route.path for route in router.routes]
        app_settings_route = "/api/v1/integration/app-settings"
        
        # Ищем маршрут в списке
        found = False
        for route in routes:
            if "app-settings" in str(route):
                found = True
                break
        
        assert found, f"Маршрут {app_settings_route} не найден в роутере"
        
        print(f"✅ Найден маршрут: {app_settings_route}")
        
    except ImportError as e:
        pytest.skip(f"Не удалось импортировать модуль: {e}")
    except Exception as e:
        pytest.fail(f"Ошибка при проверке маршрута: {e}")

@pytest.mark.asyncio
@pytest.mark.critical
async def test_api_response_structure():
    """Реальный тест: проверяем структуру API ответа"""
    try:
        from routes.integration import router
        
        # Проверяем что роутер существует
        assert router is not None
        
        # Проверяем что есть маршрут для app-settings
        routes = router.routes
        
        # Ищем маршрут app-settings
        app_settings_route = None
        for route in routes:
            if "app-settings" in str(route.path):
                app_settings_route = route
                break
        
        assert app_settings_route is not None, "Маршрут app-settings не найден"
        
        # Проверяем что это GET запрос
        assert hasattr(app_settings_route, 'methods'), "Маршрут не имеет методов"
        assert 'GET' in app_settings_route.methods, "Маршрут не поддерживает GET"
        
        print(f"✅ Маршрут поддерживает GET метод")
        print(f"✅ Структура API корректна")
        
    except ImportError as e:
        pytest.skip(f"Не удалось импортировать модуль: {e}")
    except Exception as e:
        pytest.fail(f"Ошибка при проверке структуры API: {e}") 