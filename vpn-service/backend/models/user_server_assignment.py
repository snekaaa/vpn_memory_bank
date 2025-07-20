"""
Модель UserServerAssignment для отслеживания назначений пользователей на VPN серверы
"""

from sqlalchemy import Column, Integer, BigInteger, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base


class UserServerAssignment(Base):
    """Модель для отслеживания текущих назначений пользователей на серверы"""
    __tablename__ = "user_server_assignments"
    
    user_id = Column(BigInteger, primary_key=True, index=True)  # Telegram user ID
    node_id = Column(Integer, ForeignKey("vpn_nodes.id"), nullable=False, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    last_switch_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships (опционально, если нужны)
    node = relationship("VPNNode", back_populates="user_assignments")
    country = relationship("Country", back_populates="user_assignments")
    
    def __repr__(self):
        return f"<UserServerAssignment(user_id={self.user_id}, node_id={self.node_id}, country_id={self.country_id})>"
    
    def to_dict(self) -> dict:
        """Преобразует модель в словарь для API"""
        return {
            "user_id": self.user_id,
            "node_id": self.node_id,
            "country_id": self.country_id,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "last_switch_at": self.last_switch_at.isoformat() if self.last_switch_at else None
        } 