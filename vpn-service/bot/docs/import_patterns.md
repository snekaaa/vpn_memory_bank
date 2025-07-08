# Import Patterns Documentation

## 📋 Правильные Import Patterns для VPN Bot

### ✅ Правильные Patterns

#### 1. Configuration Settings
```python
# ✅ ПРАВИЛЬНО
from config.settings import get_settings

settings = get_settings()
token = settings.telegram_bot_token
```

```python
# ❌ НЕПРАВИЛЬНО - приведет к ImportError
from config.settings import settings  # Не существует!
```

#### 2. Services Import
```python
# ✅ ПРАВИЛЬНО
from services.vless_service import VLESSService
from services.subscription_service import SubscriptionService

vless_service = VLESSService()
subscription_service = SubscriptionService()
```

#### 3. Handlers Import
```python
# ✅ ПРАВИЛЬНО
from handlers.subscription_handler import trial_subscription_handler
from handlers.menu_handler import menu_router
from handlers.start_handler import start_router
```

#### 4. Middleware Import
```python
# ✅ ПРАВИЛЬНО  
from middleware.auth_middleware import AuthMiddleware

auth = AuthMiddleware()
```

#### 5. Monitoring Import
```python
# ✅ ПРАВИЛЬНО
from monitoring_service import track_message, track_command, track_error
from monitoring_service import monitoring_service

# Или для specific components
from monitoring_service import MonitoringService, HealthChecker
```

---

## 🏗️ Архитектурные Patterns

### Dependency Injection Pattern
```python
# ✅ РЕКОМЕНДУЕМЫЙ PATTERN
class BotService:
    def __init__(self, settings=None, vless_service=None):
        self.settings = settings or get_settings()
        self.vless_service = vless_service or VLESSService()
    
    async def create_trial(self, telegram_id: int):
        # Используем injected dependencies
        return self.vless_service.generate_trial_vless_config(telegram_id, 1)
```

### Service Locator Pattern
```python
# ✅ АЛЬТЕРНАТИВНЫЙ PATTERN
class ServiceLocator:
    _instances = {}
    
    @classmethod
    def get_vless_service(cls):
        if 'vless' not in cls._instances:
            cls._instances['vless'] = VLESSService()
        return cls._instances['vless']
    
    @classmethod
    def get_subscription_service(cls):
        if 'subscription' not in cls._instances:
            cls._instances['subscription'] = SubscriptionService()
        return cls._instances['subscription']
```

---

## 🧪 Testing Import Patterns

### Mock Imports для Testing
```python
# ✅ ПРАВИЛЬНО для unit tests
from unittest.mock import Mock, patch

@patch('config.settings.get_settings')
def test_configuration(mock_get_settings):
    mock_settings = Mock()
    mock_settings.telegram_bot_token = "test_token"
    mock_get_settings.return_value = mock_settings
    
    # Тест logic здесь
```

### Conditional Imports
```python
# ✅ ПРАВИЛЬНО для optional dependencies
try:
    import structlog
    STRUCTURED_LOGGING = True
except ImportError:
    import logging
    STRUCTURED_LOGGING = False
```

---

## 🔍 Common Import Errors & Solutions

### Error 1: ImportError settings
```bash
ImportError: cannot import name 'settings' from 'config.settings'
```

**Solution:**
```python
# ❌ Неправильно
from config.settings import settings

# ✅ Правильно
from config.settings import get_settings
settings = get_settings()
```

### Error 2: Circular Import
```bash
ImportError: cannot import name 'X' from partially initialized module
```

**Solution:**
```python
# ❌ Проблема: circular import в module level
from handlers.menu_handler import menu_function

def my_function():
    return menu_function()

# ✅ Решение: import внутри функции
def my_function():
    from handlers.menu_handler import menu_function
    return menu_function()
```

### Error 3: Relative Import Issues
```bash
ImportError: attempted relative import with no known parent package
```

**Solution:**
```python
# ❌ Проблема: relative imports при direct execution
from .config.settings import get_settings

# ✅ Решение: absolute imports
from config.settings import get_settings
```

---

## 📦 Package Structure Awareness

### Current Project Structure
```
vpn-service/bot/
├── config/
│   ├── __init__.py
│   └── settings.py          # get_settings() функция
├── handlers/
│   ├── __init__.py         # Только imports, без logic
│   ├── start_handler.py
│   ├── menu_handler.py
│   └── subscription_handler.py
├── services/
│   ├── __init__.py
│   ├── vless_service.py
│   └── subscription_service.py
├── middleware/
│   ├── __init__.py
│   └── auth_middleware.py
├── monitoring_service.py    # Global monitoring
├── test_suite.py           # Comprehensive tests
└── main.py                 # Entry point
```

### Module Initialization
```python
# ✅ Правильная инициализация __init__.py
# handlers/__init__.py
from .start_handler import start_router
from .menu_handler import menu_router  
from .subscription_handler import subscription_router

__all__ = ['start_router', 'menu_router', 'subscription_router']
```

---

## 🚀 Production Import Patterns

### Environment-aware Imports
```python
# ✅ PRODUCTION PATTERN
import os

if os.getenv('ENVIRONMENT') == 'production':
    from monitoring_service import monitoring_service
    monitoring_service.start_monitoring()
else:
    # Mock monitoring for development
    class MockMonitoring:
        def track_message(self, *args): pass
        def track_command(self, *args): pass
    monitoring_service = MockMonitoring()
```

### Lazy Loading Pattern
```python
# ✅ LAZY LOADING для heavy dependencies
_vless_service = None

def get_vless_service():
    global _vless_service
    if _vless_service is None:
        from services.vless_service import VLESSService
        _vless_service = VLESSService()
    return _vless_service
```

---

## 🔧 Development Patterns

### Hot Reload Friendly Imports
```python
# ✅ HOT RELOAD PATTERN
def reload_services():
    """Reload services для development"""
    import importlib
    import services.vless_service
    import services.subscription_service
    
    importlib.reload(services.vless_service)
    importlib.reload(services.subscription_service)
```

### Debug Import Tracing
```python
# ✅ DEBUG PATTERN
import sys

def trace_imports():
    """Trace всех imports для debugging"""
    original_import = __builtins__.__import__
    
    def debug_import(name, *args, **kwargs):
        print(f"Importing: {name}")
        return original_import(name, *args, **kwargs)
    
    __builtins__.__import__ = debug_import
```

---

## 📋 Import Checklist

### Before Adding New Import
- [ ] Проверить что модуль существует
- [ ] Убедиться что нет circular dependencies
- [ ] Использовать absolute imports (не relative)
- [ ] Проверить что import работает в tests
- [ ] Документировать новые patterns

### Import Review Checklist
- [ ] Все imports используются
- [ ] Нет duplicate imports
- [ ] Imports сгруппированы логически
- [ ] Соблюден PEP 8 порядок imports
- [ ] Нет imports с side effects на module level

---

## 🎯 Best Practices Summary

1. **Always use absolute imports** в production коде
2. **Use get_settings() pattern** для configuration
3. **Avoid circular imports** через функциональные imports
4. **Group imports logically**: stdlib → 3rd party → local
5. **Use lazy loading** для heavy dependencies
6. **Test import patterns** в automated tests
7. **Document new patterns** когда добавляете complexity

---

## 🔍 Testing Import Patterns

### Automated Import Tests
```python
# test_imports.py
def test_configuration_import():
    """Тест правильного import pattern для configuration"""
    from config.settings import get_settings
    settings = get_settings()
    assert settings is not None

def test_services_import():
    """Тест import всех services"""
    from services.vless_service import VLESSService
    from services.subscription_service import SubscriptionService
    
    assert VLESSService is not None
    assert SubscriptionService is not None

def test_monitoring_import():
    """Тест monitoring imports"""
    from monitoring_service import track_message, monitoring_service
    
    assert callable(track_message)
    assert monitoring_service is not None
```

Эта документация поможет избежать import confusion и обеспечит consistent patterns во всем проекте. 