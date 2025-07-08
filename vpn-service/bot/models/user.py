"""
Модель пользователя для бота
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from services.vpn_manager import Base

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