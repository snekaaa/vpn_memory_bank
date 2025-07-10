"""
VPN Service Backend - Main Application
Включает API и админку с поддержкой множества нод
"""

import logging
import asyncio
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from config.database import get_db, get_db_session, init_database
from routes.admin_nodes import router as nodes_router
from routes.test_routes import router as test_router
from routes.integration import router as integration_router
from routes.payments import router as api_payments_router
from routes.users import router as api_users_router
from routes.plans import router as plans_router
from routes.webhooks import router as webhooks_router
from services.health_checker import HealthChecker
from app.admin.routes import router as admin_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаем FastAPI приложение
app = FastAPI(title="VPN Service", version="1.0.0")

# Настраиваем Jinja2 templates
templates = Jinja2Templates(directory=["backend/templates", "backend/app/templates"])

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Подключаем роутеры
app.include_router(admin_router)
app.include_router(nodes_router)
app.include_router(test_router)
app.include_router(integration_router, prefix="/api/v1")
app.include_router(api_payments_router, prefix="/api/v1")
app.include_router(api_users_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(plans_router)

# Период проверки здоровья нод (в секундах)
HEALTH_CHECK_INTERVAL = 300  # 5 минут

@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения"""
    # Инициализируем базу данных
    await init_database()
    
    # Запускаем задачу проверки здоровья нод
    asyncio.create_task(health_check_task())
    
    logger.info("🚀 VPN Service Backend запущен!")
    logger.info("📋 Загружены модули:")
    logger.info("  ✅ Admin Interface - интерфейс управления")
    logger.info("  ✅ Multi-Node - поддержка множества VPN нод")
    logger.info("  ✅ Health Checker - мониторинг здоровья нод")

async def health_check_task():
    """Периодическая проверка здоровья нод"""
    logger.info("🏥 Запущена задача проверки здоровья нод")
    
    while True:
        try:
            # Получаем сессию БД
            db = get_db_session()
            
            # Создаем экземпляр HealthChecker
            health_checker = HealthChecker(db)
            
            # Проверяем все ноды
            logger.info("🔍 Выполняем проверку здоровья всех нод...")
            results = await health_checker.check_all_nodes()
            
            # Логируем результаты
            healthy_nodes = sum(1 for r in results.values() if r.get('is_healthy', False))
            total_nodes = len(results)
            logger.info(f"✅ Проверка завершена: {healthy_nodes}/{total_nodes} нод здоровы")
            
            # Ждем до следующей проверки
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке здоровья нод: {e}")
            # В случае ошибки ждем немного и пробуем снова
            await asyncio.sleep(60)

@app.get("/", response_class=HTMLResponse)
async def admin_index(request: Request):
    """Главная страница админки"""
    return templates.TemplateResponse("admin/index.html", {
        "request": request,
        "title": "Панель управления"
    })

@app.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Дашборд с основной статистикой"""
    # Здесь будет собираться статистика из разных сервисов
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "title": "Дашборд"
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("admin/login.html", {
        "request": request,
        "title": "Вход в систему"
    })

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Обработка входа в систему"""
    # Здесь будет проверка учетных данных
    
    # Временное решение - принимаем любые учетные данные
    return RedirectResponse(url="/", status_code=303)

@app.get("/logout")
async def logout():
    """Выход из системы"""
    # Здесь будет логика выхода
    
    return RedirectResponse(url="/login", status_code=303)

@app.get("/health")
async def health_check():
    """Health check endpoint для Docker"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting VPN Service Backend...")
    print("📍 Access: http://localhost:8001")
    print("🔧 Components:")
    print("   - FastAPI: ✅")
    print("   - Jinja2: ✅") 
    print("   - Bootstrap 5: ✅")
    print("   - Chart.js: ✅")
    print("   - Node Management: ✅")
    
    uvicorn.run(app, host="0.0.0.0", port=8001) 