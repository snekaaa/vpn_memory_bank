"""
Модель VPN ключа для бота
"""

import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from services.vpn_manager import Base

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