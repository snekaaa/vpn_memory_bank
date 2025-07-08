from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class UserNodeAssignment(Base):
    """Модель привязки пользователя к серверной ноде"""
    __tablename__ = "user_node_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(Integer, ForeignKey("vpn_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Assignment details
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True, index=True)
    
    # X3UI specific details
    xui_inbound_id = Column(Integer)
    xui_client_email = Column(String(255))
    
    # Relationships - временно убираем back_populates для избежания circular imports
    user = relationship("User", lazy="select")
    node = relationship("VPNNode", lazy="select")
    
    def __repr__(self):
        return f"<UserNodeAssignment(id={self.id}, user_id={self.user_id}, node_id={self.node_id}, active={self.is_active})>"
    
    @property
    def is_current_assignment(self) -> bool:
        """Проверяет является ли это текущим активным assignment"""
        return self.is_active 