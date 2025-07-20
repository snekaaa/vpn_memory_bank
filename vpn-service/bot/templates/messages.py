"""
Шаблоны сообщений для упрощенного VPN бота
"""

def get_vpn_key_message(vless_url: str, is_update: bool = False) -> str:
    """Сообщение с VPN ключом и инструкцией (старый формат без сервера)"""
    action = "обновлён" if is_update else "создан"
    
    return f"""🔑 Ваш VPN ключ {action}:

`{vless_url}`

📱 Как использовать:
1. Скопируйте ключ выше
2. Откройте приложение V2Ray/Shadowrocket/Clash
3. Добавьте конфигурацию из буфера обмена

🔥 VPN готов к использованию!"""

def get_vpn_key_message_with_server(vless_url: str, current_country: dict, is_update: bool = False) -> str:
    """
    Расширенное сообщение с VPN ключом и информацией о текущем сервере
    
    Args:
        vless_url: VPN ключ
        current_country: dict с ключами {code, name, flag_emoji}
        is_update: True если это обновление ключа
    """
    action = "обновлён" if is_update else "создан"
    
    return f"""🔑 Ваш VPN ключ {action}:

`{vless_url}`

📱 Как использовать:
1. Скопируйте ключ выше
2. Откройте приложение V2Ray/Shadowrocket/Clash
3. Добавьте конфигурацию из буфера обмена

Текущий сервер: {current_country['flag_emoji']} {current_country['name']}

🔥 VPN готов к использованию!"""

def get_server_switch_loading_message(country_name: str, step: int = 1) -> str:
    """
    Прогрессивные сообщения во время переключения сервера
    
    Args:
        country_name: Название страны на которую переключаемся
        step: Номер шага (1-3)
    """
    messages = {
        1: f"""🔄 Переключаем на сервер {country_name}...
⏳ Создаем новый ключ...

Это займет 15-30 секунд""",
        
        2: f"""🔄 Настраиваем подключение...
⏳ Почти готово...

💡 Совет: После смены сервера обязательно обновите конфигурацию в вашем VPN приложении""",
        
        3: f"""✅ Сервер изменен!
🌍 Теперь вы подключены к серверу {country_name}

🔑 Ваш новый VPN ключ:"""
    }
    
    return messages.get(step, messages[1])

def get_server_switch_success_message(vless_url: str, country: dict) -> str:
    """
    Сообщение об успешном переключении сервера
    
    Args:
        vless_url: Новый VPN ключ
        country: dict с информацией о стране {code, name, flag_emoji}
    """
    return f"""✅ Сервер изменен!
{country['flag_emoji']} Теперь вы подключены к серверу {country['name']}

🔑 Ваш новый VPN ключ:
`{vless_url}`

📲 Не забудьте:
1. Удалить старую конфигурацию в VPN приложении
2. Добавить новый ключ из буфера обмена
3. Включить VPN

🔥 Готово к использованию!"""

def get_server_switch_error_message(country_name: str, error_reason: str = None) -> str:
    """
    Сообщение об ошибке переключения сервера
    
    Args:
        country_name: Название страны
        error_reason: Причина ошибки (опционально)
    """
    base_message = f"""❌ Не удалось переключиться на сервер {country_name}

Попробуйте:
• Выбрать другой сервер
• Повторить попытку через минуту"""
    
    if error_reason:
        base_message += f"\n\n🔍 Причина: {error_reason}"
    
    base_message += "\n\n🧑🏼‍💻 Поддержка: @bez_lagov"
    
    return base_message

def get_download_apps_message() -> str:
    """Сообщение со ссылками на приложения"""
    return """📱 Выберите вашу платформу:

🤖 **Android:**
• [V2RayTun](https://play.google.com/store/apps/details?id=com.v2raytun.android&hl=ru)

📱 **iOS (App Store):**
• [V2RayTun](https://apps.apple.com/ru/app/v2raytun/id6476628951)

🖥 **Windows:**
• [Hiddify](https://disk.yandex.ru/d/RWkgW7OXmpVeNQ) 

💻 **Mac:**
• [V2box](https://apps.apple.com/ru/app/v2box-v2ray-client/id6446814690)

📔 [Инструкция как подключиться к VPN](https://telegra.ph/Instrukciya-po-podklyucheniyu-VPN-06-14)"""


def get_support_message() -> str:
    """Сообщение с контактом поддержки"""
    return """🧑🏼‍💻 Служба поддержки

По всем вопросам обращайтесь:
👤 @bez_lagov

Мы поможем:
• Настроить VPN на любом устройстве
• Решить проблемы с подключением
• Ответить на вопросы по использованию

⚡ Ответим в течение 30 минут!"""

def get_no_key_error() -> str:
    """Сообщение об ошибке получения ключа"""
    return """❌ Не удалось получить VPN ключ

Попробуйте:
• Повторить запрос через минуту
• Обратиться в поддержку если проблема повторяется

🧑🏼‍💻 Поддержка: @bez_lagov"""

def get_key_update_error() -> str:
    """Сообщение об ошибке обновления ключа"""
    return """❌ Не удалось обновить VPN ключ

Попробуйте:
• Повторить запрос через минуту
• Сначала создать ключ если его нет

🧑🏼‍💻 Поддержка: @bez_lagov"""

# Сообщение с обновленным VPN ключом (убраны HTML теги)
VPN_KEY_REFRESHED = """✅ Ваш VPN ключ успешно обновлен!

🔑 Ваш новый ключ:
`{vless_url}`

📲 Как использовать:
1. Скопируйте ключ полностью
2. Откройте приложение V2rayNG/Shadowrocket
3. Удалите старый ключ
4. Импортируйте новый ключ
5. Включите VPN

❓ Нужна помощь? Напишите в поддержку: @bez_lagov
""" 