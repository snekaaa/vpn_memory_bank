from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Enum, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base
import enum

class NodeMode(str, enum.Enum):
    """Режим работы ноды"""
    default = "default"
    reality = "reality"

class VPNNode(Base):
    """Модель серверной ноды VPN"""
    __tablename__ = "vpn_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    location = Column(String(100))
    
    # NEW: Связь с таблицей стран
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True, index=True)
    
    # X3UI connection settings
    x3ui_url = Column(String(255), nullable=False)
    x3ui_username = Column(String(100), nullable=False)
    x3ui_password = Column(String(255), nullable=False)
    
    # Reality mode settings - новые поля
    mode = Column(Enum(NodeMode), default=NodeMode.default, nullable=False)
    public_key = Column(Text, nullable=True)  # Reality public key
    short_id = Column(String(32), nullable=True)  # Reality short ID
    sni_mask = Column(String(255), default='apple.com')  # SNI маскировка
    
    # Node capacity and status
    max_users = Column(Integer, default=1000)
    current_users = Column(Integer, default=0)
    status = Column(String, default="active", nullable=False)
    
    # Health monitoring
    last_health_check = Column(DateTime(timezone=True))
    health_status = Column(String, default="unknown", nullable=False)
    response_time_ms = Column(Integer)
    
    # Configuration
    priority = Column(Integer, default=100)  # Higher = preferred
    weight = Column(Float, default=1.0)  # Load balancing weight
    
    # Конфигурация для Reality
    reality_config = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships убраны для избежания circular imports
    user_assignments = relationship("UserServerAssignment", back_populates="node")
    # country = relationship("Country", back_populates="nodes")
    
    def __repr__(self):
        return f"<VPNNode(id={self.id if hasattr(self, 'id') else None}, name={self.name if hasattr(self, 'name') else None})>"
    
    @property
    def load_percentage(self) -> float:
        """Вычисляет процент загрузки ноды"""
        if self.max_users == 0:
            return 100.0
        return (self.current_users / self.max_users) * 100
    
    @property
    def is_healthy(self) -> bool:
        """Проверяет здоровье ноды"""
        return self.status == 'active' and self.health_status == 'healthy'
    
    @property
    def can_accept_users(self) -> bool:
        """Проверяет может ли нода принимать новых пользователей"""
        return (self.is_healthy and 
                self.current_users < self.max_users and 
                self.status == 'active')
    
    def calculate_score(self) -> float:
        """Вычисляет оценку ноды для load balancing (меньше = лучше)"""
        if not self.can_accept_users:
            return float('inf')
        
        load_ratio = self.current_users / self.max_users if self.max_users > 0 else 1.0
        priority_score = self.priority / 100.0
        weight_score = self.weight
        
        # Финальная оценка (меньше = лучше)
        return load_ratio / (priority_score * weight_score) 