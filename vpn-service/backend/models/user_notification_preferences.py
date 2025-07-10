from sqlalchemy import Column, Integer, String, DateTime, Time, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base

class UserNotificationPreferences(Base):
    """Модель настроек уведомлений пользователя"""
    __tablename__ = "user_notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Тип и настройки уведомлений
    notification_type = Column(String(50), nullable=False)  # 'autopay_success', 'autopay_failure', etc.
    enabled = Column(Boolean, default=True)
    frequency = Column(String(20), default="all")  # 'all', 'daily', 'weekly'
    
    # Тихие часы
    quiet_hours_start = Column(Time, nullable=True)
    quiet_hours_end = Column(Time, nullable=True)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Уникальность комбинации user_id + notification_type
    __table_args__ = (
        UniqueConstraint('user_id', 'notification_type', name='_user_notification_type_uc'),
    )
    
    # Связи
    # user = relationship("User", back_populates="notification_preferences")
    
    def __repr__(self):
        return f"<UserNotificationPreferences(user_id={self.user_id}, type={self.notification_type}, enabled={self.enabled})>"
    
    @property
    def has_quiet_hours(self) -> bool:
        """Проверка наличия тихих часов"""
        return self.quiet_hours_start is not None and self.quiet_hours_end is not None
    
    def is_quiet_time(self, check_time: Time) -> bool:
        """Проверка, находится ли время в тихих часах"""
        if not self.has_quiet_hours:
            return False
        
        start = self.quiet_hours_start
        end = self.quiet_hours_end
        
        # Если конец после начала (например, 22:00 - 08:00)
        if start > end:
            return check_time >= start or check_time <= end
        else:
            return start <= check_time <= end 