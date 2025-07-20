"""
VPN Key model for bot
"""

import sys
import os
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum, func
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

class VPNKeyStatus(enum.Enum):
    """Статусы VPN ключа"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    DELETED = "deleted"

class VPNKey(Base):
    """Модель VPN ключа"""
    __tablename__ = "vpn_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_id = Column(String, unique=True, index=True)
    key_value = Column(String, nullable=False)
    status = Column(Enum(VPNKeyStatus), default=VPNKeyStatus.ACTIVE)
    expiration_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    node_id = Column(Integer, ForeignKey("vpn_nodes.id"), nullable=True)
    
    # Отношения
    user = relationship("User", back_populates="vpn_keys")
    node = relationship("VPNNode", back_populates="vpn_keys") 