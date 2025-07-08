"""
Pydantic schemas для Admin API
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class AdminLoginRequest(BaseModel):
    """Схема для входа в админку"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)

class AdminLoginResponse(BaseModel):
    """Ответ на успешный вход"""
    message: str
    username: str
    session_expires: datetime

class UserListItem(BaseModel):
    """Элемент списка пользователей"""
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str] 
    last_name: Optional[str]
    is_active: bool
    is_blocked: bool
    created_at: datetime
    last_activity: Optional[datetime]
    vpn_keys_count: int
    
    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    """Ответ со списком пользователей"""
    items: List[UserListItem]
    total: int
    page: int
    size: int
    pages: int

class VPNKeyListItem(BaseModel):
    """Элемент списка VPN ключей"""
    id: int
    user_id: int
    key_name: str
    status: str
    created_at: datetime
    expires_at: Optional[datetime]
    total_download: int
    total_upload: int
    last_connection: Optional[datetime]
    
    # Информация о пользователе
    user_telegram_id: int
    user_username: Optional[str]
    
    class Config:
        from_attributes = True

class VPNKeyListResponse(BaseModel):
    """Ответ со списком VPN ключей"""
    items: List[VPNKeyListItem]
    total: int
    page: int
    size: int
    pages: int

class DashboardStats(BaseModel):
    """Статистика для дашборда"""
    total_users: int
    active_users: int
    blocked_users: int
    total_vpn_keys: int
    active_vpn_keys: int
    total_traffic_gb: float
    recent_registrations: int  # За последние 24 часа
    recent_connections: int   # За последние 24 часа
    active_accounts: int  # Пользователи с активными аккаунтами (упрощенная архитектура)
    expired_accounts: int  # Пользователи с истекшими аккаунтами
    total_payments: int
    completed_payments: int
    total_revenue: float

class UserUpdateRequest(BaseModel):
    """Запрос на обновление пользователя"""
    is_active: Optional[bool] = None
    is_blocked: Optional[bool] = None

class ErrorResponse(BaseModel):
    """Стандартный ответ с ошибкой"""
    error: str
    detail: Optional[str] = None

# Manual Payment Management Schemas
from typing import Dict, Any

class ManualPaymentCreateRequest(BaseModel):
    """Схема для создания ручного платежа"""
    user_id: int
    amount: float = Field(..., ge=0)
    description: str = Field(..., min_length=1, max_length=500)
    payment_method: str  # manual_admin, manual_trial, manual_correction
    subscription_days: Optional[int] = Field(None, ge=1, le=3650)  # Количество дней подписки
    metadata: Optional[Dict[str, Any]] = None

class PaymentStatusUpdateRequest(BaseModel):
    """Схема для изменения статуса платежа"""
    new_status: str  # PENDING, SUCCEEDED, FAILED, CANCELLED
    reason: Optional[str] = None

class UserPaymentHistoryResponse(BaseModel):
    """Схема ответа с историей платежей пользователя"""
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    telegram_id: int
    payments: List[Dict[str, Any]]
    total_payments: int
    total_amount: float 