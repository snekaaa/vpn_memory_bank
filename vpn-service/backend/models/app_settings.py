"""
App Settings Model
Модель для централизованного управления настройками приложения
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, CheckConstraint
from sqlalchemy.sql import func
from datetime import datetime
import json
from typing import List

from .database import Base


class AppSettings(Base):
    """
    Модель настроек приложения
    Singleton pattern - только одна запись настроек (id = 1)
    """
    __tablename__ = "app_settings"
    
    # Primary key & metadata
    id = Column(Integer, primary_key=True, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Site Configuration
    site_name = Column(String(255), nullable=False, default='VPN Service')
    site_domain = Column(String(255), nullable=True)
    site_description = Column(Text, nullable=True)
    
    # User/Trial Settings
    trial_enabled = Column(Boolean, nullable=False, default=True)
    trial_days = Column(Integer, nullable=False, default=7)
    trial_max_per_user = Column(Integer, nullable=False, default=1)
    
    # Security Settings  
    token_expire_minutes = Column(Integer, nullable=False, default=30)
    admin_telegram_ids = Column(Text, nullable=False, default='[]')  # JSON array
    admin_usernames = Column(Text, nullable=False, default='[]')     # JSON array  
    
    # Bot Settings
    telegram_bot_token = Column(String(255), nullable=True)
    bot_welcome_message = Column(Text, nullable=True)
    bot_help_message = Column(Text, nullable=True)
    bot_apps_message = Column(Text, nullable=True, default='Скачайте приложения для вашего устройства:')
    
    # Constraints для singleton pattern и валидации
    __table_args__ = (
        CheckConstraint('id = 1', name='single_settings_row'),
        CheckConstraint('trial_days >= 0', name='trial_days_non_negative'),
        CheckConstraint('trial_max_per_user >= 0', name='trial_max_per_user_non_negative'),
        CheckConstraint('token_expire_minutes > 0', name='token_expire_minutes_positive'),
    )
    
    @property 
    def admin_telegram_ids_list(self) -> List[str]:
        """Получить список admin telegram IDs как список строк"""
        try:
            return json.loads(self.admin_telegram_ids) if self.admin_telegram_ids else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    @admin_telegram_ids_list.setter
    def admin_telegram_ids_list(self, value: List[str]):
        """Установить список admin telegram IDs"""
        self.admin_telegram_ids = json.dumps(value)
    
    @property
    def admin_usernames_list(self) -> List[str]:
        """Получить список admin usernames как список строк"""
        try:
            return json.loads(self.admin_usernames) if self.admin_usernames else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    @admin_usernames_list.setter 
    def admin_usernames_list(self, value: List[str]):
        """Установить список admin usernames"""
        self.admin_usernames = json.dumps(value)
    
    def __repr__(self):
        return f"<AppSettings(id={self.id}, site_name='{self.site_name}', updated_at={self.updated_at})>" 