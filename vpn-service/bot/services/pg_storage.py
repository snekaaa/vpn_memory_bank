"""
Хранилище данных для VPN ключей, использующее PostgreSQL
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from services.db_manager import DBManager, User, VPNKey

logger = structlog.get_logger(__name__)

class PostgresStorage:
    """PostgreSQL хранилище данных для VPN ключей"""
    
    def __init__(self):
        """Инициализация хранилища"""
        try:
            self.db_manager = DBManager()
            # Используем только синхронную инициализацию для упрощения работы
            self.db_manager.create_tables()
            logger.info("PostgreSQL storage initialized")
        except Exception as e:
            logger.error("Error initializing PostgreSQL storage", error=str(e))
            # Не выбрасываем исключение, чтобы не блокировать запуск бота
    
    def get_user_vpn_keys(self, telegram_id: int) -> List[Dict[str, Any]]:
        """
        Получение всех VPN ключей пользователя
        
        Совместимо с интерфейсом SimpleStorage.get_user_vpn_keys()
        """
        session = self.db_manager.Session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                logger.debug("No user found for telegram_id", telegram_id=telegram_id)
                return []
            
            # Получаем VPN ключи пользователя прямым запросом
            vpn_keys = session.query(VPNKey).filter_by(user_id=user.id).all()
            
            result = []
            for key in vpn_keys:
                # Создаем словарь, совместимый с форматом из SimpleStorage
                key_data = {
                    'id': key.id,
                    'telegram_id': user.telegram_id,
                    'uuid': key.uuid,
                    'vless_url': key.vless_url,
                    'xui_email': key.xui_email,
                    'xui_inbound_id': key.xui_inbound_id,
                    'xui_created': key.xui_created,
                    'subscription_type': key.subscription_type,
                    'created_at': key.created_at.isoformat() if key.created_at else datetime.utcnow().isoformat(),
                    'updated_at': key.updated_at.isoformat() if key.updated_at else None
                }
                result.append(key_data)
            
            logger.debug("Retrieved VPN keys for user", 
                        telegram_id=telegram_id, 
                        count=len(result))
            return result
            
        except Exception as e:
            logger.error("Error getting VPN keys from PostgreSQL", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return []
        finally:
            session.close()
    
    def save_vpn_key(self, key_data: Dict[str, Any]) -> bool:
        """
        Сохранение VPN ключа
        
        Совместимо с интерфейсом SimpleStorage.save_vpn_key()
        """
        session = self.db_manager.Session()
        try:
            # Получаем необходимые данные из словаря
            telegram_id = key_data.get('telegram_id')
            if not telegram_id:
                logger.error("Cannot save VPN key without telegram_id")
                return False
            
            # Получаем или создаем пользователя
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                user = User(telegram_id=telegram_id)
                session.add(user)
                session.flush()  # Получаем ID пользователя
            
            # Создаем VPN ключ
            created_at = datetime.fromisoformat(key_data['created_at']) if key_data.get('created_at') else datetime.utcnow()
            vpn_key = VPNKey(
                user_id=user.id,
                uuid=key_data.get('uuid'),
                vless_url=key_data.get('vless_url'),
                xui_email=key_data.get('xui_email'),
                xui_inbound_id=key_data.get('xui_inbound_id'),
                xui_client_id=key_data.get('uuid'),  # Добавляем xui_client_id = uuid для синхронизации
                xui_created=key_data.get('xui_created', True),
                subscription_type=key_data.get('subscription_type', 'auto'),
                created_at=created_at
            )
            
            session.add(vpn_key)
            session.commit()
            
            # Обновляем ID ключа в исходных данных
            key_data['id'] = vpn_key.id
            
            logger.info("Successfully saved VPN key to PostgreSQL", 
                       key_id=vpn_key.id, 
                       telegram_id=telegram_id)
            return True
            
        except Exception as e:
            session.rollback()
            logger.error("Error saving VPN key to PostgreSQL", 
                        telegram_id=key_data.get('telegram_id'), 
                        error=str(e))
            return False
        finally:
            session.close()
    
    def update_vpn_key(self, key_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Обновление данных VPN ключа
        
        Совместимо с интерфейсом SimpleStorage.update_vpn_key()
        """
        session = self.db_manager.Session()
        try:
            # Получаем ключ из базы
            vpn_key = session.query(VPNKey).filter_by(id=key_id).first()
            if not vpn_key:
                logger.warning("VPN key not found for update", key_id=key_id)
                return False
            
            # Обновляем поля
            fields_to_update = [
                'uuid', 'vless_url', 'xui_email', 'xui_inbound_id', 
                'xui_client_id', 'xui_created', 'subscription_type'
            ]
            
            for field in fields_to_update:
                if field in update_data:
                    setattr(vpn_key, field, update_data[field])
            
            # Если есть updated_at в данных, преобразуем его
            if 'updated_at' in update_data and update_data['updated_at']:
                try:
                    vpn_key.updated_at = datetime.fromisoformat(update_data['updated_at'])
                except (ValueError, TypeError):
                    vpn_key.updated_at = datetime.utcnow()
            else:
                vpn_key.updated_at = datetime.utcnow()
            
            session.commit()
            
            logger.info("Successfully updated VPN key in PostgreSQL", key_id=key_id)
            return True
            
        except Exception as e:
            session.rollback()
            logger.error("Error updating VPN key in PostgreSQL", 
                        key_id=key_id, 
                        error=str(e))
            return False
        finally:
            session.close()
    
    def delete_vpn_key(self, key_id: int) -> bool:
        """Удаление VPN ключа (дополнительная функциональность)"""
        session = self.db_manager.Session()
        try:
            vpn_key = session.query(VPNKey).filter_by(id=key_id).first()
            if not vpn_key:
                return False
            
            session.delete(vpn_key)
            session.commit()
            
            logger.info("Successfully deleted VPN key from PostgreSQL", key_id=key_id)
            return True
            
        except Exception as e:
            session.rollback()
            logger.error("Error deleting VPN key from PostgreSQL", 
                        key_id=key_id, 
                        error=str(e))
            return False
        finally:
            session.close()
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получение всех пользователей (дополнительная функциональность)"""
        session = self.db_manager.Session()
        try:
            users = session.query(User).all()
            result = []
            
            for user in users:
                # Получаем количество ключей для каждого пользователя прямым запросом
                keys_count = session.query(VPNKey).filter_by(user_id=user.id).count()
                
                user_data = {
                    'id': user.id,
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'keys_count': keys_count
                }
                result.append(user_data)
            
            return result
            
        except Exception as e:
            logger.error("Error getting all users from PostgreSQL", error=str(e))
            return []
        finally:
            session.close()

# Создаем глобальный экземпляр для использования
pg_storage = PostgresStorage() 