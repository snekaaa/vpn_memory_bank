"""
Модель ServerSwitchLog для аудита переключений серверов пользователями
"""

from sqlalchemy import Column, Integer, BigInteger, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from config.database import Base


class ServerSwitchLog(Base):
    """Модель для логирования переключений серверов пользователями"""
    __tablename__ = "server_switch_log"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)  # Telegram user ID
    from_node_id = Column(Integer, ForeignKey("vpn_nodes.id"), nullable=True)  # Может быть NULL для первого назначения
    to_node_id = Column(Integer, ForeignKey("vpn_nodes.id"), nullable=False)
    country_code = Column(String(2), nullable=False)  # Код страны для быстрого поиска
    success = Column(Boolean, default=False, nullable=False)  # Успешно ли прошло переключение
    error_message = Column(Text, nullable=True)  # Сообщение об ошибке если success=False
    processing_time_ms = Column(Integer, nullable=True)  # Время обработки в миллисекундах
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<ServerSwitchLog(id={self.id}, user_id={self.user_id}, from_node={self.from_node_id}, to_node={self.to_node_id}, success={self.success})>"
    
    def to_dict(self) -> dict:
        """Преобразует модель в словарь для API"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "country_code": self.country_code,
            "success": self.success,
            "error_message": self.error_message,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None
        } 