# 🎨🎨🎨 ENTERING CREATIVE PHASE: ARCHITECTURE REFACTORING

## Component Description
Необходимо провести рефакторинг архитектуры VPN бота, чтобы оставить только необходимые компоненты для работы 4 основных функций:
1. 🔑 Создать/напомнить ключ
2. 🔄 Обновить ключ
3. 📱 Скачать приложение
4. 🧑🏼‍💻 Служба поддержки

Текущая архитектура содержит избыточные компоненты, связанные с платными подписками, админской панелью и другими неиспользуемыми функциями.

## Requirements & Constraints

### Функциональные требования:
- Сохранить работу 4 основных кнопок меню
- Обеспечить автоматическое создание VPN ключей
- Обеспечить обновление VPN ключей
- Сохранить интеграцию с 3x-ui панелью

### Технические ограничения:
- Необходимо избавиться от зависимости `vpn_manager.py` от `local_storage.py`
- Нельзя нарушать работу production бота
- Минимизировать изменения в работающих компонентах

## Component Analysis

### Текущие компоненты:
1. **Handlers**:
   - `start.py` - стартовый handler (оставить)
   - `vpn_simplified.py` - основная логика VPN (оставить)
   - `commands.py` - команды для нативного меню (оставить)
   - `admin_panel.py` - админ панель (удалить)
   - `simple_auth.py` - базовая авторизация (оставить)

2. **Services**:
   - `vpn_manager.py` - управление VPN ключами (рефакторинг)
   - `vless_generator.py` - генерация VLESS ключей (оставить)
   - `xui_client.py` - интеграция с 3x-ui панелью (оставить)
   - `local_storage.py` - хранение данных о подписках (удалить/заменить)
   - `api_client.py` - API клиент для бэкенда (удалить)

3. **Middleware**:
   - `auth.py` - базовая авторизация (оставить)
   - `admin_auth.py` - авторизация админов (удалить)

## Architecture Options

### Option 1: Полное удаление с минимальным рефакторингом

**Описание**: Удалить все лишние компоненты и минимально модифицировать `vpn_manager.py`, заменив зависимость от `local_storage.py` на простое хранение в файле JSON.

**Pros**:
- Простота реализации
- Минимальные изменения в работающем коде
- Быстрое внедрение

**Cons**:
- Не самое элегантное решение
- Может потребоваться миграция данных
- Потенциальные проблемы с конкурентным доступом к JSON файлу

### Option 2: Полный рефакторинг VPN Manager

**Описание**: Создать полностью новую версию `vpn_manager.py` без зависимостей от других сервисов, с собственной логикой хранения данных.

**Pros**:
- Чистая архитектура
- Отсутствие лишних зависимостей
- Лучшая масштабируемость

**Cons**:
- Больше времени на разработку
- Риск внесения ошибок
- Необходимость миграции данных

### Option 3: Гибридное решение с упрощенным хранилищем

**Описание**: Создать упрощенную версию хранилища данных (`simple_storage.py`), которая будет использоваться только для хранения VPN ключей.

**Pros**:
- Сохранение логики работы с данными
- Меньше изменений в `vpn_manager.py`
- Более чистая архитектура чем в Option 1

**Cons**:
- Дополнительный компонент в системе
- Частичное дублирование функционала
- Необходимость миграции данных

## Recommended Approach

**Выбранный вариант**: Option 3 - Гибридное решение с упрощенным хранилищем

**Обоснование**:
Этот подход обеспечивает баланс между минимизацией изменений и чистотой архитектуры. Создание упрощенного хранилища данных позволит сохранить логику работы с данными, но избавиться от лишней функциональности, связанной с подписками и платежами.

## Implementation Guidelines

### 1. Создание SimpleStorage

```python
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
```

### 2. Рефакторинг VPNManager

```python
"""
Централизованный менеджер VPN ключей для упрощенного бота
"""

import structlog
from typing import Optional, Dict, Any
from services.xui_client import XUIClient
from services.simple_storage import SimpleStorage
import datetime

logger = structlog.get_logger(__name__)

class VPNManager:
    """Менеджер для управления VPN ключами пользователей"""
    
    def __init__(self):
        self.storage = SimpleStorage()
    
    async def get_or_create_user_key(self, telegram_id: int, username: str = "") -> Optional[Dict[str, Any]]:
        """
        Получить существующий ключ пользователя или создать новый
        Основная функция для кнопки "Создать/напомнить ключ"
        """
        try:
            # Сначала ищем существующий ключ
            existing_key = await self._find_existing_key(telegram_id)
            
            if existing_key:
                logger.info("Found existing VPN key for user", 
                           telegram_id=telegram_id,
                           key_id=existing_key.get('id'))
                return existing_key
            
            # Если ключа нет - создаем новый
            logger.info("Creating new VPN key for user", telegram_id=telegram_id)
            return await self._create_new_key(telegram_id, username)
            
        except Exception as e:
            logger.error("Error in get_or_create_user_key", 
                        telegram_id=telegram_id, 
                        error=str(e))
            return None
    
    async def refresh_user_key(self, telegram_id: int, username: str = "") -> Optional[Dict[str, Any]]:
        """
        Полностью удаляет старый ключ пользователя и создает новый.
        Функция для кнопки "Обновить ключ".
        """
        try:
            # Сначала ищем и удаляем существующий ключ
            existing_key = await self._find_existing_key(telegram_id)
            
            if existing_key:
                logger.info("Existing key found, preparing to delete and recreate",
                           telegram_id=telegram_id,
                           key_id=existing_key.get('id'))
                
                # Удаляем из 3x-ui
                delete_success = await self._delete_key_from_xui(existing_key)
                
                if delete_success:
                    logger.info("Successfully deleted key from 3x-ui",
                               telegram_id=telegram_id,
                               email=existing_key.get('xui_email'))
                else:
                    logger.warning("Could not delete key from 3x-ui, proceeding to create new one",
                                 telegram_id=telegram_id,
                                 email=existing_key.get('xui_email'))

                # Деактивируем в хранилище
                existing_key['is_active'] = False
                existing_key['updated_at'] = datetime.datetime.now().isoformat()
                self.storage.update_vpn_key(existing_key['id'], existing_key)

            else:
                logger.info("No existing key found, creating a new one", telegram_id=telegram_id)

            # В любом случае создаем новый ключ
            logger.info("Creating a new key for user as part of refresh", telegram_id=telegram_id)
            return await self._create_new_key(telegram_id, username)

        except Exception as e:
            logger.error("Error in refresh_user_key",
                        telegram_id=telegram_id,
                        error=str(e))
            return None
    
    async def _find_existing_key(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Ищет активный ключ в хранилище, проверяет его в 3x-ui и синхронизирует.
        """
        try:
            local_keys = self.storage.get_user_vpn_keys(telegram_id)
            active_local_key = next((k for k in local_keys if k.get('is_active')), None)

            if not active_local_key:
                return None

            async with XUIClient() as xui_client:
                if not await xui_client.login():
                    logger.warning("XUI unavailable, returning locally cached key", telegram_id=telegram_id)
                    return active_local_key

                result = await xui_client.get_client_by_email(active_local_key['xui_email'])

                if not result:
                    logger.warning("Key exists locally but not in 3x-ui, marking inactive",
                                   telegram_id=telegram_id, key_id=active_local_key.get('id'))
                    active_local_key['is_active'] = False
                    self.storage.update_vpn_key(active_local_key['id'], active_local_key)
                    return None

                xui_client_data, xui_inbound_data = result
                panel_uuid = xui_client_data.get("id")
                local_uuid = active_local_key.get("uuid")

                if panel_uuid != local_uuid:
                    logger.warning("UUID mismatch! Syncing local key with panel data.",
                                   telegram_id=telegram_id, local_uuid=local_uuid, panel_uuid=panel_uuid)
                    
                    new_vless_url = xui_client.generate_vless_url_from_inbound(
                        panel_uuid,
                        xui_inbound_data,
                        active_local_key['xui_email']
                    )
                    active_local_key['uuid'] = panel_uuid
                    active_local_key['vless_url'] = new_vless_url
                    active_local_key['updated_at'] = datetime.datetime.now().isoformat()
                    self.storage.update_vpn_key(active_local_key['id'], active_local_key)

                return active_local_key

        except Exception as e:
            logger.error("Error finding or syncing existing key", telegram_id=telegram_id, error=str(e))
            return None
    
    async def _delete_key_from_xui(self, key_data: Dict[str, Any]) -> bool:
        """Удаление ключа (клиента) из inbound в 3x-ui"""
        try:
            email_to_delete = key_data.get('xui_email')
            inbound_id = key_data.get('xui_inbound_id')

            if not email_to_delete or not inbound_id:
                logger.warning("Cannot delete key without email or inbound_id", key_data=key_data)
                return False

            async with XUIClient() as xui_client:
                if not await xui_client.login():
                    return False

                # Получаем текущий inbound
                inbound_response = await xui_client._make_authenticated_request(
                    "GET", f"/panel/api/inbounds/get/{inbound_id}"
                )

                if not (inbound_response and inbound_response.get("success")):
                    logger.error("Failed to get inbound for deletion", inbound_id=inbound_id)
                    return False

                inbound_data = inbound_response.get("obj")
                import json
                settings = json.loads(inbound_data.get("settings", "{}"))
                clients = settings.get("clients", [])

                # Находим и удаляем клиента
                client_found = False
                updated_clients = [client for client in clients if client.get("email") != email_to_delete]
                
                if len(updated_clients) < len(clients):
                    client_found = True
                
                if not client_found:
                    logger.warning("Client to delete not found in inbound", email=email_to_delete)
                    return True # Считаем удаленным, если его и так нет

                # Обновляем inbound с новым списком клиентов
                settings["clients"] = updated_clients
                
                update_data = {
                    "id": inbound_data["id"],
                    "up": inbound_data.get("up", 0),
                    "down": inbound_data.get("down", 0),
                    "total": inbound_data.get("total", 0),
                    "remark": inbound_data.get("remark", ""),
                    "enable": inbound_data.get("enable", True),
                    "expiryTime": inbound_data.get("expiryTime", 0),
                    "listen": inbound_data.get("listen", ""),
                    "port": inbound_data.get("port", 443),
                    "protocol": inbound_data.get("protocol", "vless"),
                    "settings": json.dumps(settings),
                    "streamSettings": inbound_data.get("streamSettings", ""),
                    "tag": inbound_data.get("tag", ""),
                    "sniffing": inbound_data.get("sniffing", "")
                }

                update_result = await xui_client._make_authenticated_request(
                    "POST", f"/panel/api/inbounds/update/{inbound_id}", update_data
                )

                return update_result and update_result.get("success", False)

        except Exception as e:
            logger.error("Error deleting key from 3x-ui", error=str(e))
            return False
    
    async def _create_new_key(self, telegram_id: int, username: str) -> Optional[Dict[str, Any]]:
        """Создание нового VPN ключа"""
        try:
            # Создаем пользователя в 3x-ui
            async with XUIClient() as xui_client:
                login_success = await xui_client.login()
                
                if login_success:
                    # Создаем в 3x-ui с автоматическим типом
                    xui_result = await xui_client.create_vless_user(
                        telegram_id, 
                        "auto",  # Специальный тип для упрощенного бота
                        username
                    )
                    
                    if xui_result:
                        # Сохраняем в хранилище
                        # Сначала деактивируем все старые ключи этого пользователя
                        all_user_keys = self.storage.get_user_vpn_keys(telegram_id)
                        for key in all_user_keys:
                            key['is_active'] = False
                            self.storage.update_vpn_key(key['id'], key)

                        vpn_key_data = {
                            'id': len(self.storage.get_user_vpn_keys(telegram_id)) + 1,
                            'telegram_id': telegram_id,
                            'uuid': xui_result['uuid'],
                            'vless_url': xui_result.get('vless_url_from_api', ''),
                            'xui_email': xui_result['email'],
                            'xui_inbound_id': xui_result['inbound_id'],
                            'is_active': True,
                            'xui_created': True,
                            'subscription_type': 'auto',
                            'created_at': datetime.datetime.now().isoformat()
                        }
                        
                        # Сохраняем в хранилище
                        self.storage.save_vpn_key(vpn_key_data)
                        
                        logger.info("New VPN key created successfully", 
                                   telegram_id=telegram_id,
                                   uuid=xui_result['uuid'],
                                   email=xui_result['email'])
                        
                        return vpn_key_data
                    
                    else:
                        logger.error("Failed to create user in 3x-ui", telegram_id=telegram_id)
                        return self._create_mock_key(telegram_id, username)
                else:
                    logger.error("Failed to login to 3x-ui", telegram_id=telegram_id)
                    return self._create_mock_key(telegram_id, username)
                
        except Exception as e:
            logger.error("Error creating new VPN key", telegram_id=telegram_id, error=str(e))
            return self._create_mock_key(telegram_id, username)
    
    def _create_mock_key(self, telegram_id: int, username: str) -> Dict[str, Any]:
        """Создание фейкового ключа при недоступности 3x-ui"""
        try:
            from services.vless_generator import vless_generator
            
            # Генерируем фейковый ключ через vless_generator
            mock_key = vless_generator.create_vpn_key(telegram_id, "auto")
            mock_key['is_active'] = True
            mock_key['xui_created'] = False
            mock_key['xui_email'] = f"{telegram_id}(@{username})_mock"
            mock_key['created_at'] = datetime.datetime.now().isoformat()
            
            # Сохраняем в хранилище
            self.storage.save_vpn_key(mock_key)
            
            logger.info("Created mock VPN key due to 3x-ui unavailability", 
                       telegram_id=telegram_id,
                       uuid=mock_key['uuid'])
            
            return mock_key
            
        except Exception as e:
            logger.error("Error creating mock key", telegram_id=telegram_id, error=str(e))
            # Возвращаем минимальный ключ с ошибкой
            return {
                'id': 0,
                'telegram_id': telegram_id,
                'uuid': 'error',
                'vless_url': 'Ошибка создания ключа. Обратитесь в поддержку.',
                'is_active': False,
                'error': str(e)
            }
```

### 3. Обновление импортов в main.py

```python
"""
Главный файл бота - точка входа в приложение
"""

import asyncio
import structlog
from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config.settings import get_settings
from handlers import (
    start_router,
    vpn_simplified_router
)
from handlers.commands import commands_router

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

logger = structlog.get_logger(__name__)

async def main():
    """Запуск бота"""
    try:
        settings = get_settings()
        logger.info("Starting VPN Telegram Bot", token=settings.telegram_bot_token[:10] + "...")
        
        # Инициализация бота и диспетчера
        bot = Bot(token=settings.telegram_bot_token)
        dp = Dispatcher(storage=MemoryStorage())
        
        # Настройка команд для нативного меню
        commands = [
            BotCommand(command="create_key", description="🔑 Создать/напомнить ключ"),
            BotCommand(command="refresh_key", description="🔄 Обновить ключ"),
            BotCommand(command="download_apps", description="📱 Скачать приложение"),
            BotCommand(command="support", description="🧑🏼‍💻 Служба поддержки")
        ]
        await bot.set_my_commands(commands)
        logger.info("Bot commands set successfully")
        
        # Подключение роутеров
        dp.include_router(start_router)
        dp.include_router(vpn_simplified_router)
        dp.include_router(commands_router)
        
        logger.info("All routers registered successfully")
        
        # Пропуск накопившихся обновлений и запуск
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot is starting polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error("Failed to start bot", error=str(e))
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

### 4. План миграции данных

1. Создать скрипт миграции, который:
   - Загрузит данные из `local_storage.py`
   - Извлечет только VPN ключи
   - Сохранит их в новом формате для `simple_storage.py`

2. Запустить скрипт миграции перед обновлением кода

3. Сделать резервную копию данных перед миграцией

## Verification Checkpoint

- ✅ Сохранены все 4 основные функции
- ✅ Удалены все лишние компоненты
- ✅ Решена проблема зависимости от `local_storage.py`
- ✅ Минимизированы изменения в работающем коде
- ✅ Обеспечена миграция данных
- ✅ Сохранена интеграция с 3x-ui панелью

# 🎨🎨🎨 EXITING CREATIVE PHASE 