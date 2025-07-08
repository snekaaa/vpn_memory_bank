import aiohttp
import asyncio
import hashlib
import uuid
import json
from typing import Optional, Dict, Any, List
import structlog
from datetime import datetime, timedelta
import urllib.parse

from config.settings import get_settings

logger = structlog.get_logger(__name__)

class X3UIClient:
    """Клиент для работы с 3X-UI панелью"""
    
    def __init__(self, base_url: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        self.settings = get_settings()
        # base_url теперь обязательный - берется из ноды в базе данных
        self.base_url = base_url
        # username/password тоже берутся из ноды, но оставляем fallback для совместимости
        self.username = username or "admin"
        self.password = password or "admin"
        self.session_token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        
    async def _ensure_session(self) -> bool:
        """Обеспечение активной сессии"""
        if (self.session_token and self.token_expires and 
            datetime.utcnow() < self.token_expires):
            return True
            
        return await self._login()
    
    async def _login(self) -> bool:
        """Аутентификация в 3X-UI"""
        try:
            if not self.base_url:
                logger.error("No base_url provided for X3UI client")
                return False
                
            # Очищаем URL от завершающего слеша
            base_url = self.base_url.rstrip('/')
            
            # Проверяем, что URL начинается с http:// или https://
            if not (base_url.startswith('http://') or base_url.startswith('https://')):
                logger.error("Invalid URL format, must start with http:// or https://", url=base_url)
                return False
                
            logger.info("Attempting to login to X3UI", url=base_url)
            
            # Определяем правильный путь для login
            # Для большинства X3UI панелей используется /login
            # Попробуем сначала /login, потом /panel/login если не сработает
            login_url = f"{base_url}/login"
            logger.info("Full login URL", login_url=login_url)
            
            # Отключаем проверку SSL для самоподписанных сертификатов
            connector = aiohttp.TCPConnector(ssl=False) if base_url.startswith('https://') else None
            async with aiohttp.ClientSession(connector=connector) as session:
                login_data = {
                    "username": self.username,
                    "password": self.password
                }
                
                logger.info("Preparing login request with credentials")
                
                async with session.post(
                    login_url,
                    json=login_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    logger.info("Login response status", status=response.status)
                    
                    # Логирование заголовков и кук для отладки
                    logger.info("Response headers", headers=dict(response.headers))
                    logger.info("Response cookies", cookies={k:v for k,v in response.cookies.items()})
                    
                    # Читаем тело ответа
                    response_body = await response.text()
                    logger.info("Response body", body_length=len(response_body))
                    
                    try:
                        # Пытаемся распарсить JSON
                        data = json.loads(response_body)
                        logger.info("Response parsed as JSON", success=data.get("success", False))
                        
                        if data.get("success"):
                            # Получаем cookie из заголовков
                            session_cookie = None
                            for cookie_name, cookie_value in response.cookies.items():
                                if cookie_name == '3x-ui':
                                    session_cookie = cookie_value
                                    break
                            
                            if session_cookie:
                                self.session_token = session_cookie
                                # Токен действует 1 час согласно cookie
                                self.token_expires = datetime.utcnow() + timedelta(minutes=50)
                                logger.info("Successfully authenticated with 3X-UI")
                                return True
                            else:
                                # Все равно пытаемся продолжить даже без cookie
                                logger.warning("No session cookie received from 3X-UI, trying to continue anyway")
                                self.session_token = "dummy_token"
                                self.token_expires = datetime.utcnow() + timedelta(minutes=50)
                                return True
                        else:
                            logger.error("3X-UI login failed", error=data.get("msg"))
                            return False
                    except json.JSONDecodeError:
                        logger.warning("Response not JSON", body=response_body[:100])
                        
                        # Возможно устаревшая панель без API, пробуем через cookie
                        if response.status == 200 and len(response.cookies) > 0:
                            self.session_token = next(iter(response.cookies.values()))
                            self.token_expires = datetime.utcnow() + timedelta(minutes=50)
                            logger.info("Using fallback cookie authentication")
                            return True
                        
                        logger.error("3X-UI login failed, response not JSON")
                        return False
                        
        except Exception as e:
            logger.error("Error connecting to 3X-UI", error=str(e))
            return False
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Выполнение запроса к 3X-UI API с диагностикой"""
        if not await self._ensure_session():
            return None
            
        try:
            if not self.base_url:
                logger.error("No base_url provided for X3UI client")
                return None
                
            # Очищаем URL от завершающего слеша
            base_url = self.base_url.rstrip('/')
            
            # Проверяем, что URL начинается с http:// или https://
            if not (base_url.startswith('http://') or base_url.startswith('https://')):
                logger.error("Invalid URL format, must start with http:// or https://", url=base_url)
                return None
                
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            cookies = {
                "x-ui": self.session_token  # Исправлено: используем правильное имя cookie
            }
            
            full_url = f"{base_url}{endpoint}"
            
            # Специальная диагностика для delete client
            is_delete_request = "delClient" in endpoint
            if is_delete_request:
                logger.info("🔍 ДИАГНОСТИКА: Выполнение DELETE запроса", 
                           url=full_url, 
                           method=method,
                           data=data,
                           headers=headers,
                           cookies_present=bool(cookies.get("x-ui")))
            else:
                logger.info("Making X3UI request", url=full_url, method=method)
            
            # Отключаем проверку SSL для самоподписанных сертификатов
            connector = aiohttp.TCPConnector(ssl=False) if base_url.startswith('https://') else None
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.request(
                    method,
                    full_url,
                    json=data if data else None,
                    headers=headers,
                    cookies=cookies,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if is_delete_request:
                        logger.info("🔍 ДИАГНОСТИКА: Получен ответ на DELETE запрос", 
                                   status=response.status, 
                                   content_type=response.content_type,
                                   headers=dict(response.headers))
                    else:
                        logger.info("X3UI response", status=response.status, content_type=response.content_type)
                    
                    if response.status == 200:
                        response_text = await response.text()
                        
                        if is_delete_request:
                            logger.info("🔍 ДИАГНОСТИКА: Текст ответа на DELETE запрос", 
                                       full_text=response_text,
                                       text_length=len(response_text))
                        else:
                            logger.info("Response text preview", preview=response_text[:200])
                        
                        try:
                            # Пытаемся парсить как JSON
                            parsed_json = json.loads(response_text)
                            
                            if is_delete_request:
                                logger.info("🔍 ДИАГНОСТИКА: JSON ответ на DELETE запрос", 
                                           parsed_json=parsed_json,
                                           json_keys=list(parsed_json.keys()) if isinstance(parsed_json, dict) else "Not a dict")
                            
                            return parsed_json
                        except json.JSONDecodeError as e:
                            if is_delete_request:
                                logger.info("🔍 ДИАГНОСТИКА: Ошибка парсинга JSON в DELETE ответе - проверяем пустой ответ", 
                                           error=str(e),
                                           response_text=response_text,
                                           response_length=len(response_text))
                                
                                # Для DELETE запросов панель может возвращать пустой ответ при успехе
                                if len(response_text.strip()) == 0:
                                    logger.info("🔍 ДИАГНОСТИКА: Пустой ответ на DELETE - считаем успешным")
                                    return {"success": True, "msg": "Empty response interpreted as success"}
                            
                            # Если не JSON, проверяем что это может быть успешный ответ
                            if response_text.strip():
                                logger.warning("Non-JSON response received", 
                                             content_type=response.content_type,
                                             text_preview=response_text[:100])
                                
                                # Для некоторых endpoints может возвращаться простой текст
                                # В таком случае считаем что запрос неудачный
                                return None
                            else:
                                if is_delete_request:
                                    # Для DELETE запросов пустой ответ со статусом 200 = успех
                                    logger.info("🔍 ДИАГНОСТИКА: Пустой ответ на DELETE со статусом 200 - успех")
                                    return {"success": True, "msg": "Empty response with 200 status"}
                                else:
                                    logger.error("Empty response received")
                                    return None
                    else:
                        response_text = await response.text()
                        
                        if is_delete_request:
                            logger.error("🔍 ДИАГНОСТИКА: DELETE запрос завершился с ошибкой", 
                                       endpoint=endpoint, 
                                       status=response.status,
                                       response_text=response_text,
                                       response_headers=dict(response.headers))
                        else:
                            logger.error("3X-UI request failed", 
                                       endpoint=endpoint, 
                                       status=response.status,
                                       response_text=response_text[:200])
                        return None
                        
        except Exception as e:
            if "delClient" in endpoint:
                logger.error("🔍 ДИАГНОСТИКА: Исключение при выполнении DELETE запроса", 
                            endpoint=endpoint, 
                            error=str(e),
                            error_type=type(e).__name__)
            else:
                logger.error("Error making 3X-UI request", 
                            endpoint=endpoint, 
                            error=str(e))
            return None
    
    async def get_inbounds(self) -> Optional[List[Dict]]:
        """Получение списка inbound правил"""
        # Пробуем разные API пути в порядке приоритета  
        api_paths = [
            "/panel/api/inbounds/list",  # Стандартный новый путь
            "/panel/inbounds/list",      # Альтернативный путь
            "/xui/inbounds/list",        # Старый путь
            "/api/inbounds/list"         # Еще один вариант
        ]
        
        for api_path in api_paths:
            logger.info("Trying inbounds API path", path=api_path)
            
            result = await self._make_request("GET", api_path)
            
            if result and result.get("success"):
                logger.info("Successfully got inbounds", path=api_path, count=len(result.get("obj", [])))
                return result.get("obj", [])
            elif result is None:
                # Пробуем следующий путь
                continue
            else:
                logger.warning("API path returned unsuccessful result", path=api_path, result=result)
        
        logger.error("All inbounds API paths failed")
        return None
    
    async def create_client(self, inbound_id: int, client_config: Dict[str, Any]) -> Optional[Dict]:
        """Создание нового клиента VPN"""
        try:
            # Используем client_id из конфигурации или генерируем новый
            client_id = client_config.get("id") or client_config.get("client_id") or str(uuid.uuid4())
            
            # Использую email из client_config или формирую [telegram_id]_[timestamp]
            if client_config.get("email"):
                unique_email = client_config.get("email")
            else:
                telegram_id = client_config.get("telegram_id", "")
                timestamp = int(datetime.utcnow().timestamp())
                unique_email = f"{telegram_id}_{timestamp}"
            
            # Проверяем существующих клиентов для избежания дублирования
            existing_inbounds = await self.get_inbounds()
            existing_emails = set()
            
            if existing_inbounds:
                for inbound in existing_inbounds:
                    settings = json.loads(inbound.get('settings', '{}'))
                    clients = settings.get('clients', [])
                    for client in clients:
                        existing_emails.add(client.get('email', ''))
            
            # Убеждаемся что email уникален
            counter = 1
            final_email = unique_email
            while final_email in existing_emails:
                final_email = f"{unique_email}_{counter}"
                counter += 1
            
            # Логируем использование переданного или нового UUID
            if client_config.get("id") or client_config.get("client_id"):
                logger.info("🎯 Using provided client_id for X3UI client creation", client_id=client_id)
            else:
                logger.info("🔄 Generated new client_id for X3UI client creation", client_id=client_id)
            
            # Формируем конфигурацию клиента
            client_data = {
                "id": inbound_id,
                "settings": json.dumps({
                    "clients": [{
                        "id": client_id,
                        "email": final_email,
                        "flow": client_config.get("flow", "xtls-rprx-vision"),
                        "limitIp": client_config.get("limit_ip", 2),
                        "totalGB": client_config.get("total_gb", 0),  # 0 = безлимитный
                        "expiryTime": client_config.get("expiry_time", 0),  # 0 = без истечения
                        "enable": True,
                        "tgId": str(client_config.get("telegram_id", "")),
                        "subId": client_config.get("sub_id", "")
                    }]
                })
            }
            
            result = await self._make_request("POST", f"/panel/api/inbounds/addClient", client_data)
            
            if result and result.get("success"):
                logger.info("VPN client created successfully", 
                           client_id=client_id, 
                           email=final_email,
                           inbound_id=inbound_id)
                
                # Возвращаем данные созданного клиента
                return {
                    "client_id": client_id,
                    "email": final_email,
                    "inbound_id": inbound_id,
                    "success": True
                }
            else:
                logger.error("Failed to create VPN client", 
                           error=result.get("msg") if result else "Unknown error")
                return None
                
        except Exception as e:
            logger.error("Error creating VPN client", error=str(e))
            return None
    
    async def delete_client(self, inbound_id: int, client_id: str) -> bool:
        """Удаление клиента VPN по точному ID"""
        try:
            import asyncio
            
            logger.info("Удаление клиента из X3UI панели", 
                      inbound_id=inbound_id, 
                      client_id=client_id)
            
            # Проверяем, существует ли клиент
            client_exists_before = await self._check_client_exists(inbound_id, client_id)
            
            if not client_exists_before:
                logger.info("Клиент не найден в панели, считаем что уже удален", 
                          client_id=client_id)
                return True
            
            # Используем рабочий endpoint: RESTful с ID в URL
            endpoint = f"/panel/api/inbounds/{inbound_id}/delClient/{client_id}"
            
            logger.info("Отправляем запрос на удаление клиента", 
                       endpoint=endpoint,
                       inbound_id=inbound_id,
                       client_id=client_id)
            
            # Отправляем запрос на удаление (пустое тело запроса)
            result = await self._make_request("POST", endpoint, {})
            
            if result and result.get("success"):
                logger.info("VPN клиент успешно удален", 
                          client_id=client_id, 
                          inbound_id=inbound_id,
                          msg=result.get("msg", ""))
                
                # Проверяем, действительно ли клиент удален
                await asyncio.sleep(1)  # Небольшая задержка для обновления данных
                
                client_exists_after = await self._check_client_exists(inbound_id, client_id)
                
                if not client_exists_after:
                    logger.info("Клиент успешно удален и отсутствует в панели", 
                              client_id=client_id)
                    return True
                else:
                    logger.warning("API сообщил об успехе, но клиент все еще существует", 
                                 client_id=client_id,
                                 inbound_id=inbound_id)
                    return False
            else:
                error_msg = result.get("msg") if result else "Нет ответа от панели"
                logger.warning("Не удалось удалить клиента", 
                             client_id=client_id,
                             error=error_msg)
                
                # Проверим, может клиент все-таки удален несмотря на ошибку
                if result and isinstance(error_msg, str) and ("not found" in error_msg.lower() or "не найден" in error_msg.lower()):
                    logger.info("Клиент не найден в панели, считаем что уже удален", 
                              client_id=client_id)
                    return True
                
                return False
                
        except Exception as e:
            logger.error("Критическая ошибка при удалении VPN клиента", 
                        client_id=client_id, 
                        inbound_id=inbound_id,
                        error=str(e))
            return False

    async def _check_client_exists(self, inbound_id: int, client_id: str) -> bool:
        """Проверка существования клиента в панели"""
        try:
            inbounds = await self.get_inbounds()
            if not inbounds:
                logger.warning("Не удалось получить список inbound'ов для проверки")
                return False
                
            for inbound in inbounds:
                if inbound.get("id") == inbound_id:
                    settings = json.loads(inbound.get("settings", "{}"))
                    clients = settings.get("clients", [])
                    
                    for client in clients:
                        if client.get("id") == client_id:
                            return True
                    
                    return False
            
            logger.warning("Inbound не найден", inbound_id=inbound_id)
            return False
            
        except Exception as e:
            logger.error("Ошибка при проверке существования клиента", 
                        client_id=client_id, 
                        inbound_id=inbound_id,
                        error=str(e))
            return False
    
    async def delete_client_by_email(self, email: str) -> bool:
        """Удаление клиента из X3UI панели по email"""
        try:
            logger.info("Поиск и удаление клиента по email", email=email)
            
            # Получаем все inbound'ы
            inbounds = await self.get_inbounds()
            if not inbounds:
                logger.error("Не удалось получить список inbound'ов", email=email)
                return False
            
            # Ищем клиента с указанным email
            client_found = False
            deleted_clients = 0
            
            for inbound in inbounds:
                settings = json.loads(inbound.get("settings", "{}"))
                clients = settings.get("clients", [])
                
                for client in clients:
                    if client.get("email") == email or (email in client.get("email", "")):
                        client_found = True
                        inbound_id = inbound.get("id")
                        client_id = client.get("id")
                        
                        logger.info("Найден клиент для удаления", 
                                  email=email,
                                  inbound_id=inbound_id,
                                  client_id=client_id)
                        
                        # Удаляем клиента
                        delete_result = await self.delete_client(inbound_id, client_id)
                        
                        if delete_result:
                            logger.info("Клиент успешно удален по email", 
                                      email=email,
                                      inbound_id=inbound_id,
                                      client_id=client_id)
                            deleted_clients += 1
                        else:
                            logger.error("Не удалось удалить клиента найденного по email", 
                                       email=email,
                                       inbound_id=inbound_id,
                                       client_id=client_id)
            
            if client_found:
                logger.info(f"Всего найдено и удалено {deleted_clients} клиентов с email {email}")
                return deleted_clients > 0
            
            logger.warning("Клиент с указанным email не найден", email=email)
            # Если клиента нет, то нет необходимости его удалять
            return True
                
        except Exception as e:
            logger.error("Ошибка при удалении клиента по email", 
                       email=email, 
                       error=str(e))
            return False
    
    async def get_client_stats(self, inbound_id: int, client_id: str) -> Optional[Dict]:
        """Получение статистики клиента"""
        try:
            # Получаем статистику по inbound
            result = await self._make_request("GET", f"/panel/api/inbounds/get/{inbound_id}")
            
            if result and result.get("success"):
                inbound_data = result.get("obj")
                if inbound_data:
                    # Парсим настройки клиентов
                    settings = json.loads(inbound_data.get("settings", "{}"))
                    clients = settings.get("clients", [])
                    
                    # Ищем нужного клиента
                    for client in clients:
                        if client.get("id") == client_id:
                            # Получаем статистику трафика
                            client_stats = inbound_data.get("clientStats") or []  # Обработка None
                            stats = {}
                            if client_stats:  # Дополнительная проверка
                                stats = next((s for s in client_stats if s.get("email") == client.get("email")), {})
                            
                            # Рассчитываем общий трафик
                            up_traffic = stats.get("up", 0)
                            down_traffic = stats.get("down", 0)
                            total_traffic = up_traffic + down_traffic
                            
                            return {
                                "client_id": client_id,
                                "email": client.get("email"),
                                "enabled": client.get("enable", False),
                                "total_gb": client.get("totalGB", 0),
                                "expiry_time": client.get("expiryTime", 0),
                                "up_traffic": up_traffic,
                                "down_traffic": down_traffic,
                                "total_traffic": total_traffic,
                                "enable": client.get("enable", False)
                            }
                
                logger.warning("Client not found in 3xui stats", client_id=client_id, inbound_id=inbound_id)
                return None
                
        except Exception as e:
            logger.error("Error getting client stats", 
                        client_id=client_id, 
                        inbound_id=inbound_id,
                        error=str(e))
            return None
    
    async def generate_client_url(self, inbound_id: int, client_id: str) -> Optional[str]:
        """Генерация VLESS URL для клиента"""
        try:
            # Увеличиваем задержку для лучшей синхронизации панели
            import asyncio
            await asyncio.sleep(1.0)
            
            logger.info("Generating client URL", 
                       inbound_id=inbound_id, 
                       client_id=client_id)
            
            # Получаем данные inbound через get_inbounds (более надежно)
            inbounds = await self.get_inbounds()
            if not inbounds:
                logger.error("Failed to get inbounds for URL generation")
                return None
            
            # Находим целевой inbound
            target_inbound = None
            for inbound in inbounds:
                if inbound.get("id") == inbound_id:
                    target_inbound = inbound
                    break
            
            if not target_inbound:
                logger.error("Inbound not found for URL generation", inbound_id=inbound_id)
                return None
            
            # Парсим настройки
            settings = json.loads(target_inbound.get("settings", "{}"))
            stream_settings = json.loads(target_inbound.get("streamSettings", "{}"))
            
            # Ищем клиента с улучшенной логикой поиска
            clients = settings.get("clients", [])
            client = None
            
            # Сначала поиск по точному ID
            for c in clients:
                if c.get("id") == client_id:
                    client = c
                    logger.info("Found client by exact ID", 
                               client_id=client_id,
                               client_email=c.get("email"))
                    break
            
            # Fallback: поиск по email pattern (если ID содержится в email)
            if not client:
                logger.warning("Client not found by exact ID, searching by email pattern", 
                              client_id=client_id,
                              total_clients=len(clients))
                
                for c in clients:
                    email = c.get("email", "")
                    # Проверяем если часть UUID содержится в email или наоборот
                    if (client_id in email or 
                        email.startswith(client_id.split('-')[0]) or
                        any(part in email for part in client_id.split('-')[:2])):
                        client = c
                        logger.info("Found client by email pattern", 
                                   client_id=client_id,
                                   matched_email=email,
                                   client_real_id=c.get("id"))
                        # Используем реальный ID клиента из панели
                        client_id = c.get("id")
                        break
            
            # Последний fallback: берем последнего созданного клиента
            if not client and clients:
                client = clients[-1]
                client_id = client.get("id")
                logger.info("Using last created client as fallback", 
                           client_id=client_id,
                           client_email=client.get("email"))
            
            if not client:
                logger.error("No clients found in inbound", 
                            inbound_id=inbound_id,
                            total_clients=len(clients))
                return None
            
            # Получаем хост из base_url (исправлено)
            import urllib.parse
            parsed_url = urllib.parse.urlparse(self.base_url)
            host = parsed_url.hostname
            
            if not host:
                logger.error("Failed to parse hostname from base_url", 
                            base_url=self.base_url)
                return None
            
            # Формируем VLESS URL
            port = target_inbound.get("port")
            
            # Параметры из stream settings
            reality_settings = stream_settings.get("realitySettings", {})
            
            # Получаем публичный ключ из правильного места в настройках Reality
            # Попробуем найти public key в нескольких возможных местах
            public_key = ''
            
            # Вариант 1: reality_settings.publicKey
            if reality_settings.get('publicKey'):
                public_key = reality_settings.get('publicKey')
                logger.info("Found public key in reality_settings.publicKey")
            
            # Вариант 2: reality_settings.settings.publicKey  
            elif reality_settings.get('settings', {}).get('publicKey'):
                public_key = reality_settings.get('settings', {}).get('publicKey')
                logger.info("Found public key in reality_settings.settings.publicKey")
            
            # Вариант 3: reality_settings.dest (иногда тут хранится)
            elif reality_settings.get('dest'):
                # dest может содержать public key в некоторых конфигурациях
                dest = reality_settings.get('dest', '')
                if len(dest) > 40:  # Примерная длина public key
                    public_key = dest
                    logger.info("Found public key in reality_settings.dest")
            
            # Логируем все настройки Reality для диагностики
            logger.info("Reality settings diagnostic", 
                       reality_settings_keys=list(reality_settings.keys()),
                       has_public_key=bool(public_key),
                       public_key_length=len(public_key) if public_key else 0,
                       reality_settings_sample=str(reality_settings)[:200] + "..." if reality_settings else "None")
            
            if not public_key:
                logger.warning("Public key not found in Reality settings - VLESS URL will not work!", 
                              available_keys=list(reality_settings.keys()))
            
            # Получаем short_id
            short_id = ""
            if reality_settings.get("shortIds") and len(reality_settings.get("shortIds")) > 0:
                short_id = reality_settings.get("shortIds")[0]
            
            # Получаем SNI
            sni = "apple.com"  # Значение по умолчанию
            if reality_settings.get("serverNames") and len(reality_settings.get("serverNames")) > 0:
                sni = reality_settings.get("serverNames")[0]
            
            vless_url = (
                f"vless://{client_id}@{host}:{port}?"
                f"type=tcp&security=reality"
                f"&fp=chrome"
                f"&pbk={public_key}"
                f"&sni={sni}"
                f"&flow={client.get('flow', 'xtls-rprx-vision')}"
                f"&sid={short_id}"
                f"&spx=%2F"
                f"#{client.get('email', 'VPN')}"
            )
            
            logger.info("Generated VLESS URL successfully", 
                       host=host, 
                       port=port, 
                       public_key=public_key[:20] + "..." if public_key else "None",
                       client_email=client.get('email'),
                       url_length=len(vless_url))
            
            return vless_url
            
        except Exception as e:
            logger.error("Error generating client URL", 
                        client_id=client_id, 
                        inbound_id=inbound_id,
                        error=str(e),
                        exc_info=True)
            return None
    
    async def reset_client_traffic(self, inbound_id: int, client_id: str) -> bool:
        """Сброс статистики трафика клиента"""
        try:
            data = {
                "inboundId": inbound_id,
                "uuid": client_id
            }
            
            result = await self._make_request("POST", "/panel/api/inbounds/resetClientTraffic", data)
            
            if result and result.get("success"):
                logger.info("Client traffic reset successfully", 
                           client_id=client_id)
                return True
            else:
                logger.error("Failed to reset client traffic", 
                           client_id=client_id,
                           error=result.get("msg") if result else "Unknown error")
                return False
                
        except Exception as e:
            logger.error("Error resetting client traffic", 
                        client_id=client_id, 
                        error=str(e))
            return False
    
    async def get_server_status(self) -> Optional[Dict]:
        """Получение статуса сервера"""
        try:
            result = await self._make_request("POST", "/panel/api/server/status")
            
            if result and result.get("success"):
                return result.get("obj", {})
            return None
            
        except Exception as e:
            logger.error("Error getting server status", error=str(e))
            return None
    
    async def generate_reality_keys(self) -> Optional[Dict[str, str]]:
        """Генерация новых Reality ключей через RealityKeyGenerator (эквивалент кнопки Get New Cert)"""
        try:
            from services.reality_key_generator import RealityKeyGenerator
            
            logger.info("Generating Reality keys via RealityKeyGenerator")
            
            # Генерируем ключи через новый надежный генератор
            keys = RealityKeyGenerator.generate_keys()
            
            # Валидируем ключи
            if not RealityKeyGenerator.validate_keys(keys.private_key, keys.public_key):
                logger.warning("Generated keys failed validation, regenerating")
                keys = RealityKeyGenerator.generate_keys()
                
                if not RealityKeyGenerator.validate_keys(keys.private_key, keys.public_key):
                    logger.error("Failed to generate valid keys after retry")
                    return None
            
            logger.info("Reality keys generated successfully via RealityKeyGenerator",
                       public_key=keys.public_key[:20] + "...",
                       method=keys.generation_method)
            
            return keys.to_dict()
            
        except Exception as e:
            logger.error("Failed to generate Reality keys via RealityKeyGenerator", error=str(e))
            return None
    
    async def update_inbound_reality_keys(self, inbound_id: int, private_key: str, public_key: str) -> bool:
        """Обновление Reality ключей существующего inbound'а (эквивалент кнопки Get New Cert + Apply)"""
        try:
            # Сначала получаем текущие настройки inbound'а
            inbounds = await self.get_inbounds()
            if not inbounds:
                logger.error("Failed to get inbounds list for key update")
                return False
            
            target_inbound = None
            for inbound in inbounds:
                if inbound.get("id") == inbound_id:
                    target_inbound = inbound
                    break
            
            if not target_inbound:
                logger.error("Inbound not found for key update", inbound_id=inbound_id)
                return False
            
            # Обновляем Reality ключи в streamSettings
            stream_settings = target_inbound.get("streamSettings", "{}")
            if isinstance(stream_settings, str):
                stream_settings = json.loads(stream_settings)
            
            reality_settings = stream_settings.get("realitySettings", {})
            reality_settings["privateKey"] = private_key
            
            # Public Key должен быть в settings.publicKey, а не в корне
            if "settings" not in reality_settings:
                reality_settings["settings"] = {}
            reality_settings["settings"]["publicKey"] = public_key
            
            stream_settings["realitySettings"] = reality_settings
            
            # Подготавливаем данные для обновления inbound'а
            update_data = {
                "id": target_inbound["id"],
                "remark": target_inbound["remark"],
                "enable": target_inbound["enable"],
                "port": target_inbound["port"],
                "protocol": target_inbound["protocol"],
                "settings": target_inbound["settings"],
                "streamSettings": json.dumps(stream_settings),
                "tag": target_inbound["tag"],
                "sniffing": target_inbound["sniffing"]
            }
            
            logger.info("Updating inbound with new Reality keys via API",
                       inbound_id=inbound_id,
                       public_key=public_key[:20] + "...")
            
            # Обновляем inbound через API
            result = await self._make_request(
                "POST",
                f"/panel/api/inbounds/update/{inbound_id}",
                update_data
            )
            
            if result and result.get("success"):
                logger.info("Reality keys updated successfully via X3UI API",
                           inbound_id=inbound_id)
                return True
            else:
                logger.error("Failed to update Reality keys via API",
                           result=result)
                return False
                
        except Exception as e:
            logger.error("Error updating Reality keys via X3UI API",
                        inbound_id=inbound_id,
                        error=str(e))
            return False

# Глобальный экземпляр клиента (DEPRECATED)
# Используйте X3UIClient(node.x3ui_url, node.x3ui_username, node.x3ui_password)
# для каждой ноды индивидуально
x3ui_client = None  # Удален глобальный клиент 