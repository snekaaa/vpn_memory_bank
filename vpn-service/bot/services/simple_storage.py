"""
Упрощенное хранилище данных для VPN ключей
"""
import json
import os
import structlog
from typing import Dict, Any, List, Optional

logger = structlog.get_logger(__name__)

class SimpleStorage:
    """Простое хранилище данных для VPN ключей"""
    
    def __init__(self, data_file: str = "vpn_keys.json"):
        self.data_file = data_file
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Загрузка данных из файла"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"vpn_keys": {}}
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return {"vpn_keys": {}}
    
    def _save_data(self) -> bool:
        """Сохранение данных в файл"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            return False
    
    def get_user_vpn_keys(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Получение всех VPN ключей пользователя"""
        vpn_keys = self.data.get("vpn_keys", {})
        user_keys = []
        
        for key_id, key_data in vpn_keys.items():
            if key_data.get("telegram_id") == telegram_id:
                user_keys.append(key_data)
        
        return user_keys
    
    def save_vpn_key(self, key_data: Dict[str, Any]) -> bool:
        """Сохранение VPN ключа"""
        try:
            key_id = key_data.get("id") or len(self.data.get("vpn_keys", {})) + 1
            key_data["id"] = key_id
            
            self.data.setdefault("vpn_keys", {})
            self.data["vpn_keys"][str(key_id)] = key_data
            
            return self._save_data()
        except Exception as e:
            logger.error(f"Error saving VPN key: {e}")
            return False
    
    def update_vpn_key(self, key_id: int, update_data: Dict[str, Any]) -> bool:
        """Обновление данных VPN ключа"""
        try:
            str_key_id = str(key_id)
            if str_key_id in self.data.get("vpn_keys", {}):
                self.data["vpn_keys"][str_key_id].update(update_data)
                return self._save_data()
            return False
        except Exception as e:
            logger.error(f"Error updating VPN key: {e}")
            return False

# Создаем глобальный экземпляр для использования
simple_storage = SimpleStorage() 