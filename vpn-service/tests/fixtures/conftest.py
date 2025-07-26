import pytest
import httpx
import asyncio
from typing import AsyncGenerator

@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Фикстура для асинхронного HTTP клиента"""
    async with httpx.AsyncClient() as client:
        yield client

@pytest.fixture
def base_url() -> str:
    """Базовый URL для API тестов"""
    return "http://localhost:8000"

@pytest.fixture
def test_telegram_id() -> int:
    """Тестовый Telegram ID"""
    return 123456789

@pytest.fixture
def test_user_data() -> dict:
    """Тестовые данные пользователя"""
    return {
        "telegram_id": 123456789,
        "username": "test_user",
        "first_name": "Test",
        "last_name": "User"
    } 