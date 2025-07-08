"""
Admin Authentication System
Session-based authentication для админки
"""

from fastapi import Request, HTTPException, Depends
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional
import os

# Session storage (в продакшене использовать Redis)
active_sessions: Dict[str, dict] = {}

class AdminAuth:
    def __init__(self):
        # В продакшене брать из переменных окружения
        self.admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "secure_admin_123")
        self.admin_password_hash = self.hash_password(admin_password)
        
    def hash_password(self, password: str) -> str:
        """Хешируем пароль с солью"""
        salt = "vpn_admin_salt_2025"
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def verify_password(self, username: str, password: str) -> bool:
        """Проверяем учетные данные"""
        if username != self.admin_username:
            return False
        return self.hash_password(password) == self.admin_password_hash
    
    def create_session(self, username: str) -> str:
        """Создаем новую сессию"""
        session_id = secrets.token_urlsafe(32)
        active_sessions[session_id] = {
            "username": username,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=8),
            "last_activity": datetime.utcnow()
        }
        return session_id
    
    def verify_session(self, session_id: str) -> bool:
        """Проверяем валидность сессии"""
        if not session_id or session_id not in active_sessions:
            return False
        
        session = active_sessions[session_id]
        if datetime.utcnow() > session["expires_at"]:
            # Удаляем просроченную сессию
            del active_sessions[session_id]
            return False
        
        # Обновляем время последней активности
        session["last_activity"] = datetime.utcnow()
        return True
    
    def destroy_session(self, session_id: str) -> bool:
        """Удаляем сессию (logout)"""
        if session_id in active_sessions:
            del active_sessions[session_id]
            return True
        return False
    
    def get_session_info(self, session_id: str) -> Optional[dict]:
        """Получаем информацию о сессии"""
        if session_id in active_sessions:
            return active_sessions[session_id]
        return None

# Глобальный экземпляр auth системы
admin_auth = AdminAuth()

async def get_current_admin(request: Request) -> str:
    """Dependency для проверки авторизации администратора"""
    session_id = request.cookies.get("admin_session")
    
    if not session_id or not admin_auth.verify_session(session_id):
        raise HTTPException(
            status_code=401, 
            detail="Unauthorized access. Please login."
        )
    
    session_info = admin_auth.get_session_info(session_id)
    return session_info["username"] if session_info else None

async def optional_admin(request: Request) -> Optional[str]:
    """Опциональная проверка авторизации (для login page)"""
    session_id = request.cookies.get("admin_session")
    
    if session_id and admin_auth.verify_session(session_id):
        session_info = admin_auth.get_session_info(session_id)
        return session_info["username"] if session_info else None
    
    return None 