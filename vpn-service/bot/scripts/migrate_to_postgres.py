#!/usr/bin/env python

"""
Скрипт для миграции данных из JSON в PostgreSQL
"""

import json
import os
import sys
import structlog
from datetime import datetime

# Добавляем родительскую директорию в путь импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.pg_storage import pg_storage

logger = structlog.get_logger(__name__)

def migrate_data(json_file="vpn_keys.json"):
    """
    Мигрирует данные из JSON файла в PostgreSQL
    """
    logger.info("Starting migration from JSON to PostgreSQL", source_file=json_file)
    
    try:
        # Проверяем существование файла
        if not os.path.exists(json_file):
            logger.error("Data file not found", file_path=json_file)
            return False
            
        # Загружаем данные из JSON
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Получаем словарь VPN ключей
        vpn_keys = data.get("vpn_keys", {})
        total_keys = len(vpn_keys)
        
        if total_keys == 0:
            logger.warning("No VPN keys found in JSON file")
            return False
            
        logger.info("Found keys in JSON file", count=total_keys)
        
        # Бэкап файла перед миграцией
        backup_file = f"{json_file}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Backup file created", backup_file=backup_file)
        
        # Мигрируем данные
        migrated_count = 0
        failed_count = 0
        
        for key_id, key_data in vpn_keys.items():
            # Проверка существования обязательных полей
            if not all(field in key_data for field in ['telegram_id', 'uuid', 'vless_url', 'xui_email']):
                logger.warning("Skipping key with missing required fields", key_id=key_id)
                failed_count += 1
                continue
                
            try:
                # Сохраняем ключ в PostgreSQL
                success = pg_storage.save_vpn_key(key_data)
                if success:
                    migrated_count += 1
                    logger.debug("Successfully migrated key", key_id=key_id)
                else:
                    failed_count += 1
                    logger.warning("Failed to migrate key", key_id=key_id)
            except Exception as e:
                failed_count += 1
                logger.error("Error migrating key", key_id=key_id, error=str(e))
        
        # Выводим итоги миграции
        success_rate = (migrated_count / total_keys) * 100 if total_keys > 0 else 0
        logger.info("Migration completed", 
                   total=total_keys,
                   migrated=migrated_count, 
                   failed=failed_count,
                   success_rate=f"{success_rate:.1f}%")
        
        return migrated_count > 0
        
    except Exception as e:
        logger.error("Migration failed", error=str(e))
        return False

def verify_migration(json_file="vpn_keys.json"):
    """
    Проверяет корректность миграции путем сравнения данных в JSON и PostgreSQL
    """
    logger.info("Verifying migration", source_file=json_file)
    
    try:
        # Загружаем данные из JSON
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        vpn_keys = data.get("vpn_keys", {})
        
        # Получаем список всех telegram_id из JSON
        json_telegram_ids = set()
        for key_id, key_data in vpn_keys.items():
            telegram_id = key_data.get('telegram_id')
            if telegram_id:
                json_telegram_ids.add(telegram_id)
        
        # Проверяем каждого пользователя
        verified_count = 0
        for telegram_id in json_telegram_ids:
            # Получаем ключи из JSON
            json_keys = []
            for key_id, key_data in vpn_keys.items():
                if key_data.get('telegram_id') == telegram_id:
                    json_keys.append(key_data)
            
            # Получаем ключи из PostgreSQL
            pg_keys = pg_storage.get_user_vpn_keys(telegram_id)
            
            # Проверяем количество ключей
            if len(json_keys) == len(pg_keys):
                verified_count += 1
                logger.debug("User verified", telegram_id=telegram_id, 
                            keys_count=len(json_keys))
            else:
                logger.warning("Key count mismatch", telegram_id=telegram_id, 
                              json_keys=len(json_keys), 
                              pg_keys=len(pg_keys))
        
        # Выводим итоги проверки
        success_rate = (verified_count / len(json_telegram_ids)) * 100 if json_telegram_ids else 0
        logger.info("Verification completed", 
                   total_users=len(json_telegram_ids),
                   verified=verified_count,
                   success_rate=f"{success_rate:.1f}%")
        
        return verified_count == len(json_telegram_ids)
        
    except Exception as e:
        logger.error("Verification failed", error=str(e))
        return False

if __name__ == "__main__":
    # Настройка логирования
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Путь к файлу по умолчанию
    default_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vpn_keys.json")
    
    # Получаем путь к файлу из аргументов или используем путь по умолчанию
    json_file = sys.argv[1] if len(sys.argv) > 1 else default_file
    
    # Запускаем миграцию
    if migrate_data(json_file):
        # Проверяем миграцию
        if verify_migration(json_file):
            logger.info("Migration and verification successful!")
            sys.exit(0)
        else:
            logger.warning("Migration completed but verification failed!")
            sys.exit(1)
    else:
        logger.error("Migration failed!")
        sys.exit(1) 