"""
Модель Country для управления странами VPN серверов
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from config.database import Base


class Country(Base):
    """Модель страны для VPN серверов"""
    __tablename__ = "countries"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(2), unique=True, nullable=False, index=True)  # ISO 3166-1 alpha-2 (RU, NL, DE)
    name = Column(String(100), nullable=False)  # "Россия", "Нидерланды", "Германия"
    name_en = Column(String(100))  # "Russia", "Netherlands", "Germany"
    flag_emoji = Column(String(10), nullable=False)  # "🇷🇺", "🇳🇱", "🇩🇪"
    is_active = Column(Boolean, default=True, nullable=False)  # Can users select this country?
    priority = Column(Integer, default=100, nullable=False)  # Display order (higher = first)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user_assignments = relationship("UserServerAssignment", back_populates="country")
    
    def __repr__(self):
        return f"<Country(id={self.id}, code={self.code}, name={self.name})>"
    
    @property
    def display_name(self) -> str:
        """Возвращает название с флагом для отображения"""
        return f"{self.flag_emoji} {self.name}"
    
    def to_dict(self) -> dict:
        """Преобразует модель в словарь для API"""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "name_en": self.name_en,
            "flag_emoji": self.flag_emoji,
            "is_active": self.is_active,
            "priority": self.priority,
            "display_name": self.display_name
        } 