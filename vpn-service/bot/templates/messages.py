"""
Шаблоны сообщений для упрощенного VPN бота
"""

def get_vpn_key_message(vless_url: str, is_update: bool = False) -> str:
    """Сообщение с VPN ключом и инструкцией"""
    action = "обновлён" if is_update else "создан"
    
    return f"""🔑 Ваш VPN ключ {action}:

`{vless_url}`

📱 Как использовать:
1. Скопируйте ключ выше
2. Откройте приложение V2Ray/Shadowrocket/Clash
3. Добавьте конфигурацию из буфера обмена

🔥 VPN готов к использованию!"""

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