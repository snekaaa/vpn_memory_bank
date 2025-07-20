"""
Bot models module
Модели данных для бота
"""

# Исправленный импорт для backend services
import sys
import os
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