"""
Минималистичный тестовый роутер для отладки
"""

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["test_minimal"])

@router.get("/test-minimal")
async def test_minimal():
    """Простейший тест endpoint"""
    return {"message": "test minimal works", "status": "ok"}

@router.get("/test-minimal/db")
async def test_minimal_db():
    """Тест с database dependency"""
    try:
        from config.database import get_db
        return {"message": "db dependency works", "status": "ok"}
    except Exception as e:
        return {"message": f"db error: {str(e)}", "status": "error"}

@router.get("/test-minimal/models")
async def test_minimal_models():
    """Тест импорта models"""
    try:
        from models.payment_provider import PaymentProvider
        return {"message": "models import works", "status": "ok"}
    except Exception as e:
        return {"message": f"models error: {str(e)}", "status": "error"} 