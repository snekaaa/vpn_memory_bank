from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base
import enum

class VPNKeyStatus(str, enum.Enum):
    """Статусы VPN ключа"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"

class VPNKey(Base):
    """Модель VPN ключа"""
    __tablename__ = "vpn_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # subscription_id убрано - упрощенная архитектура
    node_id = Column(Integer, ForeignKey("vpn_nodes.id"), nullable=True)  # ID ноды, на которой создан ключ
    
    # Данные ключа
    uuid = Column(String(36), unique=True, index=True, nullable=False)  # UUID ключа
    key_name = Column(String(255), unique=True, index=True, nullable=True)
    vless_url = Column(Text, nullable=False)  # VLESS URL из базы
    vless_config = Column(Text, nullable=True)  # VLESS конфигурация (дополнительная)
    qr_code_data = Column(Text, nullable=True)   # Данные для QR кода
    
    # Статус ключа
    status = Column(String(20), default="active")
    
    # Данные 3X-UI
    xui_email = Column(String(255), nullable=False, index=True)  # Email для X3UI
    xui_client_id = Column(String(255), unique=True, index=True)  # ID клиента в 3X-UI
    xui_inbound_id = Column(Integer, nullable=True)  # ID inbound в 3X-UI
    
    # Статистика использования
    total_download = Column(Integer, default=0)  # Скачано байт
    total_upload = Column(Integer, default=0)    # Загружено байт
    last_connection = Column(DateTime(timezone=True), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи - закомментированы для избежания circular imports
    # user = relationship("User", lazy="select")
    # subscription связь убрана - упрощенная архитектура
    # node = relationship("VPNNode", lazy="select")
    
    def __repr__(self):
        return f"<VPNKey(id={self.id}, user_id={self.user_id}, key_name={self.key_name}, status={self.status})>"
    
    @property
    def is_active(self) -> bool:
        """Проверка активности ключа"""
        from datetime import datetime, timezone
        if self.status != "active":
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True
    
    @property
    def traffic_used_gb(self) -> float:
        """Использованный трафик в ГБ"""
        total_bytes = self.total_download + self.total_upload
        return round(total_bytes / (1024 ** 3), 2) 