"""
User model for bot
"""

import sys
import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from sqlalchemy.orm import relationship

# Исправленный импорт для backend services
sys.path.append(os.path.join(os.path.dirname(__file__), '../../backend'))

try:
    from models.database import Base
except ImportError:
    try:
        from config.database import Base
    except ImportError:
        # Fallback - создаем простую заглушку
        from sqlalchemy.ext.declarative import declarative_base
        Base = declarative_base()

class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Отношения
    vpn_keys = relationship("VPNKey", back_populates="user", lazy="joined")
    subscriptions = relationship("Subscription", back_populates="user", lazy="joined")
    payments = relationship("Payment", back_populates="user", lazy="joined")
    node_assignments = relationship("UserNodeAssignment", back_populates="user", lazy="joined") 