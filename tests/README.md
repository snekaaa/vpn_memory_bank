# Тестирование VPN Memory Bank

Этот репозиторий содержит полный набор тестов для VPN Memory Bank проекта с использованием pytest и Allure для отчетности.

## 🚀 Быстрый старт

### Установка зависимостей

```bash
pip install pytest pytest-asyncio pytest-cov allure-pytest
```

### Запуск всех тестов

```bash
# Из корневой папки проекта
pytest tests/

# Или из папки tests
cd tests && pytest
```

## 📊 Структура тестов

```
tests/
├── integration/           # Интеграционные тесты
│   ├── test_hello.py     # Health checks и базовые тесты
│   ├── test_payments.py  # Тесты платежной системы
│   ├── test_webhooks.py  # Тесты webhook'ов
│   ├── test_e2e_user_journey.py  # E2E тесты пользователей
│   ├── test_user_dashboard.py    # Тесты dashboard
│   ├── test_app_settings.py      # Тесты настроек приложения
│   └── test_full_cycle.py        # Тесты полного цикла создания пользователя
├── allure-results/       # Результаты Allure тестов
├── htmlcov/             # HTML отчеты coverage
├── conftest.py          # Фикстуры и конфигурация
├── pytest.ini          # Конфигурация pytest
├── coverage.ini         # Конфигурация coverage
└── README.md           # Этот файл
```

## 🧪 Типы тестов

### По категориям
- **critical** - Критически важные тесты
- **integration** - Интеграционные тесты
- **e2e** - End-to-end тесты
- **mock** - Тесты с мок-данными
- **slow** - Медленные тесты

### По функциональности
- **payment** - Тесты платежей
- **webhook** - Тесты webhook'ов
- **dashboard** - Тесты пользовательского интерфейса
- **api** - Тесты API

## 🎯 Запуск конкретных тестов

### По маркерам

```bash
# Только критические тесты
pytest -m critical

# Только интеграционные тесты
pytest -m integration

# Исключить медленные тесты
pytest -m "not slow"

# Комбинирование маркеров
pytest -m "critical and not slow"
```

### По файлам

```bash
# Тесты платежей
pytest tests/integration/test_payments.py

# Тесты webhook'ов
pytest tests/integration/test_webhooks.py

# Конкретный тест
pytest tests/integration/test_hello.py::test_basic_health_check
```

### По паттернам

```bash
# Все тесты содержащие "payment" в названии
pytest -k "payment"

# Все тесты webhook'ов
pytest -k "webhook"

# Параметризованные тесты для конкретного провайдера
pytest -k "robokassa"
```

## 📈 Coverage отчеты

### Генерация отчетов

```bash
# HTML отчет (автоматически при запуске тестов)
pytest --cov=. --cov-report=html

# XML отчет для CI/CD
pytest --cov=. --cov-report=xml

# Консольный отчет
pytest --cov=. --cov-report=term-missing
```

### Просмотр HTML отчета

```bash
# После запуска тестов откройте
open tests/htmlcov/index.html
```

## 📋 Allure отчеты

### Генерация Allure отчетов

```bash
# Запуск тестов с генерацией Allure данных
pytest --alluredir=tests/allure-results

# Запуск Allure сервера для просмотра отчетов
allure serve tests/allure-results
```

### Установка Allure (если нужно)

```bash
# macOS
brew install allure

# Linux
sudo apt-get install allure

# Windows
scoop install allure
```

## 🔧 Конфигурация

### pytest.ini
- Маркеры для категоризации тестов
- Настройки логирования
- Конфигурация coverage
- Фильтры для warnings

### coverage.ini
- Исключения из анализа покрытия
- HTML и XML отчеты
- Пороги покрытия кода

### conftest.py
- Общие фикстуры для всех тестов
- Моковые данные
- Утилиты для генерации тестовых данных

## 🚦 CI/CD Integration

### GitHub Actions пример

```yaml
- name: Run tests
  run: |
    pytest tests/ --cov=. --cov-report=xml --alluredir=allure-results

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v1
  with:
    file: tests/coverage.xml
```

### Минимальные требования для прохождения

- **Coverage**: минимум 80%
- **Critical тесты**: должны проходить все
- **Время выполнения**: все тесты < 2 минуты

## 🐛 Отладка

### Подробный вывод

```bash
# Детальный вывод ошибок
pytest -vvv tests/

# Остановка на первой ошибке
pytest -x tests/

# Запуск последних упавших тестов
pytest --lf
```

### Логирование

```bash
# Включить логирование в консоль
pytest -s --log-cli-level=DEBUG
```

## 📝 Написание новых тестов

### Шаблон теста

```python
import pytest
import allure

@allure.epic("Feature Name")
@allure.feature("Specific Feature")
@pytest.mark.critical
@pytest.mark.integration
async def test_something():
    with allure.step("Description of step"):
        # Test implementation
        assert True
        
        allure.attach(
            "Test data",
            name="Test Result",
            attachment_type=allure.attachment_type.TEXT
        )
```

### Использование фикстур

```python
def test_with_fixtures(sample_user_data, sample_payment_data):
    user = sample_user_data
    payment = sample_payment_data
    
    assert user["telegram_id"] > 0
    assert payment["amount"] > 0
```

### Параметризация

```python
@pytest.mark.parametrize("provider,expected_url", [
    ("robokassa", "https://robokassa.ru"),
    ("freekassa", "https://freekassa.ru")
])
def test_payment_providers(provider, expected_url):
    assert expected_url in get_provider_url(provider)
```

## 🤝 Лучшие практики

1. **Именование**: Используйте описательные имена тестов
2. **Изоляция**: Каждый тест должен быть независимым
3. **Ассерты**: Используйте понятные assert сообщения
4. **Документация**: Добавляйте docstrings к тестам
5. **Маркеры**: Правильно категоризируйте тесты
6. **Фикстуры**: Переиспользуйте общие данные
7. **Аллюр**: Добавляйте степы и аттачменты для лучшей отчетности

## 🆘 Помощь

При возникновении проблем:

1. Проверьте установку зависимостей
2. Убедитесь в правильности путей
3. Просмотрите логи тестов
4. Проверьте конфигурацию pytest.ini

## 📞 Контакты

Для вопросов по тестированию обращайтесь к команде разработки.