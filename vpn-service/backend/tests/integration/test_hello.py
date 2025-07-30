import pytest

@pytest.mark.asyncio
async def test_hello_world():
    """Минимальный async hello world тест"""
    awaitable = 42
    assert awaitable == 42 