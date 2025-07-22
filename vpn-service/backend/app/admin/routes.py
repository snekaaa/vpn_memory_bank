"""
Admin Routes для VPN Service
CRUD операции и веб-интерфейс
"""

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, String, case, text, delete, desc
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import structlog
import json
from pydantic import BaseModel

from config.database import get_db
from models.user import User
from models.vpn_key import VPNKey, VPNKeyStatus
from models.vpn_node import VPNNode, NodeMode
from models.user_node_assignment import UserNodeAssignment
# from models.subscription import Subscription, SubscriptionStatus  # Убрано - упрощенная архитектура
from models.payment import Payment, PaymentStatus
from models.payment_provider import (
    PaymentProvider, PaymentProviderType, PaymentProviderStatus
)
from models.auto_payment import AutoPayment
# NEW: Country management imports
from models.country import Country
from models.user_server_assignment import UserServerAssignment
from models.server_switch_log import ServerSwitchLog
from services.country_service import CountryService
from services.user_server_service import UserServerService
from services.x3ui_client import x3ui_client
from services.node_manager import NodeManager, NodeConfig
from services.load_balancer import LoadBalancer
from services.health_checker import HealthChecker
from services.x3ui_client_pool import X3UIClientPool

from services.payment_processor import payment_processor_manager
from services.payment_management_service import PaymentManagementService, get_payment_management_service
from services.trial_automation_service import TrialAutomationService, get_trial_automation_service
from services.auto_payment_service import AutoPaymentService
from .auth import admin_auth, get_current_admin, optional_admin
from .schemas import (
    AdminLoginRequest, AdminLoginResponse, UserListResponse, 
    VPNKeyListResponse, DashboardStats, UserUpdateRequest
)

# Manual Payment Management Schemas
class ManualPaymentCreateRequest(BaseModel):
    user_id: int
    amount: float
    description: str
    payment_method: str  # manual_admin, manual_trial, manual_correction
    subscription_days: Optional[int] = None  # Количество дней подписки
    metadata: Optional[Dict[str, Any]] = None

class PaymentStatusUpdateRequest(BaseModel):
    new_status: str  # PENDING, SUCCEEDED, FAILED, CANCELLED
    reason: Optional[str] = None

class UserPaymentHistoryResponse(BaseModel):
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    telegram_id: int
    payments: List[Dict[str, Any]]
    total_payments: int
    total_amount: float
# Import will be added after router creation
from services.node_automation import (
    NodeAutomationService, 
    NodeDeploymentConfig, 
    DeploymentMethod
)

# NEW: User deletion service import
from services.user_deletion_service import (
    UserDeletionService, 
    get_user_deletion_service,
    DeletionResult,
    KeyDeletionResult
)

# Создаем роутер
router = APIRouter(prefix="/admin", tags=["admin"])

# Настройка templates
templates = Jinja2Templates(directory=["app/templates"])

# Настройка логгера
logger = structlog.get_logger(__name__)

async def get_template_context(request, db: AsyncSession, **kwargs):
    """Получить базовый контекст для всех шаблонов с настройками сайта"""
    try:
        from services.app_settings_service import AppSettingsService
        app_settings = await AppSettingsService.get_settings(db)
        
        base_context = {
            "request": request,
            "site_name": app_settings.site_name,
            "site_domain": app_settings.site_domain,
            "site_description": app_settings.site_description,
        }
        base_context.update(kwargs)
        return base_context
    except Exception as e:
        logger.error("Error getting template context", error=str(e))
        # Fallback к базовому контексту
        base_context = {
            "request": request,
            "site_name": "VPN Service",
            "site_domain": None,
            "site_description": None,
        }
        base_context.update(kwargs)
        return base_context


# =============================================================================
# PYDANTIC МОДЕЛИ ДЛЯ ПЛАТЕЖНЫХ ПРОВАЙДЕРОВ
# =============================================================================

class PaymentProviderCreate(BaseModel):
    name: str
    provider_type: PaymentProviderType
    description: Optional[str] = None
    is_active: bool = False
    is_test_mode: bool = True
    is_default: bool = False
    config: Dict[str, Any] = {}
    webhook_url: Optional[str] = None
    priority: int = 100

    # Новые поля для FreeKassa интеграции
    min_amount: Optional[float] = 1.0
    max_amount: Optional[float] = 100000.0
    commission_percent: Optional[float] = 0.0
    commission_fixed: Optional[float] = 0.0
    success_url: Optional[str] = None
    failure_url: Optional[str] = None
    notification_url: Optional[str] = None
    notification_method: Optional[str] = "POST"


class PaymentProviderUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_test_mode: Optional[bool] = None
    is_default: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = None
    priority: Optional[int] = None
    
    # Новые поля для FreeKassa интеграции
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    commission_percent: Optional[float] = None
    commission_fixed: Optional[float] = None
    success_url: Optional[str] = None
    failure_url: Optional[str] = None
    notification_url: Optional[str] = None
    notification_method: Optional[str] = None


class PaymentProviderResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    status: str
    is_active: bool
    is_test_mode: bool
    is_default: bool
    description: Optional[str]
    webhook_url: Optional[str]
    priority: int
    
    # Новые поля для FreeKassa интеграции
    min_amount: Optional[float]
    max_amount: Optional[float]
    commission_percent: Optional[float]
    commission_fixed: Optional[float]
    success_url: Optional[str]
    failure_url: Optional[str]
    notification_url: Optional[str]
    notification_method: Optional[str]
    
    # Статистика
    total_payments: int
    successful_payments: int
    failed_payments: int
    total_amount: float
    success_rate: float
    is_healthy: bool
    created_at: datetime
    updated_at: datetime
    masked_config: Dict[str, Any]

    class Config:
        from_attributes = True


class PaymentProviderDashboardStats(BaseModel):
    total_providers: int
    active_providers: int
    total_payments_today: int
    total_amount_today: float
    success_rate_today: float

@router.get("/", response_class=HTMLResponse)
async def admin_root(request: Request, current_admin: Optional[str] = Depends(optional_admin)):
    """Главная страница админки - перенаправление на dashboard или login"""
    if current_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    else:
        return RedirectResponse(url="/admin/login", status_code=302)

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, current_admin: Optional[str] = Depends(optional_admin)):
    """Страница входа в админку"""
    if current_admin:
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    
    return templates.TemplateResponse("admin/login.html", {
        "request": request,
        "title": "Admin Login"
    })

@router.post("/login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Обработка входа в админку"""
    if not admin_auth.verify_password(username, password):
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "title": "Admin Login",
            "error": "Неверные учетные данные"
        }, status_code=401)
    
    # Создаем сессию
    session_id = admin_auth.create_session(username)
    
    # Создаем redirect response с cookie
    response = RedirectResponse(url="/admin/dashboard", status_code=302)
    response.set_cookie(
        key="admin_session",
        value=session_id,
        max_age=8 * 60 * 60,  # 8 часов
        httponly=True,
        secure=False,  # В продакшене True
        samesite="lax"
    )
    
    return response

@router.post("/logout")
async def admin_logout(request: Request):
    """Выход из админки"""
    session_id = request.cookies.get("admin_session")
    if session_id:
        admin_auth.destroy_session(session_id)
    
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_session")
    return response

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request, 
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Главная страница админки с статистикой"""
    
    # Собираем статистику
    stats = await get_dashboard_stats(db)
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "title": "Admin Dashboard",
        "current_admin": current_admin,
        "stats": stats
    })

@router.get("/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    page: int = 1,
    size: int = 50,
    search: Optional[str] = None,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница управления пользователями"""
    
    users_data = await get_users_paginated(db, page, size, search)
    
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "title": "Users Management",
        "current_admin": current_admin,
        "users_data": users_data,
        "search": search or ""
    })

@router.get("/vpn-keys", response_class=HTMLResponse)
async def admin_vpn_keys_page(
    request: Request,
    page: int = 1,
    size: int = 50,
    status: Optional[str] = None,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница управления VPN ключами"""
    
    keys_data = await get_vpn_keys_paginated(db, page, size, status)
    
    return templates.TemplateResponse("admin/vpn_keys.html", {
        "request": request,
        "title": "VPN Keys Management",
        "current_admin": current_admin,
        "keys_data": keys_data,
        "status_filter": status or ""
    })

# API эндпоинты для AJAX операций
@router.patch("/api/users/{user_id}")
async def update_user(
    user_id: int,
    update_data: UserUpdateRequest,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Обновление пользователя"""
    
    # Находим пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Обновляем поля
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
    if update_data.is_blocked is not None:
        user.is_blocked = update_data.is_blocked
    
    user.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "User updated successfully", "user_id": user_id}

@router.post("/api/users/{user_id}/cancel-autopay")
async def cancel_user_autopay(
    user_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Отключение автоплатежа пользователя администратором"""
    
    # Находим пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Используем AutoPaymentService для отключения автоплатежа
    auto_payment_service = AutoPaymentService(db)
    cancel_result = await auto_payment_service.cancel_auto_payment(user_id)
    
    if cancel_result['success']:
        return {"success": True, "message": "Автоплатеж успешно отключен"}
    else:
        raise HTTPException(
            status_code=400, 
            detail=cancel_result.get('message', 'Ошибка при отключении автоплатежа')
        )

# Роут для перегенерации VPN ключей удален согласно требованиям

@router.post("/api/generate-real-vless")
async def generate_real_vless_config(
    request: Request,
    current_admin: str = Depends(get_current_admin)
):
    """Генерация реальной VLESS конфигурации для тестирования"""
    
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        node_host = data.get("node_host")  # Убран хардкод - хост обязателен
        node_port = data.get("node_port", 443)  # Изменен порт на 443 (стандартный для Reality)
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="telegram_id is required")
        
        if not node_host:
            raise HTTPException(status_code=400, detail="node_host is required")
        
        from services.vless_generator import vless_generator
        
        # Генерируем VLESS конфигурацию
        vless_config = vless_generator.generate_vless_for_node(
            node_host=node_host,
            node_port=node_port,
            alias=f"VPN-Admin-Test-{telegram_id}"
        )
        
        return {
            "success": True,
            "message": "Реальная VLESS конфигурация сгенерирована",
            "config": vless_config,
            "instructions": {
                "client_setup": "Скопируйте VLESS URL в ваш VPN клиент",
                "supported_clients": ["V2RayN", "Clash", "SagerNet", "V2RayNG"]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating VLESS config: {str(e)}")

# Вспомогательные функции
async def get_dashboard_stats(db: AsyncSession) -> DashboardStats:
    """Получение статистики для дашборда"""
    
    # Общее количество пользователей
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar()
    
    # Активные пользователи
    active_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True, User.is_blocked == False)
    )
    active_users = active_users_result.scalar()
    
    # Заблокированные пользователи
    blocked_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_blocked == True)
    )
    blocked_users = blocked_users_result.scalar()
    
    # VPN ключи
    total_keys_result = await db.execute(select(func.count(VPNKey.id)))
    total_vpn_keys = total_keys_result.scalar()
    
    active_keys_result = await db.execute(
        select(func.count(VPNKey.id)).where(VPNKey.status == "active")
    )
    active_vpn_keys = active_keys_result.scalar()
    
    # Трафик (в ГБ)
    traffic_result = await db.execute(
        select(func.sum(VPNKey.total_download + VPNKey.total_upload))
    )
    total_traffic_bytes = traffic_result.scalar() or 0
    total_traffic_gb = round(total_traffic_bytes / (1024**3), 2)
    
    # Статистика за последние 24 часа
    yesterday = datetime.utcnow() - timedelta(hours=24)
    
    recent_registrations_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= yesterday)
    )
    recent_registrations = recent_registrations_result.scalar()
    
    recent_connections_result = await db.execute(
        select(func.count(VPNKey.id)).where(VPNKey.last_connection >= yesterday)
    )
    recent_connections = recent_connections_result.scalar()
    
    # Упрощенная архитектура - статистика активных аккаунтов пользователей
    active_accounts_result = await db.execute(
        text("SELECT COUNT(id) FROM users WHERE subscription_status = 'active' AND valid_until > NOW()")
    )
    active_accounts = active_accounts_result.scalar() or 0
    
    expired_accounts_result = await db.execute(
        text("SELECT COUNT(id) FROM users WHERE subscription_status = 'active' AND valid_until <= NOW()")
    )
    expired_accounts = expired_accounts_result.scalar() or 0
    
    # Статистика по платежам
    total_payments_result = await db.execute(select(func.count(Payment.id)))
    total_payments = total_payments_result.scalar() or 0
    
    completed_payments_result = await db.execute(
        select(func.count(Payment.id)).where(Payment.status == PaymentStatus.SUCCEEDED)
    )
    completed_payments = completed_payments_result.scalar() or 0
    
    # Сумма завершенных платежей
    total_revenue_result = await db.execute(
        select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.SUCCEEDED)
    )
    total_revenue = total_revenue_result.scalar() or 0
    
    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        blocked_users=blocked_users,
        total_vpn_keys=total_vpn_keys,
        active_vpn_keys=active_vpn_keys,
        total_traffic_gb=total_traffic_gb,
        recent_registrations=recent_registrations,
        recent_connections=recent_connections,
        active_accounts=active_accounts,
        expired_accounts=expired_accounts,
        total_payments=total_payments,
        completed_payments=completed_payments,
        total_revenue=total_revenue
    )

def get_subscription_display(user) -> str:
    """Получить читаемое отображение статуса подписки"""
    from datetime import datetime, timezone
    
    if user.subscription_status == "none":
        return "Нет подписки"
    
    if user.subscription_status != "active":
        return f"Статус: {user.subscription_status}"
    
    if not user.valid_until:
        return "Активная (бессрочная)"
    
    now = datetime.now(timezone.utc)
    if user.valid_until <= now:
        return "Истекла"
    
    # Вычисляем дни
    delta = user.valid_until - now
    days = delta.days
    
    if days == 0:
        hours = delta.seconds // 3600
        return f"Истекает через {hours}ч"
    elif days == 1:
        return "Истекает завтра"
    else:
        return f"Осталось {days} дней"

async def get_users_paginated(db: AsyncSession, page: int = 1, size: int = 50, search: Optional[str] = None):
    """Получение пользователей с пагинацией"""
    offset = (page - 1) * size
    
    # Базовый запрос (упрощенная архитектура - без загрузки подписок)
    base_query = select(User)
    count_query = select(func.count(User.id))
    
    # Добавляем поиск если есть
    if search:
        search_filter = (
            User.username.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%") |
            func.cast(User.telegram_id, String).ilike(f"%{search}%")
        )
        base_query = base_query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # Получаем общее количество
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Получаем пользователей с подписками
    result = await db.execute(
        base_query
        .offset(offset)
        .limit(size)
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    
    # Получаем данные активности из X3UI
    x3ui_activity_data = await get_x3ui_user_activity()
    
    # Формируем ответ
    user_items = []
    for user in users:
        # Получаем количество АКТИВНЫХ VPN ключей пользователя (упрощенная архитектура)
        vpn_keys_count_result = await db.execute(
            select(func.count(VPNKey.id)).where(
                VPNKey.user_id == user.id,
                VPNKey.status == "active"
            )
        )
        vpn_keys_count = vpn_keys_count_result.scalar()
        
        # Ищем данные активности пользователя в X3UI
        x3ui_activity = x3ui_activity_data.get(str(user.telegram_id))
        
        # Определяем последнюю активность
        last_activity = user.last_activity
        if x3ui_activity and x3ui_activity.get("last_connection"):
            x3ui_last_activity = x3ui_activity["last_connection"]
            # Используем более свежую дату
            if not last_activity or x3ui_last_activity > last_activity:
                last_activity = x3ui_last_activity
                # Обновляем в базе данных
                user.last_activity = last_activity
                
        user_items.append({
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "is_blocked": user.is_blocked,
            "created_at": user.created_at,
            "last_activity": last_activity,
            "vpn_keys_count": vpn_keys_count,
            # Упрощенная архитектура - показываем информацию о подписке
            "subscription_info": get_subscription_display(user),
            "x3ui_status": x3ui_activity.get("status", "unknown") if x3ui_activity else "unknown",
            "subscription_status": user.subscription_status if user.subscription_status else "none",
            "valid_until": user.valid_until.isoformat() if user.valid_until else None
        })
    
    # Сохраняем обновления активности
    await db.commit()
    
    return {
        "items": user_items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }

async def get_vpn_keys_paginated(db: AsyncSession, page: int = 1, size: int = 50, status: Optional[str] = None):
    """Получение VPN ключей с пагинацией (только из БД, без X3UI)"""
    offset = (page - 1) * size
    
    # Базовый запрос с join к пользователям и нодам
    base_query = select(VPNKey, User, VPNNode).join(User, VPNKey.user_id == User.id, isouter=True).join(VPNNode, VPNKey.node_id == VPNNode.id, isouter=True)
    count_query = select(func.count(VPNKey.id))
    
    # Фильтр по статусу
    if status and status in ["active", "inactive", "suspended", "expired", "revoked"]:
        status_filter = VPNKey.status == status
        base_query = base_query.where(status_filter)
        count_query = count_query.where(status_filter)
    
    # Получаем общее количество
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Получаем ключи с пользователями и нодами
    result = await db.execute(
        base_query
        .offset(offset)
        .limit(size)
        .order_by(VPNKey.created_at.desc())
    )
    rows = result.all()
    
    # Формируем ответ (только данные из БД)
    key_items = []
    for vpn_key, user, node in rows:
        total_bytes = vpn_key.total_download + vpn_key.total_upload
        up = vpn_key.total_upload
        down = vpn_key.total_download
        node_info = {}
        if node:
            node_info = {
                "id": node.id,
                "name": node.name,
                "priority": node.priority,
                "status": node.status,
                "location": node.location,
            }
        key_items.append({
            "id": vpn_key.id,
            "user_id": vpn_key.user_id,
            "key_name": vpn_key.key_name,
            "status": vpn_key.status,
            "created_at": vpn_key.created_at,
            "expires_at": vpn_key.expires_at,
            "total_download": down,
            "total_upload": up,
            "last_connection": vpn_key.last_connection,
            "user_telegram_id": user.telegram_id if user else None,
            "user_username": user.username if user else None,
            "traffic_gb": round(total_bytes / (1024**3), 2),
            "vless_url": vpn_key.vless_url,
            "node_info": node_info,
            "client_email": vpn_key.xui_email,
            "client_id": vpn_key.xui_client_id,
        })
    return {
        "items": key_items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }

async def get_x3ui_user_activity() -> Dict[str, Dict]:
    """Получение данных активности пользователей из X3UI панели"""
    try:
        # Получаем список inbound правил
        inbounds = await x3ui_client.get_inbounds()
        if not inbounds:
            return {}
        
        activity_data = {}
        
        for inbound in inbounds:
            try:
                # Парсим настройки клиентов
                import json
                settings = json.loads(inbound.get('settings', '{}'))
                clients = settings.get('clients', [])
                
                # Получаем статистику клиентов
                client_stats = inbound.get('clientStats', [])
                
                for client in clients:
                    client_email = client.get('email', '')
                    client_id = client.get('id', '')
                    tg_id = client.get('tgId', '')
                    
                    # Извлекаем telegram_id из email если tgId не указан
                    if not tg_id and client_email:
                        # Пробуем различные форматы
                        import re
                        
                        # Формат: telegram_id (@username)
                        match = re.search(r'^(\d{8,})\s*\(', client_email)
                        if not match:
                            # Формат: tg_XXXXXX_username
                            match = re.search(r'tg_(\d{8,})_', client_email)
                        if not match:
                            # Просто число в начале
                            match = re.search(r'^(\d{8,})', client_email)
                        if not match:
                            # Любое число 8+ символов в email
                            match = re.search(r'(\d{8,})', client_email)
                        
                        if match:
                            tg_id = match.group(1)
                    
                    if tg_id:
                        # Находим статистику для этого клиента
                        stats = next((s for s in client_stats if s.get('email') == client_email), {})
                        
                        # Рассчитываем общий трафик в ГБ
                        up_traffic = stats.get('up', 0)
                        down_traffic = stats.get('down', 0)
                        total_traffic_bytes = up_traffic + down_traffic
                        traffic_gb = round(total_traffic_bytes / (1024**3), 2)
                        
                        # Определяем статус (активен/неактивен)
                        is_enabled = client.get('enable', False)
                        expiry_time = client.get('expiryTime', 0)
                        is_expired = expiry_time > 0 and datetime.utcnow().timestamp() * 1000 > expiry_time
                        
                        status = "active" if is_enabled and not is_expired else "inactive"
                        
                        # Определяем последнюю активность
                        # X3UI не предоставляет точную дату последнего подключения,
                        # но если есть трафик, значит было подключение
                        last_connection = None
                        if total_traffic_bytes > 0:
                            # Если есть трафик, считаем что последняя активность была недавно
                            # Это приблизительная оценка
                            last_connection = datetime.utcnow() - timedelta(hours=1)
                        
                        activity_data[tg_id] = {
                            "status": status,
                            "traffic_gb": traffic_gb,
                            "up_traffic": up_traffic,
                            "down_traffic": down_traffic,
                            "last_connection": last_connection,
                            "is_enabled": is_enabled,
                            "is_expired": is_expired,
                            "inbound_id": inbound.get('id'),
                            "client_id": client_id,
                            "email": client_email
                        }
                        
            except Exception as e:
                # Логируем ошибку, но продолжаем обработку других inbound
                print(f"Error processing inbound {inbound.get('id', 'unknown')}: {e}")
                continue
        
        return activity_data
        
    except Exception as e:
        print(f"Error getting X3UI user activity: {e}")
        return {}

@router.get("/nodes", response_class=HTMLResponse)
async def admin_nodes_page(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница управления VPN нодами"""
    
    # Инициализируем NodeManager
    node_manager = NodeManager(db)
    
    try:
        # Получаем все ноды
        nodes = await node_manager.get_nodes(include_assignments=True)
        
        # Получаем статистику
        load_balancer = LoadBalancer(db)
        load_stats = await load_balancer.get_node_load_stats()
        
        # Создаем отчет о здоровье системы
        total_nodes = len(nodes) if nodes else 0
        healthy_nodes = sum(1 for node in nodes if node.health_status == "healthy") if nodes else 0
        unhealthy_nodes = sum(1 for node in nodes if node.health_status == "unhealthy") if nodes else 0
        active_nodes = sum(1 for node in nodes if node.status == "active") if nodes else 0
        total_users = sum(node.current_users for node in nodes) if nodes else 0
        total_capacity = sum(node.max_users for node in nodes) if nodes else 0
        
        health_report = {
            "total_nodes": total_nodes,
            "healthy_nodes": healthy_nodes,
            "unhealthy_nodes": unhealthy_nodes,
            "active_nodes": active_nodes,
            "total_users": total_users,
            "total_capacity": total_capacity,
            "load_percentage": (total_users / total_capacity * 100) if total_capacity > 0 else 0
        }
        
        # Проверяем наличие старого шаблона для обратной совместимости
        try:
            return templates.TemplateResponse("admin/nodes/list.html", {
                "request": request,
                "title": "VPN Nodes Management",
                "current_admin": current_admin,
                "nodes": nodes or [],
                "load_stats": load_stats,
                "health_report": health_report
            })
        except Exception:
            # Если новый шаблон недоступен, используем старый
            return templates.TemplateResponse("admin/nodes.html", {
                "request": request,
                "title": "VPN Nodes Management",
                "current_admin": current_admin,
                "nodes": nodes or [],
                "load_stats": load_stats,
                "health_report": health_report
            })
    except Exception as e:
        # Логируем ошибку
        print(f"Error loading nodes page: {str(e)}")
        
        try:
            # Сначала пробуем новый шаблон
            return templates.TemplateResponse("admin/nodes/list.html", {
                "request": request,
                "title": "VPN Nodes Management",
                "current_admin": current_admin,
                "nodes": [],
                "load_stats": [],
                "health_report": {
                    "total_nodes": 0,
                    "healthy_nodes": 0,
                    "unhealthy_nodes": 0,
                    "active_nodes": 0,
                    "total_users": 0,
                    "total_capacity": 0,
                    "load_percentage": 0
                },
                "error": f"Error loading nodes: {str(e)}"
            })
        except Exception:
            # Затем старый шаблон если новый недоступен
            return templates.TemplateResponse("admin/nodes.html", {
                "request": request,
                "title": "VPN Nodes Management",
                "current_admin": current_admin,
                "nodes": [],
                "load_stats": [],
                "health_report": {
                    "total_nodes": 0,
                    "healthy_nodes": 0,
                    "unhealthy_nodes": 0,
                    "active_nodes": 0,
                    "total_users": 0,
                    "total_capacity": 0,
                    "load_percentage": 0
                },
                "error": f"Error loading nodes: {str(e)}"
            })

@router.get("/nodes/create", response_class=HTMLResponse)
async def admin_create_node_page(
    request: Request,
    current_admin: str = Depends(get_current_admin)
):
    """Страница создания новой ноды"""
    
    try:
        # Пробуем сначала новый шаблон
        return templates.TemplateResponse("admin/nodes/create.html", {
            "request": request,
            "title": "Create New Node",
            "current_admin": current_admin
        })
    except Exception:
        # При ошибке используем старый шаблон
        return templates.TemplateResponse("admin/node_create.html", {
            "request": request,
            "title": "Create New Node",
            "current_admin": current_admin
        })

@router.post("/nodes/create")
async def admin_create_node(
    request: Request,
    name: str = Form(...),
    x3ui_url: str = Form(...),
    x3ui_username: str = Form(...),
    x3ui_password: str = Form(...),
    location: str = Form(""),
    description: str = Form(""),
    max_users: int = Form(1000),
    priority: int = Form(100),
    weight: float = Form(1.0),
    # Reality настройки
    reality_port: int = Form(443),
    sni_mask: str = Form("apple.com"),
    create_inbound: bool = Form(True),
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Обработка создания новой ноды с автоматическим созданием Reality inbound"""
    
    # Инициализируем NodeManager
    node_manager = NodeManager(db)
    
    # Создаем конфигурацию
    config = NodeConfig(
        name=name,
        x3ui_url=x3ui_url,
        x3ui_username=x3ui_username,
        x3ui_password=x3ui_password,
        description=description,
        location=location,
        max_users=max_users,
        priority=priority,
        weight=weight
    )
    
    # Создаем ноду
    node = await node_manager.create_node(config)
    
    if not node:
        # Напрямую используем новый шаблон без try/except
        return templates.TemplateResponse("admin/nodes/create.html", {
            "request": request,
            "title": "Добавить VPN Ноду",
            "current_admin": current_admin,
            "error": "Не удалось создать ноду. Проверьте подключение к X3UI."
        }, status_code=400)
    
    # НОВОЕ: Автоматически создаем Reality inbound после создания ноды
    inbound_success = False
    if create_inbound:
        try:
            from services.reality_inbound_service import RealityInboundService
            
            logger.info("Creating Reality inbound for manually created node", 
                       node_id=node.id, 
                       node_name=node.name,
                       port=reality_port,
                       sni_mask=sni_mask)
            
            # Создаем Reality inbound через универсальный сервис
            inbound_success = await RealityInboundService.create_reality_inbound(
                node=node,
                port=reality_port,
                sni_mask=sni_mask,
                remark=f"Manual-Reality-{node.name}"
            )
            
            if inbound_success:
                logger.info("Reality inbound created successfully for manual node", 
                           node_id=node.id)
                
                # Обновляем ноду с Reality параметрами
                try:
                    from models.vpn_node import NodeMode
                    node.mode = NodeMode.reality
                    node.sni_mask = sni_mask
                    await db.commit()
                    await db.refresh(node)
                except Exception as e:
                    logger.warning("Failed to update node with Reality mode", 
                                  node_id=node.id, 
                                  error=str(e))
            else:
                logger.warning("Failed to create Reality inbound for manual node", 
                              node_id=node.id)
                
        except Exception as e:
            logger.error("Error creating Reality inbound for manual node", 
                        node_id=node.id, 
                        error=str(e))
    
    # Перенаправляем на страницу ноды с информацией о статусе inbound'а
    if create_inbound and not inbound_success:
        # Добавляем параметр в URL для отображения warning
        return RedirectResponse(url=f"/admin/nodes/{node.id}?inbound_warning=1", status_code=302)
    
    return RedirectResponse(url=f"/admin/nodes/{node.id}", status_code=302)

@router.get("/nodes/{node_id}", response_class=HTMLResponse)
async def admin_node_detail_page(
    node_id: int,
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Детальная страница ноды"""
    
    try:
        # Получаем ноду напрямую из БД
        node_result = await db.execute(
            select(VPNNode).where(VPNNode.id == node_id)
        )
        node = node_result.scalar_one_or_none()
        
        if not node:
            logger.warning("Node not found", node_id=node_id)
            return RedirectResponse(url="/admin/nodes", status_code=302)
        
        # Получаем пользователей на этой ноде
        try:
            result = await db.execute(
                select(User)
                .join(UserServerAssignment, User.telegram_id == UserServerAssignment.user_id)
                .where(UserServerAssignment.node_id == node_id)
                .order_by(User.created_at.desc())
            )
            users = result.scalars().all()
        except Exception as user_error:
            logger.warning("Error loading users for node", node_id=node_id, error=str(user_error))
            users = []
        
        logger.info("Loading node view page", node_id=node_id, node_name=node.name, users_count=len(users))
        
        # Преобразуем ноду в словарь чтобы избежать ленивой загрузки в шаблоне  
        node_dict = {
            "id": node.id,
            "name": node.name,
            "location": node.location,
            "status": node.status,
            "priority": node.priority,
            "x3ui_url": node.x3ui_url,
            "x3ui_username": node.x3ui_username,
            "x3ui_password": node.x3ui_password,
            "description": node.description,
            "weight": node.weight,
            "response_time_ms": node.response_time_ms,
            "created_at": node.created_at,
            "updated_at": node.updated_at,
            "last_health_check": node.last_health_check,
            "health_status": getattr(node, 'health_status', 'unknown'),
            "current_users": getattr(node, 'current_users', 0),
            "max_users": getattr(node, 'max_users', 1000),
            # Вычисляем load_percentage заранее
            "load_percentage": (getattr(node, 'current_users', 0) / getattr(node, 'max_users', 1000)) * 100 if getattr(node, 'max_users', 1000) > 0 else 0,
            # Убираем user_assignments чтобы избежать ленивой загрузки
            "user_assignments": []
        }
        
        # Отображаем шаблон
        return templates.TemplateResponse("admin/nodes/view.html", {
            "request": request,
            "title": f"Node: {node.name}",
            "current_admin": current_admin,
            "node": node_dict,
            "users": users
        })
        
    except Exception as e:
        logger.error("Error loading node view page", node_id=node_id, error=str(e))
        # При ошибке перенаправляем на список нод
        return RedirectResponse(url="/admin/nodes", status_code=302)

@router.get("/nodes/{node_id}/node_dashboard")
async def admin_node_client_dashboard(
    node_id: int,
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница управления клиентами ноды"""
    try:
        # Получаем ноду из базы данных
        node_result = await db.execute(select(VPNNode).where(VPNNode.id == node_id))
        node = node_result.scalar_one_or_none()
        
        if not node:
            raise HTTPException(status_code=404, detail="Нода не найдена")
        
        return templates.TemplateResponse(
            "admin/nodes/node_dashboard.html",
            {
                "request": request,
                "admin": current_admin,
                "node": node
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы управления клиентами: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

@router.get("/nodes/{node_id}/edit", response_class=HTMLResponse)
async def admin_edit_node_page(
    node_id: int,
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница редактирования ноды"""
    
    # Инициализируем NodeManager
    node_manager = NodeManager(db)
    
    # Получаем ноду
    node = await node_manager.get_node_by_id(node_id)
    
    if not node:
        return RedirectResponse(url="/admin/nodes", status_code=302)
    
    try:
        # Получаем список стран для выпадающего списка
        countries_result = await db.execute(select(Country).order_by(Country.priority.desc(), Country.name))
        countries = countries_result.scalars().all()
        
        # Пробуем сначала новый шаблон
        return templates.TemplateResponse("admin/nodes/edit.html", {
            "request": request,
            "title": f"Edit Node: {node.name}",
            "current_admin": current_admin,
            "node": node,
            "countries": countries  # NEW: Передаем страны в template
        })
    except Exception:
        # При ошибке используем старый шаблон если он существует
        # Предполагаем что старый шаблон может не существовать, поэтому перенаправляем на список
        return RedirectResponse(url="/admin/nodes", status_code=302)

@router.post("/nodes/{node_id}/edit")
async def admin_update_node(
    node_id: int,
    request: Request,
    name: str = Form(...),
    x3ui_url: str = Form(...),
    x3ui_username: str = Form(...),
    x3ui_password: str = Form(...),
    location: str = Form(""),
    description: str = Form(""),
    max_users: int = Form(1000),
    priority: int = Form(100),
    weight: float = Form(1.0),
    status: str = Form("active"),
    country_id: Optional[int] = Form(None),  # NEW: Country assignment
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Обработка обновления ноды"""
    
    # Инициализируем NodeManager
    node_manager = NodeManager(db)
    
    # Создаем словарь обновлений
    updates = {
        "name": name,
        "x3ui_url": x3ui_url,
        "x3ui_username": x3ui_username,
        "x3ui_password": x3ui_password,
        "location": location,
        "description": description,
        "max_users": max_users,
        "priority": priority,
        "weight": weight,
        "status": status,
        "country_id": country_id if country_id else None  # NEW: Add country assignment
    }
    
    # Обновляем ноду
    node = await node_manager.update_node(node_id, updates)
    
    if not node:
        try:
            # Пробуем сначала новый шаблон
            return templates.TemplateResponse("admin/nodes/edit.html", {
                "request": request,
                "title": f"Edit Node: {name}",
                "current_admin": current_admin,
                "error": "Failed to update node."
            }, status_code=400)
        except Exception:
            # При ошибке перенаправляем на список нод
            return RedirectResponse(url="/admin/nodes", status_code=302)
    
    return RedirectResponse(url=f"/admin/nodes/{node.id}", status_code=302)

@router.post("/nodes/{node_id}/delete")
async def admin_delete_node(
    node_id: int,
    migrate_users: bool = Form(True),
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Удаление ноды"""
    
    # Инициализируем NodeManager
    node_manager = NodeManager(db)
    
    # Удаляем ноду
    success = await node_manager.delete_node(node_id, migrate_users)
    
    if not success:
        return JSONResponse(
            content={"success": False, "message": "Failed to delete node"},
            status_code=400
        )
    
    return RedirectResponse(url="/admin/nodes", status_code=302)

@router.post("/nodes/{node_id}/test")
async def admin_test_node_connection(
    node_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Тестирование подключения к ноде"""
    
    # Инициализируем NodeManager
    node_manager = NodeManager(db)
    
    # Тестируем подключение
    success = await node_manager.test_node_connection(node_id)
    
    return JSONResponse(
        content={"success": success}
    )

@router.post("/nodes/{node_id}/test-connection")
async def admin_test_node_connection_alt(
    node_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Тестирование подключения к ноде (альтернативный путь для шаблонов)"""
    
    # Инициализируем NodeManager
    node_manager = NodeManager(db)
    
    # Тестируем подключение
    success = await node_manager.test_node_connection(node_id)
    
    return JSONResponse(
        content={"success": success}
    )

@router.get("/nodes/health", response_class=HTMLResponse)
async def admin_nodes_health_page(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница мониторинга здоровья нод"""
    
    # Инициализируем HealthChecker
    health_checker = HealthChecker(db)
    
    # Получаем отчет о здоровье
    health_report = await health_checker.get_health_report()
    
    try:
        # Пробуем сначала новый шаблон, если он существует
        return templates.TemplateResponse("admin/nodes/health.html", {
            "request": request,
            "title": "VPN Nodes Health",
            "current_admin": current_admin,
            "health_report": health_report
        })
    except Exception:
        # Если новый шаблон не найден, используем старый
        try:
            return templates.TemplateResponse("admin/nodes_health.html", {
                "request": request,
                "title": "VPN Nodes Health",
                "current_admin": current_admin,
                "health_report": health_report
            })
        except Exception:
            # Если и старый шаблон не найден, перенаправляем на список нод
            return RedirectResponse(url="/admin/nodes", status_code=302)

@router.get("/nodes/dashboard", response_class=HTMLResponse)
async def admin_nodes_dashboard(
    request: Request,
    node_id: Optional[int] = None,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница мониторинга нод"""
    
    # Инициализируем NodeManager
    node_manager = NodeManager(db)
    
    # Если указан node_id, показываем конкретную ноду
    if node_id:
        node = await node_manager.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Нода не найдена")
            
        # Получаем статистику ноды
        health_checker = HealthChecker(db)
        node_stats = await health_checker.get_node_stats(node_id)
        
        return templates.TemplateResponse("admin/nodes/node_dashboard.html", {
            "request": request,
            "title": f"Мониторинг ноды: {node.name}",
            "current_admin": current_admin,
            "node": node,
            "stats": node_stats
        })
        
    # Иначе показываем все ноды
    nodes = await node_manager.get_nodes(include_assignments=True)
    
    # Получаем статистику нагрузки
    load_balancer = LoadBalancer(db)
    load_stats = await load_balancer.get_node_load_stats()
    
    # Получаем отчет о здоровье системы
    health_checker = HealthChecker(db)
    health_report = await health_checker.get_health_report()
    
    try:
        # Пробуем сначала новый шаблон
        return templates.TemplateResponse("admin/nodes/dashboard.html", {
            "request": request,
            "title": "Мониторинг нод",
            "current_admin": current_admin,
            "nodes": nodes,
            "load_stats": load_stats,
            "health_report": health_report
        })
    except Exception:
        # В случае ошибки перенаправляем на список нод
        return RedirectResponse(url="/admin/nodes", status_code=302)

@router.get("/nodes/balance", response_class=HTMLResponse)
async def admin_nodes_balance_page(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница перебалансировки нод"""
    
    # Инициализируем LoadBalancer
    load_balancer = LoadBalancer(db)
    
    # Получаем статистику нагрузки
    load_stats = await load_balancer.get_node_load_stats()
    
    # Получаем все ноды
    node_manager = NodeManager(db)
    nodes = await node_manager.get_nodes(include_assignments=True)
    
    return templates.TemplateResponse("admin/nodes/balance.html", {
        "request": request,
        "title": "Балансировка нод",
        "current_admin": current_admin,
        "nodes": nodes,
        "load_stats": load_stats
    })

@router.post("/nodes/{node_id}/check-health")
async def admin_check_node_health(
    node_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Проверка здоровья конкретной ноды"""
    
    # Инициализируем HealthChecker
    health_checker = HealthChecker(db)
    
    # Проверяем здоровье
    status = await health_checker.check_node_health_by_id(node_id)
    
    return JSONResponse(
        content={
            "success": True,
            "is_healthy": status.is_healthy,
            "response_time_ms": status.response_time_ms,
            "error_message": status.error_message,
            "checked_at": status.checked_at.isoformat()
        }
    )

@router.post("/nodes/check-all-health")
async def admin_check_all_nodes_health(
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Проверка здоровья всех нод"""
    
    # Инициализируем HealthChecker
    health_checker = HealthChecker(db)
    
    # Проверяем здоровье всех нод
    statuses = await health_checker.check_all_nodes()
    
    # Преобразуем в JSON-совместимый формат
    result = {}
    for node_id, status in statuses.items():
        result[str(node_id)] = {
            "is_healthy": status.is_healthy,
            "response_time_ms": status.response_time_ms,
            "error_message": status.error_message,
            "checked_at": status.checked_at.isoformat()
        }
    
    return JSONResponse(
        content={"success": True, "statuses": result}
    )

@router.post("/nodes/rebalance")
async def admin_rebalance_nodes(
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Перебалансировка пользователей между нодами"""
    
    # Инициализируем LoadBalancer
    load_balancer = LoadBalancer(db)
    
    # Выполняем перебалансировку
    result = await load_balancer.rebalance_users()
    
    return JSONResponse(content=result)

@router.get("/nodes/{node_id}/users", response_class=HTMLResponse)
async def admin_node_users_page(
    node_id: int,
    request: Request,
    page: int = 1,
    size: int = 50,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница пользователей на конкретной ноде"""
    
    # Получаем ноду
    result = await db.execute(select(VPNNode).where(VPNNode.id == node_id))
    node = result.scalar_one_or_none()
    
    if not node:
        return RedirectResponse(url="/admin/nodes", status_code=302)
    
    # Получаем пользователей с пагинацией
    offset = (page - 1) * size
    
    users_query = (
        select(User)
        .join(UserServerAssignment, User.telegram_id == UserServerAssignment.user_id)
        .where(UserServerAssignment.node_id == node_id)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    
    count_query = (
        select(func.count(User.id))
        .join(UserServerAssignment, User.telegram_id == UserServerAssignment.user_id)
        .where(UserServerAssignment.node_id == node_id)
    )
    
    users_result = await db.execute(users_query)
    count_result = await db.execute(count_query)
    
    users = users_result.scalars().all()
    total_users = count_result.scalar() or 0
    
    # Вычисляем пагинацию
    total_pages = (total_users + size - 1) // size
    
    return templates.TemplateResponse("admin/node_users.html", {
        "request": request,
        "title": f"Users on Node: {node.name}",
        "current_admin": current_admin,
        "node": node,
        "users": users,
        "pagination": {
            "page": page,
            "size": size,
            "total_users": total_users,
            "total_pages": total_pages
        }
    })

@router.post("/nodes/{node_id}/migrate-user/{user_id}")
async def admin_migrate_user(
    node_id: int,
    user_id: int,
    target_node_id: int = Form(...),
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Миграция пользователя на другую ноду"""
    
    # Инициализируем LoadBalancer
    load_balancer = LoadBalancer(db)
    
    # Мигрируем пользователя
    success = await load_balancer.migrate_user(user_id, target_node_id)
    
    if not success:
        return JSONResponse(
            content={"success": False, "message": "Failed to migrate user"},
            status_code=400
        )
    
    return JSONResponse(
        content={"success": True, "message": "User migrated successfully"}
    )

@router.post("/api/test-x3ui-connection")
async def test_x3ui_connection_api(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """API endpoint для тестирования X3UI соединения"""
    try:
        data = await request.json()
        
        config = NodeConfig(
            name="Test",
            x3ui_url=data.get("x3ui_url"),
            x3ui_username=data.get("x3ui_username"),
            x3ui_password=data.get("x3ui_password")
        )
        
        node_manager = NodeManager(db)
        result = await node_manager._test_x3ui_connection(config)
        
        return {"success": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- AUTO NODE DEPLOYMENT ---

@router.get("/nodes/auto/create", response_class=HTMLResponse)
async def admin_auto_create_node_page(
    request: Request,
    current_admin: str = Depends(get_current_admin)
):
    """Страница автоматического развертывания ноды"""
    return templates.TemplateResponse("admin/nodes/create_auto.html", {
        "request": request,
        "current_admin": current_admin
    })

@router.post("/nodes/api/auto-deploy")
async def admin_start_auto_deployment(
    request: Request,
    ssh_host: str = Form(...),
    ssh_user: str = Form(...),
    ssh_password: str = Form(...),
    name: str = Form(None),
    location: str = Form(""),
    deployment_method: str = Form("ssh"),
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Запуск автоматизированного развертывания ноды"""
    try:
        config = NodeDeploymentConfig(
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            ssh_password=ssh_password,
            name=name,
            location=location,
            random_port=True,
            random_password=True,
            random_slug=True,
            auto_add_to_balancer=True
        )
        
        automation_service = NodeAutomationService(db)
        deployment_id = await automation_service.start_automated_deployment(config)
        return {"success": True, "deployment_id": deployment_id}
    except Exception as e:
        logger.error("Admin auto-deploy error", error=str(e))
        return {"success": False, "error": str(e)}

@router.get("/nodes/api/deployment-progress/{deployment_id}")
async def admin_get_deployment_progress(
    deployment_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    automation_service = NodeAutomationService(db)
    progress = await automation_service.get_deployment_progress(deployment_id)
    if progress:
        return {"success": True, "progress": progress}
    return {"success": False, "error": "Deployment not found"}

@router.post("/nodes/api/generate-installer-script")
async def admin_generate_installer_script(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    data = await request.json()
    try:
        config = NodeDeploymentConfig(
            domain=data["domain"],
            deployment_method=DeploymentMethod.MANUAL,
            x3ui_url=data.get("x3ui_url"),
            x3ui_username=data.get("x3ui_username"),
            x3ui_password=data.get("x3ui_password"),
            ssl_email=data.get("ssl_email"),
            custom_port=data.get("custom_port", 443)
        )
        automation_service = NodeAutomationService(db)
        env_info = {"domain": config.domain, "os_type": "ubuntu", "architecture": "amd64"}
        script = await automation_service._generate_installer_script(config, env_info)
        filename = f"install_node_{config.domain}_{int(datetime.utcnow().timestamp())}.sh"
        return {"success": True, "script_content": script, "script_filename": filename}
    except Exception as e:
        logger.error("Generate installer script error", error=str(e))
        return {"success": False, "error": str(e)}

@router.post("/nodes/api/validate-deployment-config")
async def admin_validate_deployment_config(
    ssh_host: str = Form(...),
    ssh_user: str = Form(...),
    ssh_password: str = Form(...),
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Проверка SSH подключения к серверу"""
    try:
        # Создаем конфигурацию для тестирования
        config = NodeDeploymentConfig(
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            ssh_password=ssh_password
        )
        
        automation_service = NodeAutomationService(db)
        
        # Тестируем SSH подключение
        result = await automation_service._test_ssh_connection(config)
        
        if result.get("success"):
            return {"success": True, "message": "SSH подключение успешно установлено"}
        else:
            return {"success": False, "error": result.get("error", "Не удалось подключиться по SSH")}
            
    except Exception as e:
        return {"success": False, "error": f"Ошибка SSH: {str(e)}"}

@router.post("/nodes/api/create-direct")
async def admin_create_node_direct(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Прямое создание ноды без проверки X3UI (для автоматизации)"""
    try:
        data = await request.json()
        
        # Создаем ноду напрямую
        new_node = VPNNode(
            name=data["name"],
            description=data.get("description", ""),
            location=data.get("location", ""),
            x3ui_url=data["x3ui_url"],
            x3ui_username=data["x3ui_username"],
            x3ui_password=data["x3ui_password"],
            max_users=data.get("max_users", 1000),
            priority=data.get("priority", 100),
            weight=data.get("weight", 1.0),
            status='active',
            health_status='unknown',
            mode=NodeMode.reality if data.get("mode") == "reality" else NodeMode.reality,
            public_key=data.get("public_key"),
            short_id=data.get("short_id"),
            sni_mask=data.get("sni_mask", "apple.com")
        )
        
        db.add(new_node)
        await db.commit()
        await db.refresh(new_node)
        
        logger.info("VPN node created directly", 
                   node_id=new_node.id, 
                   name=new_node.name)
        
        return {"success": True, "node_id": new_node.id, "message": "Node created successfully"}
        
    except Exception as e:
        logger.error("Error creating node directly", error=str(e))
        await db.rollback()
        return {"success": False, "error": str(e)}

@router.post("/api/cleanup-clients")
async def admin_cleanup_clients(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Очистка всех нод от осиротевших клиентов в X3UI панели"""
    try:
        from services.client_cleanup_utility import cleanup_clients
        
        logger.info("Запуск очистки клиентов", admin=current_admin)
        result = await cleanup_clients(db)
        
        return {
            "success": True,
            "result": result,
            "message": result.get("message", "Очистка выполнена")
        }
        
    except Exception as e:
        logger.error(f"Ошибка при очистке клиентов: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при очистке клиентов: {str(e)}")

@router.get("/api/node-clients/{node_id}")
async def admin_get_node_clients(
    node_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Получение списка всех клиентов на ноде"""
    try:
        # Получаем ноду из базы данных
        node_result = await db.execute(select(VPNNode).where(VPNNode.id == node_id))
        node = node_result.scalar_one_or_none()
        
        if not node:
            raise HTTPException(status_code=404, detail="Нода не найдена")
        
        # Используем утилиту для получения клиентов
        from services.client_cleanup_utility import ClientCleanupUtility
        utility = ClientCleanupUtility(db)
        
        # Получаем всех клиентов на ноде
        clients = await utility.get_clients_on_node(node)
        
        # Получаем информацию о осиротевших клиентах и дубликатах
        orphaned, duplicates = await utility.find_orphaned_clients(node)
        
        # Помечаем клиентов, которые являются осиротевшими или дубликатами
        orphaned_ids = {c.get("id") for c in orphaned}
        duplicate_emails = {c.get("email") for c in duplicates}
        
        for client in clients:
            client["is_orphaned"] = client.get("id") in orphaned_ids
            client["is_duplicate"] = client.get("email") in duplicate_emails and not client.get("is_orphaned")
        
        return {
            "success": True,
            "node_id": node_id,
            "node_name": node.name,
            "clients_count": len(clients),
            "orphaned_count": len(orphaned),
            "duplicates_count": len(duplicates),
            "clients": clients
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении клиентов ноды: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении клиентов: {str(e)}")

@router.post("/api/delete-client/{inbound_id}/{client_id}")
async def delete_x3ui_client(
    inbound_id: int,
    client_id: str,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Удаление клиента из X3UI панели через админку"""
    try:
        # Сначала ищем ноду по ключу с этим client_id
        vpn_key_result = await db.execute(
            select(VPNKey).where(VPNKey.xui_client_id == client_id)
        )
        vpn_key = vpn_key_result.scalar_one_or_none()
        
        if vpn_key:
            # Если нашли ключ, получаем его ноду
            node_result = await db.execute(
                select(VPNNode).where(VPNNode.id == vpn_key.node_id)
            )
            node = node_result.scalar_one_or_none()
        else:
            # Если ключ не найден, используем первую активную ноду (fallback)
            node_result = await db.execute(
                select(VPNNode).where(VPNNode.status == "active")
                .order_by(VPNNode.priority.desc())
                .limit(1)
            )
            node = node_result.scalar_one_or_none()
        
        if not node:
            return {"success": False, "error": "Не найдена подходящая нода"}
        
        # Создаем X3UIClient
        from services.x3ui_client import X3UIClient
        x3ui_client = X3UIClient(
            base_url=node.x3ui_url,
            username=node.x3ui_username,
            password=node.x3ui_password
        )
        
        # Проверяем подключение
        if not await x3ui_client._login():
            return {"success": False, "error": "Не удалось подключиться к X3UI панели"}
        
        # ИСПРАВЛЕННАЯ ЛОГИКА: Удаляем клиента из X3UI панели перед деактивацией в БД
        logger.info("🗑️ Attempting to delete client from X3UI panel via admin", 
                   inbound_id=inbound_id, 
                   client_id=client_id,
                   node_id=node.id,
                   vpn_key_found=vpn_key is not None)
        
        deletion_success = await x3ui_client.delete_client(inbound_id, client_id)
        
        if deletion_success:
            logger.info("✅ Client successfully deleted from X3UI panel", 
                       inbound_id=inbound_id, 
                       client_id=client_id,
                       node_id=node.id)
            
            # КРИТИЧЕСКИ ВАЖНО: Деактивируем в БД ТОЛЬКО при успешном удалении из X3UI панели
            if vpn_key:
                vpn_key.status = VPNKeyStatus.INACTIVE.value
                vpn_key.updated_at = datetime.utcnow()
                await db.commit()
                
                logger.info("✅ VPN key deactivated in database after successful X3UI deletion", 
                           vpn_key_id=vpn_key.id,
                           client_id=client_id)
                
                return {
                    "success": True, 
                    "message": "Клиент успешно удален из X3UI панели и деактивирован в базе"
                }
            else:
                logger.info("ℹ️ VPN key not found in database, X3UI client deleted only", 
                           client_id=client_id)
                return {
                    "success": True, 
                    "message": "Клиент успешно удален из X3UI панели (не найден в базе)"
                }
        else:
            # При неудачном удалении из X3UI - НЕ ДЕАКТИВИРУЕМ в БД и возвращаем детальную ошибку
            logger.error("❌ Failed to delete client from X3UI panel", 
                        inbound_id=inbound_id, 
                        client_id=client_id,
                        node_id=node.id,
                        node_url=node.x3ui_url)
            
            return {
                "success": False, 
                "error": f"Не удалось удалить клиента из X3UI панели (нода: {node.name}, ID: {client_id})"
            }
        
    except Exception as e:
        logger.error(f"Ошибка при удалении клиента: {str(e)}")
        return {"success": False, "error": str(e)}

# === ПОДПИСКИ УДАЛЕНЫ - УПРОЩЕННАЯ АРХИТЕКТУРА ===

# === ПЛАТЕЖИ ===
@router.get("/payments", response_class=HTMLResponse)
async def admin_payments_page(
    request: Request,
    page: int = 1,
    size: int = 50,
    status: Optional[str] = None,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница управления платежами"""
    
    # Базовый запрос БЕЗ джойнов (так как связи закомментированы в модели)
    query = select(Payment)
    
    # Фильтрация по статусу
    if status:
        query = query.where(Payment.status == status)
    
    # Подсчет общего количества
    count_query = select(func.count(Payment.id))
    if status:
        count_query = count_query.where(Payment.status == status)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Пагинация
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Payment.created_at.desc())
    
    result = await db.execute(query)
    payments = result.scalars().all()
    
    # Получаем пользователей отдельным запросом
    from models.user import User
    if payments:
        user_ids = [p.user_id for p in payments if p.user_id]
        if user_ids:
            users_query = select(User).where(User.id.in_(user_ids))
            users_result = await db.execute(users_query)
            users = {u.id: u for u in users_result.scalars().all()}
            
            # Добавляем пользователей к платежам
            for payment in payments:
                payment.user = users.get(payment.user_id)
    
    # Статистика
    stats_query = select(
        func.count(Payment.id).label('total'),
        func.sum(case((Payment.status == 'SUCCEEDED', 1), else_=0)).label('completed'),
        func.sum(case((Payment.status == 'PENDING', 1), else_=0)).label('pending'),
        func.sum(case((Payment.status == 'FAILED', 1), else_=0)).label('failed'),
        func.sum(case((Payment.status == 'SUCCEEDED', Payment.amount), else_=0)).label('total_amount')
    )
    stats_result = await db.execute(stats_query)
    stats = stats_result.first()
    
    return templates.TemplateResponse("admin/payments.html", {
        "request": request,
        "title": "Payments Management",
        "current_admin": current_admin,
        "payments": payments,
        "total": total,
        "page": page,
        "size": size,
        "status_filter": status or "",
        "stats": stats,
        "has_next": (page * size) < total,
        "has_prev": page > 1
    })

# === УПРАВЛЕНИЕ УСЛУГАМИ ===

# Импортируем централизованный сервис управления планами
from services.service_plans_manager import service_plans_manager

@router.get("/services", response_class=HTMLResponse)
async def admin_services_page(
    request: Request,
    current_admin: str = Depends(get_current_admin)
):
    """Страница управления услугами"""
    
    return templates.TemplateResponse("admin/services.html", {
        "request": request,
        "title": "Управление услугами",
        "current_admin": current_admin,
        "services": service_plans_manager.get_plans()
    })

@router.get("/services/create", response_class=HTMLResponse)
async def admin_service_create_page(
    request: Request,
    current_admin: str = Depends(get_current_admin)
):
    """Страница создания услуги"""
    
    return templates.TemplateResponse("admin/service_create.html", {
        "request": request,
        "title": "Создать услугу",
        "current_admin": current_admin
    })

@router.post("/services/create")
async def admin_service_create(
    request: Request,
    service_id: str = Form(...),
    name: str = Form(...),
    price: float = Form(...),
    duration_days: int = Form(...),
    description: str = Form(""),
    discount: str = Form(""),
    active: bool = Form(False),
    current_admin: str = Depends(get_current_admin)
):
    """Создание новой услуги"""
    
    try:
        # Проверяем, что ID не занят
        if service_plans_manager.get_plan(service_id):
            return templates.TemplateResponse("admin/service_create.html", {
                "request": request,
                "title": "Создать услугу",
                "current_admin": current_admin,
                "error": "ID услуги уже существует"
            })
        
        # Создаем новую услугу
        new_service = {
            "id": service_id,
            "name": name,
            "price": price,
            "duration": f"{duration_days} дней",
            "duration_days": duration_days,
            "description": description,
            "discount": discount if discount else None,
            "active": active
        }
        
        # Добавляем через сервис
        service_plans_manager.create_plan(service_id, new_service)
        
        return RedirectResponse(url="/admin/services", status_code=302)
        
    except Exception as e:
        return templates.TemplateResponse("admin/service_create.html", {
            "request": request,
            "title": "Создать услугу",
            "current_admin": current_admin,
            "error": f"Ошибка при создании услуги: {str(e)}"
        })

@router.get("/services/{service_id}/edit", response_class=HTMLResponse)
async def admin_service_edit_page(
    service_id: str,
    request: Request,
    current_admin: str = Depends(get_current_admin)
):
    """Страница редактирования услуги"""
    
    service = service_plans_manager.get_plan(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    
    return templates.TemplateResponse("admin/service_edit.html", {
        "request": request,
        "title": f"Редактировать услугу: {service['name']}",
        "current_admin": current_admin,
        "service": service
    })

@router.post("/services/{service_id}/edit")
async def admin_service_update(
    service_id: str,
    request: Request,
    name: str = Form(...),
    price: float = Form(...),
    duration_days: int = Form(...),
    description: str = Form(""),
    discount: str = Form(""),
    active: bool = Form(False),
    current_admin: str = Depends(get_current_admin)
):
    """Обновление услуги"""
    
    try:
        service = service_plans_manager.get_plan(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Услуга не найдена")
        
        # Обновляем данные услуги
        updated_data = {
            "name": name,
            "price": price,
            "duration": f"{duration_days} дней",
            "duration_days": duration_days,
            "description": description,
            "discount": discount if discount else None,
            "active": active
        }
        service_plans_manager.update_plan(service_id, updated_data)
        
        return RedirectResponse(url="/admin/services", status_code=302)
        
    except Exception as e:
        service = service_plans_manager.get_plan(service_id)
        return templates.TemplateResponse("admin/service_edit.html", {
            "request": request,
            "title": f"Редактировать услугу: {service['name']}",
            "current_admin": current_admin,
            "service": service,
            "error": f"Ошибка при обновлении услуги: {str(e)}"
        })

@router.post("/services/{service_id}/delete")
async def admin_service_delete(
    service_id: str,
    current_admin: str = Depends(get_current_admin)
):
    """Удаление услуги"""
    
    try:
        if not service_plans_manager.get_plan(service_id):
            raise HTTPException(status_code=404, detail="Услуга не найдена")
        
        # Удаляем услугу
        service_plans_manager.delete_plan(service_id)
        
        return RedirectResponse(url="/admin/services", status_code=302)
        
    except Exception as e:
        return RedirectResponse(url="/admin/services?error=" + str(e), status_code=302)

@router.post("/services/{service_id}/toggle")
async def admin_service_toggle(
    service_id: str,
    current_admin: str = Depends(get_current_admin)
):
    """Переключение активности услуги"""
    
    try:
        service = service_plans_manager.get_plan(service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Услуга не найдена")
        
        # Переключаем активность
        updated_data = service.copy()
        updated_data["active"] = not service["active"]
        service_plans_manager.update_plan(service_id, updated_data)
        
        return RedirectResponse(url="/admin/services", status_code=302)
        
    except Exception as e:
        return RedirectResponse(url="/admin/services?error=" + str(e), status_code=302)


# =============================================================================
# УПРАВЛЕНИЕ ПЛАТЕЖНЫМИ ПРОВАЙДЕРАМИ
# =============================================================================

# =============================================================================
# MANUAL PAYMENT MANAGEMENT ENDPOINTS 
# =============================================================================

@router.get("/payments/create", response_class=HTMLResponse)
async def admin_create_payment_page(
    request: Request,
    user_id: Optional[int] = None,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница создания ручного платежа"""
    try:
        # Если указан user_id, получаем информацию о пользователе
        user = None
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
        
        return templates.TemplateResponse("admin/payment_create.html", {
            "request": request,
            "title": "Создать платеж",
            "user": user,
            "payment_methods": [
                {"value": "manual_admin", "label": "Ручной платеж администратором"},
                {"value": "manual_trial", "label": "Ручной триальный платеж"},
                {"value": "manual_correction", "label": "Корректировка платежа"}
            ]
        })
    except Exception as e:
        logger.error("Error loading create payment page", error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка загрузки страницы")

@router.post("/api/payments/create")
async def create_manual_payment(
    payment_data: ManualPaymentCreateRequest,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """API создания ручного платежа"""
    try:
        # Валидация payment_method
        valid_methods = ["manual_admin", "manual_trial", "manual_correction"]
        if payment_data.payment_method not in valid_methods:
            raise HTTPException(status_code=400, detail="Неверный метод платежа")
        
        # Получаем сервис управления платежами
        payment_service = PaymentManagementService(db)
        
        # Создаем платеж
        from models.payment import PaymentMethod
        payment_method_enum = PaymentMethod(payment_data.payment_method)
        
        payment = await payment_service.create_manual_payment(
            user_id=payment_data.user_id,
            amount=payment_data.amount,
            description=payment_data.description,
            payment_method=payment_method_enum,
            admin_user=current_admin,
            subscription_days=payment_data.subscription_days,
            metadata=payment_data.metadata
        )
        
        logger.info(
            "Manual payment created via admin API",
            payment_id=payment.id,
            user_id=payment_data.user_id,
            amount=payment_data.amount,
            admin_user=current_admin
        )
        
        return {
            "success": True,
            "payment_id": payment.id,
            "message": "Платеж успешно создан",
            "payment": {
                "id": payment.id,
                "user_id": payment.user_id,
                "amount": payment.amount,
                "status": payment.status.value,
                "payment_method": payment.payment_method.value,
                "description": payment.description,
                "created_at": payment.created_at.isoformat()
            }
        }
        
    except ValueError as ve:
        logger.warning("Validation error creating manual payment", error=str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Error creating manual payment", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка создания платежа")

@router.patch("/api/payments/{payment_id}/status")
async def update_payment_status(
    payment_id: int,
    status_data: PaymentStatusUpdateRequest,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """API изменения статуса платежа"""
    try:
        # Валидация статуса
        valid_statuses = ["PENDING", "SUCCEEDED", "FAILED", "CANCELLED", "REFUNDED"]
        if status_data.new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail="Неверный статус платежа")
        
        # Получаем сервис управления платежами
        payment_service = PaymentManagementService(db)
        
        # Обновляем статус
        from models.payment import PaymentStatus
        new_status_enum = PaymentStatus(status_data.new_status)
        
        updated_payment = await payment_service.update_payment_status(
            payment_id=payment_id,
            new_status=new_status_enum,
            admin_user=current_admin,
            reason=status_data.reason
        )
        
        logger.info(
            "Payment status updated via admin API",
            payment_id=payment_id,
            new_status=status_data.new_status,
            admin_user=current_admin,
            reason=status_data.reason
        )
        
        return {
            "success": True,
            "payment_id": updated_payment.id,
            "message": "Статус платежа обновлен",
            "payment": {
                "id": updated_payment.id,
                "user_id": updated_payment.user_id,
                "status": updated_payment.status.value,
                "updated_at": updated_payment.updated_at.isoformat(),
                "paid_at": updated_payment.paid_at.isoformat() if updated_payment.paid_at else None
            }
        }
        
    except ValueError as ve:
        logger.warning("Validation error updating payment status", error=str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Error updating payment status", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка обновления статуса платежа")

@router.get("/users/{user_id}/", response_class=HTMLResponse)
async def admin_user_profile_page(
    user_id: int,
    request: Request,
    page: int = 1,
    size: int = 50,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница профиля пользователя с историей платежей"""
    try:
        logger.info("Loading user profile page", user_id=user_id)
        
        # Получаем пользователя
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning("User not found", user_id=user_id)
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        logger.info("User found", user_id=user_id, username=user.username)
        
        # Получаем историю платежей
        try:
            payment_service = get_payment_management_service(db)
            offset = (page - 1) * size
            payments = await payment_service.get_user_payments_history(
                user_id=user_id,
                limit=size,
                offset=offset
            )
            logger.info("Payments loaded", user_id=user_id, payments_count=len(payments))
        except Exception as e:
            logger.error("Error loading payments", user_id=user_id, error=str(e))
            payments = []
        
        # Подсчитываем общую статистику
        try:
            total_payments_count = await db.scalar(
                select(func.count(Payment.id)).where(Payment.user_id == user_id)
            ) or 0
            
            total_amount = await db.scalar(
                select(func.sum(Payment.amount))
                .where(Payment.user_id == user_id)
                .where(Payment.status == PaymentStatus.SUCCEEDED)
            ) or 0.0
            
            # Подсчитываем статистику по статусам
            pending_payments = await db.scalar(
                select(func.count(Payment.id))
                .where(Payment.user_id == user_id)
                .where(Payment.status == PaymentStatus.PENDING)
            ) or 0
            
            failed_payments = await db.scalar(
                select(func.count(Payment.id))
                .where(Payment.user_id == user_id)
                .where(Payment.status == PaymentStatus.FAILED)
            ) or 0
            
            logger.info("Payment stats calculated", 
                       user_id=user_id, 
                       total_payments=total_payments_count,
                       total_amount=total_amount)
        except Exception as e:
            logger.error("Error calculating payment stats", user_id=user_id, error=str(e))
            total_payments_count = 0
            total_amount = 0.0
            pending_payments = 0
            failed_payments = 0
        
        # Получаем активный автоплатеж пользователя
        try:
            auto_payment_result = await db.execute(
                select(AutoPayment)
                .where(AutoPayment.user_id == user_id)
                .where(AutoPayment.status == "active")
                .order_by(AutoPayment.created_at.desc())
                .limit(1)
            )
            user.auto_payment = auto_payment_result.scalar_one_or_none()
            logger.info("Auto payment loaded", 
                       user_id=user_id, 
                       has_autopay=user.auto_payment is not None)
        except Exception as e:
            logger.error("Error loading auto payment", user_id=user_id, error=str(e))
            user.auto_payment = None
        
        # Подготавливаем данные для шаблона
        payments_data = []
        try:
            for payment in payments:
                payments_data.append({
                    "id": payment.id,
                    "amount": payment.amount,
                    "status": payment.status.value if hasattr(payment.status, 'value') else str(payment.status),
                    "payment_method": payment.payment_method.value if hasattr(payment.payment_method, 'value') else str(payment.payment_method),
                    "description": payment.description,
                    "created_at": payment.created_at,
                    "paid_at": payment.paid_at,
                    "updated_at": payment.updated_at
                })
        except Exception as e:
            logger.error("Error preparing payment data", user_id=user_id, error=str(e))
            payments_data = []
        
        total_pages = (total_payments_count + size - 1) // size if total_payments_count > 0 else 1
        
        logger.info("User profile page prepared successfully", 
                   user_id=user_id, 
                   total_pages=total_pages,
                   payments_data_count=len(payments_data))
        
        return templates.TemplateResponse("admin/user_profile.html", {
            "request": request,
            "current_admin": current_admin,
            "title": f"Профиль пользователя {user.username or user.first_name or f'ID {user.id}'}",
            "user": user,
            "payments": payments_data,
            "current_page": page,
            "total_pages": total_pages,
            "size": size,
            "total_payments": total_payments_count,
            "total_amount": total_amount,
            "pending_payments": pending_payments,
            "failed_payments": failed_payments,
            "payment_statuses": [
                {"value": "PENDING", "label": "Ожидает"},
                {"value": "SUCCEEDED", "label": "Успешно"},
                {"value": "FAILED", "label": "Ошибка"},
                {"value": "CANCELLED", "label": "Отменен"}
            ]
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error loading user profile page", 
                    user_id=user_id, 
                    error=str(e), 
                    error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="Ошибка загрузки профиля пользователя")

@router.get("/api/users/{user_id}/payments")
async def get_user_payments_api(
    user_id: int,
    page: int = 1,
    size: int = 50,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
) -> UserPaymentHistoryResponse:
    """API получения истории платежей пользователя"""
    try:
        # Получаем пользователя
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Получаем платежи
        payment_service = PaymentManagementService(db)
        offset = (page - 1) * size
        payments = await payment_service.get_user_payments_history(
            user_id=user_id,
            limit=size,
            offset=offset
        )
        
        # Подсчитываем статистику
        total_payments_count = await db.scalar(
            select(func.count(Payment.id)).where(Payment.user_id == user_id)
        )
        
        total_amount = await db.scalar(
            select(func.sum(Payment.amount))
            .where(Payment.user_id == user_id)
            .where(Payment.status == PaymentStatus.SUCCEEDED)
        ) or 0.0
        
        # Форматируем данные
        payments_data = []
        for payment in payments:
            payments_data.append({
                "id": payment.id,
                "amount": payment.amount,
                "currency": payment.currency,
                "status": payment.status.value,
                "payment_method": payment.payment_method.value,
                "description": payment.description,
                "created_at": payment.created_at.isoformat(),
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                "updated_at": payment.updated_at.isoformat()
            })
        
        return UserPaymentHistoryResponse(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            telegram_id=user.telegram_id,
            payments=payments_data,
            total_payments=total_payments_count,
            total_amount=total_amount
        )
        
    except Exception as e:
        logger.error("Error getting user payments via API", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка получения истории платежей")

@router.get("/payments/{payment_id}", response_class=HTMLResponse)
async def admin_payment_detail_page(
    payment_id: int,
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Детальная страница платежа"""
    
    # Получаем платеж БЕЗ джойнов (так как связи закомментированы в модели)
    query = select(Payment).where(Payment.id == payment_id)
    
    result = await db.execute(query)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Получаем пользователя отдельным запросом если есть user_id
    from models.user import User
    if payment.user_id:
        user_query = select(User).where(User.id == payment.user_id)
        user_result = await db.execute(user_query)
        payment.user = user_result.scalar_one_or_none()
    else:
        payment.user = None
    
    return templates.TemplateResponse("admin/payment_detail.html", {
        "request": request,
        "title": f"Платеж #{payment.id}",
        "current_admin": current_admin,
        "payment": payment
    })

# =============================================================================
# PAYMENT PROVIDERS MANAGEMENT
# =============================================================================

@router.get("/payment-providers", response_class=HTMLResponse)
async def admin_payment_providers_page(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Главная страница управления платежными провайдерами"""
    
    # Получаем список провайдеров
    result = await db.execute(
        select(PaymentProvider).order_by(PaymentProvider.priority, PaymentProvider.id)
    )
    providers = result.scalars().all()
    
    # Получаем статистику
    stats = await _get_payment_provider_dashboard_stats(db)
    
    # Добавляем дополнительную информацию к провайдерам с реальной статистикой
    providers_with_info = []
    for provider in providers:
        # Получаем реальную статистику платежей для каждого провайдера
        payments_result = await db.execute(
            select(Payment).where(Payment.provider_id == provider.id)
        )
        payments = payments_result.scalars().all()
        
        total_payments = len(payments)
        successful_payments = len([p for p in payments if p.status == PaymentStatus.SUCCEEDED])
        failed_payments = len([p for p in payments if p.status == PaymentStatus.FAILED])
        
        provider_dict = {
            "id": provider.id,
            "name": provider.name,
            "provider_type": provider.provider_type.value,
            "status": provider.status.value,
            "is_active": provider.is_active,
            "is_test_mode": provider.is_test_mode,
            "is_default": provider.is_default,
            "description": provider.description,
            "priority": provider.priority,  # Добавляем приоритет
            "total_payments": total_payments,  # Реальное количество платежей
            "successful_payments": successful_payments,
            "failed_payments": failed_payments,
            "success_rate": (successful_payments / total_payments * 100) if total_payments > 0 else 0.0,
            "is_healthy": provider.is_healthy,
            "masked_config": provider.mask_sensitive_config()
        }
        providers_with_info.append(provider_dict)
    
    return templates.TemplateResponse("admin/payment_providers/list.html", {
        "request": request,
        "title": "Управление платежными системами",
        "current_admin": current_admin,
        "providers": providers_with_info,
        "stats": stats,
        "provider_types": [t.value for t in PaymentProviderType]
    })


def _get_provider_description(provider_type: str) -> str:
    """Получение описания провайдера по типу"""
    descriptions = {
        "robokassa": "Российская платежная система с поддержкой карт, электронных кошельков и интернет-банкинга",
        "freekassa": "Платежная система с низкими комиссиями и поддержкой криптовалют",
        "yookassa": "Платежная система от Яндекса с широкими возможностями приема платежей",
        "tinkoff": "Эквайринг от Тинькофф Банка с быстрым подключением",
        "sberbank": "Эквайринг от Сбербанка - самая популярная российская платежная система"
    }
    return descriptions.get(provider_type.lower(), "Платежная система для приема онлайн платежей")


@router.get("/payment-providers/create", response_class=HTMLResponse)
async def admin_create_payment_provider_page(
    request: Request,
    current_admin: str = Depends(get_current_admin)
):
    """Страница создания платежного провайдера"""
    
    return templates.TemplateResponse("admin/payment_providers/create.html", {
        "request": request,
        "title": "Добавить платежную систему",
        "current_admin": current_admin,
        "provider_types": [
            {"value": t.value, "name": t.value.title()}
            for t in PaymentProviderType
        ],
        "_get_provider_description": _get_provider_description
    })


@router.get("/payment-providers/{provider_id}/edit", response_class=HTMLResponse)
async def admin_edit_payment_provider_page(
    provider_id: int,
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница редактирования платежного провайдера"""
    
    result = await db.execute(
        select(PaymentProvider).where(PaymentProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    
    # Получаем реальную статистику платежей для провайдера
    payments_result = await db.execute(
        select(Payment).where(Payment.provider_id == provider.id)
    )
    payments = payments_result.scalars().all()
    
    total_payments = len(payments)
    successful_payments = len([p for p in payments if p.status == PaymentStatus.SUCCEEDED])
    failed_payments = len([p for p in payments if p.status == PaymentStatus.FAILED])
    total_amount = sum([p.amount for p in payments if p.status == PaymentStatus.SUCCEEDED])
    
    # Создаем объект с дополнительной статистикой
    provider_with_stats = {
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type.value,
        "status": provider.status.value,
        "is_active": provider.is_active,
        "is_test_mode": provider.is_test_mode,
        "is_default": provider.is_default,
        "description": provider.description,
        "priority": provider.priority,
        "config": provider.config,
        "webhook_url": provider.webhook_url,
        "min_amount": provider.min_amount,
        "max_amount": provider.max_amount,
        "commission_percent": provider.commission_percent,
        "commission_fixed": provider.commission_fixed,
        "success_url": provider.success_url,
        "failure_url": provider.failure_url,
        "notification_url": provider.notification_url,
        "notification_method": provider.notification_method,
        "created_at": provider.created_at,
        "updated_at": provider.updated_at,
        "total_payments": total_payments,
        "successful_payments": successful_payments,
        "failed_payments": failed_payments,
        "total_amount": total_amount,
        "success_rate": (successful_payments / total_payments * 100) if total_payments > 0 else 0.0
    }
    
    # Получаем настройки из БД
    from services.app_settings_service import AppSettingsService
    app_settings = await AppSettingsService.get_settings(db)
    
    return templates.TemplateResponse("admin/payment_providers/edit.html", {
        "request": request,
        "title": f"Редактировать {provider.name}",
        "current_admin": current_admin,
        "provider": provider_with_stats,
        "provider_types": [
            {"value": t.value, "name": t.value.title()}
            for t in PaymentProviderType
        ],
        "masked_config": provider.mask_sensitive_config(),
        "app_domain": app_settings.site_domain,
        "_get_provider_description": _get_provider_description
    })


# =============================================================================
# API ENDPOINTS ДЛЯ ПЛАТЕЖНЫХ ПРОВАЙДЕРОВ
# =============================================================================

@router.get("/api/payment-providers")
async def get_payment_providers(
    active_only: bool = False,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
) -> List[PaymentProviderResponse]:
    """Получение списка платежных провайдеров"""
    
    query = select(PaymentProvider).order_by(PaymentProvider.priority, PaymentProvider.id)
    
    if active_only:
        query = query.where(PaymentProvider.is_active == True)
    
    result = await db.execute(query)
    providers = result.scalars().all()
    
    return [
        PaymentProviderResponse(
            **provider.__dict__,
            provider_type=provider.provider_type.value,
            status=provider.status.value,
            success_rate=provider.success_rate,
            is_healthy=provider.is_healthy,
            masked_config=provider.mask_sensitive_config()
        )
        for provider in providers
    ]


@router.get("/api/payment-providers/{provider_id}")
async def get_payment_provider(
    provider_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
) -> PaymentProviderResponse:
    """Получение конкретного платежного провайдера"""
    
    result = await db.execute(
        select(PaymentProvider).where(PaymentProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    
    # Исключаем конфликтующие поля из __dict__
    provider_dict = {k: v for k, v in provider.__dict__.items() 
                    if k not in ['provider_type', 'status']}
    
    return PaymentProviderResponse(
        **provider_dict,
        provider_type=provider.provider_type.value,
        status=provider.status.value,
        success_rate=provider.success_rate,
        is_healthy=provider.is_healthy,
        masked_config=provider.mask_sensitive_config()
    )


@router.post("/api/payment-providers")
async def create_payment_provider(
    provider_data: PaymentProviderCreate,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
) -> PaymentProviderResponse:
    """Создание нового платежного провайдера"""
    
    # Проверяем, что провайдер по умолчанию только один для типа
    if provider_data.is_default:
        await _ensure_single_default_provider(db, provider_data.provider_type)
    
    # Создаем провайдера
    provider = PaymentProvider(
        name=provider_data.name,
        provider_type=provider_data.provider_type,
        description=provider_data.description,
        is_active=provider_data.is_active,
        is_test_mode=provider_data.is_test_mode,
        is_default=provider_data.is_default,
        config=provider_data.config,
        webhook_url=provider_data.webhook_url,
        priority=provider_data.priority,
        min_amount=provider_data.min_amount,
        max_amount=provider_data.max_amount,
        commission_percent=provider_data.commission_percent,
        commission_fixed=provider_data.commission_fixed,
        success_url=provider_data.success_url,
        failure_url=provider_data.failure_url,
        notification_url=provider_data.notification_url,
        notification_method=provider_data.notification_method,
        status=PaymentProviderStatus.inactive
    )
    
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    
    # Исключаем конфликтующие поля из __dict__
    provider_dict = {k: v for k, v in provider.__dict__.items() 
                    if k not in ['provider_type', 'status']}
    
    return PaymentProviderResponse(
        **provider_dict,
        provider_type=provider.provider_type.value,
        status=provider.status.value,
        success_rate=provider.success_rate,
        is_healthy=provider.is_healthy,
        masked_config=provider.mask_sensitive_config()
    )


@router.put("/api/payment-providers/{provider_id}")
async def update_payment_provider(
    provider_id: int,
    provider_data: PaymentProviderUpdate,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
) -> PaymentProviderResponse:
    """Обновление платежного провайдера"""
    
    result = await db.execute(
        select(PaymentProvider).where(PaymentProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    
    # Проверяем провайдера по умолчанию
    if provider_data.is_default and provider_data.is_default != provider.is_default:
        await _ensure_single_default_provider(db, provider.provider_type, provider_id)
    
    # Обновляем поля
    update_data = provider_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(provider, field, value)
    
    provider.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(provider)
    
    # Очищаем кэш процессоров
    payment_processor_manager.clear_cache()
    
    # Исключаем конфликтующие поля из __dict__
    provider_dict = {k: v for k, v in provider.__dict__.items() 
                    if k not in ['provider_type', 'status']}
    
    return PaymentProviderResponse(
        **provider_dict,
        provider_type=provider.provider_type.value,
        status=provider.status.value,
        success_rate=provider.success_rate,
        is_healthy=provider.is_healthy,
        masked_config=provider.mask_sensitive_config()
    )


@router.delete("/api/payment-providers/{provider_id}")
async def delete_payment_provider(
    provider_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Удаление платежного провайдера"""
    
    result = await db.execute(
        select(PaymentProvider).where(PaymentProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Провайдер не найден")
    
    # Проверяем, что у провайдера нет активных платежей
    # (здесь можно добавить проверку через связанные платежи)
    
    await db.execute(
        delete(PaymentProvider).where(PaymentProvider.id == provider_id)
    )
    await db.commit()
    
    # Очищаем кэш процессоров
    payment_processor_manager.clear_cache()
    
    return {"message": "Провайдер удален успешно", "provider_id": provider_id}





@router.get("/api/payment-providers/stats")
async def get_payment_providers_stats(
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
) -> PaymentProviderDashboardStats:
    """Получение статистики платежных провайдеров"""
    
    return await _get_payment_provider_dashboard_stats(db)


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ПЛАТЕЖНЫХ ПРОВАЙДЕРОВ
# =============================================================================

async def _ensure_single_default_provider(
    db: AsyncSession, 
    provider_type: PaymentProviderType, 
    exclude_id: int = None
):
    """Обеспечение единственного провайдера по умолчанию для типа"""
    
    query = select(PaymentProvider).where(
        PaymentProvider.provider_type == provider_type,
        PaymentProvider.is_default == True
    )
    
    if exclude_id:
        query = query.where(PaymentProvider.id != exclude_id)
    
    result = await db.execute(query)
    existing_defaults = result.scalars().all()
    
    for provider in existing_defaults:
        provider.is_default = False
    
    await db.commit()


async def _get_payment_provider_dashboard_stats(db: AsyncSession) -> PaymentProviderDashboardStats:
    """Получение статистики для дашборда платежных провайдеров"""
    
    # Статистика провайдеров
    provider_result = await db.execute(select(PaymentProvider))
    providers = provider_result.scalars().all()
    
    total_providers = len(providers)
    active_providers = len([p for p in providers if p.is_active])
    
    # Статистика платежей за сегодня
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    payments_today_result = await db.execute(
        select(Payment).where(
            Payment.created_at >= today_start,
            Payment.created_at <= today_end
        )
    )
    payments_today = payments_today_result.scalars().all()
    
    total_payments_today = len(payments_today)
    successful_payments_today = len([p for p in payments_today if p.status == PaymentStatus.SUCCEEDED])
    total_amount_today = sum([p.amount for p in payments_today if p.status == PaymentStatus.SUCCEEDED])
    success_rate_today = (successful_payments_today / total_payments_today * 100) if total_payments_today > 0 else 0.0
    
    return PaymentProviderDashboardStats(
        total_providers=total_providers,
        active_providers=active_providers,
        total_payments_today=total_payments_today,
        total_amount_today=total_amount_today,
        success_rate_today=success_rate_today
    )


# NEW: Country Management Routes

@router.get("/countries", response_class=HTMLResponse)
async def admin_countries_page(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница управления странами VPN серверов"""
    try:
        country_service = CountryService(db)
        
        # Получаем все страны (включая неактивные)
        result = await db.execute(select(Country).order_by(Country.priority.desc(), Country.name))
        countries = result.scalars().all()
        
        # Получаем статистику по каждой стране
        countries_stats = []
        for country in countries:
            # Получаем ноды для страны
            nodes = await country_service.get_nodes_by_country(country.id)
            
            # Подсчитываем статистику
            total_nodes = len(nodes)
            healthy_nodes = len([n for n in nodes if n.is_healthy])
            total_capacity = sum(n.max_users for n in nodes)
            current_users = sum(n.current_users for n in nodes)
            
            # Получаем количество назначений пользователей
            assignments_result = await db.execute(
                select(func.count(UserServerAssignment.user_id)).where(
                    UserServerAssignment.country_id == country.id
                )
            )
            user_assignments = assignments_result.scalar() or 0
            
            countries_stats.append({
                "country": country,
                "total_nodes": total_nodes,
                "healthy_nodes": healthy_nodes,
                "total_capacity": total_capacity,
                "current_users": current_users,
                "user_assignments": user_assignments,
                "load_percentage": (current_users / total_capacity * 100) if total_capacity > 0 else 0
            })
        
        return templates.TemplateResponse(
            "admin/countries/list.html",
            {
                "request": request,
                "countries_stats": countries_stats,
                "title": "Управление странами"
            }
        )
        
    except Exception as e:
        logger.error("Error loading countries page", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")


@router.get("/countries/{country_id}/nodes", response_class=HTMLResponse)
async def admin_country_nodes_page(
    country_id: int,
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница управления нодами в стране"""
    try:
        country_service = CountryService(db)
        
        # Получаем страну
        country = await country_service.get_country_by_id(country_id)
        if not country:
            raise HTTPException(status_code=404, detail="Страна не найдена")
        
        # Получаем ноды для страны
        country_nodes = await country_service.get_nodes_by_country(country_id)
        
        # Получаем все ноды без страны для возможности назначения
        unassigned_nodes_result = await db.execute(
            select(VPNNode).where(VPNNode.country_id.is_(None))
        )
        unassigned_nodes = unassigned_nodes_result.scalars().all()
        
        return templates.TemplateResponse(
            "admin/countries/nodes.html",
            {
                "request": request,
                "country": country,
                "country_nodes": country_nodes,
                "unassigned_nodes": unassigned_nodes,
                "title": f"Ноды страны {country.name}"
            }
        )
        
    except Exception as e:
        logger.error("Error loading country nodes page", country_id=country_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")


@router.post("/countries/{country_id}/assign-node/{node_id}")
async def assign_node_to_country(
    country_id: int,
    node_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Назначить ноду на страну"""
    try:
        # Проверяем существование страны и ноды
        country = await db.get(Country, country_id)
        node = await db.get(VPNNode, node_id)
        
        if not country:
            raise HTTPException(status_code=404, detail="Страна не найдена")
        if not node:
            raise HTTPException(status_code=404, detail="Нода не найдена")
        
        # Назначаем ноду на страну
        node.country_id = country_id
        await db.commit()
        
        logger.info("Node assigned to country", 
                   node_id=node_id, 
                   country_id=country_id,
                   admin=current_admin)
        
        return RedirectResponse(
            url=f"/admin/countries/{country_id}/nodes",
            status_code=303
        )
        
    except Exception as e:
        logger.error("Error assigning node to country", 
                    node_id=node_id, 
                    country_id=country_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка назначения: {str(e)}")


@router.post("/countries/{country_id}/unassign-node/{node_id}")
async def unassign_node_from_country(
    country_id: int,
    node_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Отменить назначение ноды от страны"""
    try:
        node = await db.get(VPNNode, node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Нода не найдена")
        
        # Убираем назначение
        node.country_id = None
        await db.commit()
        
        logger.info("Node unassigned from country", 
                   node_id=node_id, 
                   country_id=country_id,
                   admin=current_admin)
        
        return RedirectResponse(
            url=f"/admin/countries/{country_id}/nodes",
            status_code=303
        )
        
    except Exception as e:
        logger.error("Error unassigning node from country", 
                    node_id=node_id, 
                    country_id=country_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка отмены назначения: {str(e)}")


@router.get("/countries/logs", response_class=HTMLResponse)
async def admin_country_switch_logs(
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Страница логов переключения серверов"""
    try:
        # Получаем последние 100 логов переключений
        result = await db.execute(
            select(ServerSwitchLog)
            .order_by(ServerSwitchLog.created_at.desc())
            .limit(100)
        )
        switch_logs = result.scalars().all()
        
        # Получаем информацию о нодах для логов
        logs_with_details = []
        for log in switch_logs:
            from_node = None
            to_node = None
            
            if log.from_node_id:
                from_node = await db.get(VPNNode, log.from_node_id)
            if log.to_node_id:
                to_node = await db.get(VPNNode, log.to_node_id)
            
            logs_with_details.append({
                "log": log,
                "from_node": from_node,
                "to_node": to_node
            })
        
        return templates.TemplateResponse(
            "admin/countries/switch_logs.html",
            {
                "request": request,
                "logs_with_details": logs_with_details,
                "title": "Логи переключения серверов"
            }
        )
        
    except Exception as e:
        logger.error("Error loading switch logs page", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки: {str(e)}")


@router.get("/api/countries/stats")
async def api_countries_stats(
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """API для получения статистики стран"""
    try:
        country_service = CountryService(db)
        countries = await country_service.get_available_countries()
        
        stats = []
        for country in countries:
            nodes = await country_service.get_nodes_by_country(country.id)
            
            total_nodes = len(nodes)
            healthy_nodes = len([n for n in nodes if n.is_healthy])
            total_capacity = sum(n.max_users for n in nodes)
            current_users = sum(n.current_users for n in nodes)
            
            stats.append({
                "country": country.to_dict(),
                "nodes_total": total_nodes,
                "nodes_healthy": healthy_nodes,
                "total_capacity": total_capacity,
                "current_users": current_users,
                "load_percentage": (current_users / total_capacity * 100) if total_capacity > 0 else 0
            })
        
        return {"countries": stats}
        
    except Exception as e:
        logger.error("Error getting countries stats", error=str(e))
        return {"error": str(e)}


@router.get("/countries/create", response_class=HTMLResponse)
async def admin_create_country_form(
    request: Request,
    current_admin: str = Depends(get_current_admin)
):
    """Форма создания новой страны"""
    return templates.TemplateResponse(
        "admin/countries/create.html",
        {
            "request": request,
            "title": "Добавить страну"
        }
    )


@router.post("/countries/create")
async def admin_create_country(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    name_en: str = Form(""),
    flag_emoji: str = Form(...),
    priority: int = Form(100),
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Создание новой страны"""
    try:
        # Проверяем что код страны уникален
        existing_country = await db.execute(select(Country).where(Country.code == code.upper()))
        if existing_country.scalar_one_or_none():
            return templates.TemplateResponse(
                "admin/countries/create.html",
                {
                    "request": request,
                    "title": "Добавить страну",
                    "error": f"Страна с кодом {code.upper()} уже существует"
                }
            )
        
        # Создаем новую страну
        new_country = Country(
            code=code.upper(),
            name=name,
            name_en=name_en or name,
            flag_emoji=flag_emoji,
            priority=priority,
            is_active=True
        )
        
        db.add(new_country)
        await db.commit()
        
        logger.info("Country created successfully", country_code=code, name=name)
        return RedirectResponse(url="/admin/countries", status_code=303)
        
    except Exception as e:
        logger.error("Error creating country", error=str(e))
        return templates.TemplateResponse(
            "admin/countries/create.html",
            {
                "request": request,
                "title": "Добавить страну",
                "error": f"Ошибка создания страны: {str(e)}"
            }
        )

# =============================================================================
# USER DELETION MANAGEMENT
# =============================================================================

@router.get("/users/{user_id}/deletion-preview")
async def get_user_deletion_preview(
    user_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """API получения превью удаления пользователя"""
    try:
        deletion_service = get_user_deletion_service(db)
        preview = await deletion_service.get_user_deletion_preview(user_id)
        
        if "error" in preview:
            raise HTTPException(status_code=404, detail=preview["error"])
        
        logger.info("User deletion preview generated", 
                   user_id=user_id, 
                   admin_user=current_admin,
                   can_delete=preview.get("can_delete", False))
        
        return {
            "success": True,
            "preview": preview
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating user deletion preview", 
                    user_id=user_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка получения превью удаления")


@router.delete("/users/{user_id}")
async def delete_user_completely(
    user_id: int,
    request: Request,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """API полного удаления пользователя из системы"""
    try:
        # Получаем данные из тела запроса
        body = await request.json()
        confirmation = body.get("confirmation", "")
        force_delete = body.get("force_delete", False)
        
        # Валидация подтверждения
        if not confirmation:
            raise HTTPException(status_code=400, detail="Требуется подтверждение удаления")
        
        # Получаем информацию о пользователе для проверки подтверждения
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Проверяем подтверждение (имя пользователя или telegram_id)
        expected_confirmations = [
            user.username,
            user.first_name,
            str(user.telegram_id),
            f"{user.first_name} {user.last_name}".strip()
        ]
        expected_confirmations = [c for c in expected_confirmations if c]
        
        if confirmation not in expected_confirmations:
            raise HTTPException(
                status_code=400, 
                detail="Неверное подтверждение. Введите имя пользователя, username или Telegram ID"
            )
        
        logger.info("Starting user deletion process", 
                   user_id=user_id, 
                   admin_user=current_admin,
                   force_delete=force_delete,
                   confirmation_used=confirmation)
        
        # Выполняем удаление
        deletion_service = get_user_deletion_service(db)
        result = await deletion_service.delete_user_completely(
            user_id=user_id,
            admin_user=current_admin,
            force_delete=force_delete
        )
        
        # Форматируем ответ
        response_data = {
            "success": result.success,
            "user_id": result.user_id,
            "user_telegram_id": result.user_telegram_id,
            "username": result.username,
            "deletion_summary": {
                "vpn_keys_found": result.vpn_keys_found,
                "vpn_keys_deleted": result.vpn_keys_deleted,
                "database_cleanup_success": result.database_cleanup_success,
                "total_duration_seconds": result.total_duration_seconds
            },
            "x3ui_deletions": [
                {
                    "vpn_key_id": d.vpn_key_id,
                    "node_name": d.node_name,
                    "success": d.x3ui_success,
                    "error": d.error_message
                }
                for d in result.x3ui_deletions
            ],
            "errors": result.errors,
            "warnings": result.warnings
        }
        
        if result.success:
            logger.info("User deletion completed successfully", 
                       user_id=user_id, 
                       admin_user=current_admin,
                       duration=result.total_duration_seconds)
            
            response_data["message"] = "Пользователь успешно удален из системы"
        else:
            logger.error("User deletion failed", 
                        user_id=user_id, 
                        admin_user=current_admin,
                        errors=result.errors)
            
            response_data["message"] = "Удаление пользователя завершилось с ошибками"
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Critical error during user deletion API", 
                    user_id=user_id, 
                    error=str(e),
                    exc_info=True)
        raise HTTPException(status_code=500, detail="Критическая ошибка при удалении пользователя")


@router.post("/users/{user_id}/deletion-check")
async def check_user_deletion_safety(
    user_id: int,
    current_admin: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Проверка безопасности удаления пользователя"""
    try:
        deletion_service = get_user_deletion_service(db)
        
        # Получаем превью удаления
        preview = await deletion_service.get_user_deletion_preview(user_id)
        
        if "error" in preview:
            raise HTTPException(status_code=404, detail=preview["error"])
        
        # Анализируем безопасность удаления
        safety_analysis = {
            "can_delete_safely": preview.get("can_delete", False),
            "blockers": preview.get("blockers", []),
            "impact_assessment": {
                "vpn_keys_to_delete": preview["deletion_preview"]["vpn_keys"],
                "related_records_to_clean": (
                    preview["deletion_preview"]["server_assignments"] +
                    preview["deletion_preview"]["switch_logs"] +
                    preview["deletion_preview"]["auto_payments"]
                ),
                "payments_to_preserve": preview["deletion_preview"]["payments_to_update"]
            },
            "recommendations": []
        }
        
        # Добавляем рекомендации
        if preview["deletion_preview"]["vpn_keys"] > 0:
            safety_analysis["recommendations"].append(
                f"Будет удалено {preview['deletion_preview']['vpn_keys']} VPN ключей"
            )
        
        if preview["deletion_preview"]["payments_to_update"] > 0:
            safety_analysis["recommendations"].append(
                f"У пользователя есть {preview['deletion_preview']['payments_to_update']} платежей - они сохранятся, но ссылка на пользователя будет удалена"
            )
        
        if not preview.get("can_delete", False):
            safety_analysis["recommendations"].append(
                "Удаление заблокировано - устраните блокирующие условия или используйте принудительное удаление"
            )
        
        return {
            "success": True,
            "safety_analysis": safety_analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error checking user deletion safety", 
                    user_id=user_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка проверки безопасности удаления")


# =============================================================================
# APP SETTINGS MANAGEMENT
# =============================================================================

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request, 
    admin=Depends(get_current_admin), 
    db: AsyncSession = Depends(get_db)
):
    """Страница настроек приложения"""
    try:
        from services.app_settings_service import AppSettingsService
        
        # Получаем текущие настройки
        settings = await AppSettingsService.get_settings(db)
        
        context = {
            "request": request,
            "current_admin": admin,
            "settings": settings,
            "page_title": "Настройки приложения"
        }
        
        return templates.TemplateResponse("admin/settings.html", context)
        
    except Exception as e:
        logger.error("Error loading settings page", error=str(e))
        import traceback
        logger.error("Full traceback:", error=traceback.format_exc())
        raise HTTPException(status_code=500, detail="Ошибка загрузки страницы настроек")


@router.post("/settings")
async def update_settings(
    request: Request,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Обновление настроек приложения"""
    try:
        from services.app_settings_service import AppSettingsService
        
        # Получаем данные формы
        form_data = await request.form()
        
        # Преобразуем данные формы в словарь
        settings_data = {}
        
        # Явно обрабатываем чекбокс trial_enabled (он отсутствует в форме, если не отмечен)
        settings_data['trial_enabled'] = 'trial_enabled' in form_data and form_data['trial_enabled'] == 'on'
        
        for key, value in form_data.items():
            if key == 'trial_enabled':
                settings_data[key] = value == 'on'
            elif key in ['trial_days', 'trial_max_per_user', 'token_expire_minutes']:
                try:
                    settings_data[key] = int(value) if value else 0
                except ValueError:
                    continue
            else:
                settings_data[key] = value
        
        # Обновляем настройки
        updated_settings = await AppSettingsService.update_settings(db, settings_data)
        
        # Добавляем сообщение об успехе
        success_message = "Настройки успешно обновлены"
        
        context = {
            "request": request,
            "current_admin": admin,
            "settings": updated_settings,
            "page_title": "Настройки приложения",
            "success_message": success_message
        }
        
        return templates.TemplateResponse("admin/settings.html", context)
        
    except Exception as e:
        logger.error("Error updating settings", error=str(e))
        
        # Возвращаем страницу с ошибкой
        from services.app_settings_service import AppSettingsService
        settings = await AppSettingsService.get_settings(db)
        
        context = {
            "request": request,
            "current_admin": admin,
            "settings": settings,
            "page_title": "Настройки приложения",
            "error_message": f"Ошибка обновления настроек: {str(e)}"
        }
        
        return templates.TemplateResponse("admin/settings.html", context)


@router.post("/settings/reset")
async def reset_settings(
    request: Request,
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Сброс настроек к значениям по умолчанию"""
    try:
        from services.app_settings_service import AppSettingsService
        
        # Сбрасываем настройки
        default_settings = await AppSettingsService.reset_to_defaults(db)
        
        # Добавляем сообщение об успехе
        success_message = "Настройки сброшены к значениям по умолчанию"
        
        context = {
            "request": request,
            "admin": admin,
            "settings": default_settings,
            "page_title": "Настройки приложения",
            "success_message": success_message
        }
        
        return templates.TemplateResponse("admin/settings.html", context)
        
    except Exception as e:
        logger.error("Error resetting settings", error=str(e))
        
        # Возвращаем страницу с ошибкой
        from services.app_settings_service import AppSettingsService
        settings = await AppSettingsService.get_settings(db)
        
        context = {
            "request": request,
            "admin": admin,
            "settings": settings,
            "page_title": "Настройки приложения",
            "error_message": f"Ошибка сброса настроек: {str(e)}"
        }
        
        return templates.TemplateResponse("admin/settings.html", context)


@router.get("/settings/api")
async def get_settings_api(
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """API для получения настроек (JSON)"""
    try:
        from services.app_settings_service import AppSettingsService
        
        settings = await AppSettingsService.get_settings(db)
        
        return {
            "success": True,
            "settings": {
                "id": settings.id,
                "site_name": settings.site_name,
                "site_domain": settings.site_domain,
                "site_description": settings.site_description,
                "trial_enabled": settings.trial_enabled,
                "trial_days": settings.trial_days,
                "trial_max_per_user": settings.trial_max_per_user,
                "token_expire_minutes": settings.token_expire_minutes,
                "admin_telegram_ids": settings.admin_telegram_ids_list,
                "admin_usernames": settings.admin_usernames_list,
                "telegram_bot_token": settings.telegram_bot_token,
                "bot_welcome_message": settings.bot_welcome_message,
                "bot_help_message": settings.bot_help_message,
                "bot_apps_message": settings.bot_apps_message,
                "updated_at": settings.updated_at.isoformat() if settings.updated_at else None
            }
        }
        
    except Exception as e:
        logger.error("Error getting settings via API", error=str(e))
        raise HTTPException(status_code=500, detail="Ошибка получения настроек")