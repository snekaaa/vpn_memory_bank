# CREATIVE PHASE: АЛГОРИТМЫ СИСТЕМЫ ПОДПИСОК

## 🧮 АЛГОРИТМИЧЕСКИЕ РЕШЕНИЯ

### 1. АЛГОРИТМ ПРОВЕРКИ ПОДПИСИ

**Проблема**: Безопасная валидация webhook'ов от Robokassa.

**Решение**: Полная проверка с константным временем сравнения

```python
class RobokassaSignatureValidator:
    def verify_result_signature(self, webhook_data: Dict[str, Any]) -> bool:
        # Формируем строку для подписи
        signature_string = f"{webhook_data['OutSum']}:{webhook_data['InvId']}:{self.password2}"
        
        # Добавляем Shp_ параметры если есть
        shp_params = sorted([
            (k, v) for k, v in webhook_data.items() 
            if k.startswith('Shp_')
        ])
        for key, value in shp_params:
            signature_string += f":{key}={value}"
        
        # MD5 + константное время сравнения
        expected = hashlib.md5(signature_string.encode('utf-8')).hexdigest().upper()
        return hmac.compare_digest(expected, webhook_data['SignatureValue'].upper())
```

**Временная сложность**: O(n) где n - количество параметров
**Пространственная сложность**: O(1)

### 2. ЛОГИКА АКТИВАЦИИ ПОДПИСКИ  

**Проблема**: Корректная активация с учетом различных сценариев.

**Решение**: Умная логика с накоплением времени

```python
class SubscriptionActivator:
    def activate_subscription(self, user, payment_data):
        months = payment_data['subscription_months']
        now = datetime.utcnow()
        
        # Определяем дату начала
        if user.subscription_end_date and user.subscription_end_date > now:
            # Продление активной подписки - накопление времени
            start_date = user.subscription_end_date
        else:
            # Новая подписка или реактивация
            start_date = now
        
        # Новая дата окончания
        end_date = start_date + timedelta(days=30 * months)
        
        # Атомарное обновление
        user.subscription_end_date = end_date
        user.subscription_status = 'active'
        user.last_payment_date = now
        
        return {
            'activated_at': now,
            'expires_at': end_date,
            'total_days_added': 30 * months
        }
```

**Временная сложность**: O(1)
**Пространственная сложность**: O(1)

### 3. СИСТЕМА УВЕДОМЛЕНИЙ

**Проблема**: Своевременные напоминания о продлении подписки.

**Решение**: Планировщик с правилами уведомлений

```python
class NotificationScheduler:
    def __init__(self):
        self.notification_rules = [
            {'days_before': 30, 'message_type': 'reminder'},
            {'days_before': 7, 'message_type': 'urgent'},  
            {'days_before': 1, 'message_type': 'critical'},
            {'days_after': 0, 'message_type': 'expired'}
        ]
    
    async def check_and_send_notifications(self):
        now = datetime.utcnow()
        
        for rule in self.notification_rules:
            target_date = self.calculate_target_date(now, rule)
            users = await self.get_users_for_notification(target_date, rule)
            
            for user in users:
                await self.send_personalized_notification(user, rule['message_type'])
    
    def calculate_target_date(self, now, rule):
        if 'days_before' in rule:
            return now + timedelta(days=rule['days_before'])
        else:
            return now - timedelta(days=rule['days_after'])
    
    async def send_personalized_notification(self, user, message_type):
        template = self.get_message_template(message_type)
        message = template.format(
            name=user.first_name,
            expire_date=user.subscription_end_date.strftime('%d.%m.%Y'),
            days_left=self.calculate_days_left(user.subscription_end_date)
        )
        await self.bot.send_message(user.telegram_id, message)
```

**Временная сложность**: O(n*m) где n - пользователи, m - правила
**Пространственная сложность**: O(1)

## 🔄 АЛГОРИТМИЧЕСКАЯ ИНТЕГРАЦИЯ

```python
class PaymentProcessor:
    def __init__(self, validator, activator, scheduler):
        self.validator = validator
        self.activator = activator
        self.scheduler = scheduler
    
    async def process_payment_webhook(self, webhook_data):
        # 1. Валидация подписи
        if not self.validator.verify_result_signature(webhook_data):
            raise SecurityError("Invalid signature")
        
        # 2. Активация подписки
        user = await self.get_user_by_invoice(webhook_data['InvId'])
        result = self.activator.activate_subscription(user, webhook_data)
        
        # 3. Планирование уведомлений
        await self.scheduler.schedule_notifications_for_user(user)
        
        return result
```

## ⚡ ОПТИМИЗАЦИИ

### Batch обработка уведомлений
```python
async def process_notifications_batch(self, users_batch):
    """Обработка уведомлений пакетами для производительности"""
    tasks = [
        self.send_notification(user, message_type) 
        for user in users_batch
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
```

### Кеширование подписей
```python
class CachedSignatureValidator:
    def __init__(self, cache_size=1000):
        self.signature_cache = {}
        self.cache_size = cache_size
    
    def verify_with_cache(self, webhook_data):
        cache_key = self.generate_cache_key(webhook_data)
        
        if cache_key in self.signature_cache:
            return self.signature_cache[cache_key]
        
        result = self.verify_result_signature(webhook_data)
        
        if len(self.signature_cache) >= self.cache_size:
            self.signature_cache.pop(next(iter(self.signature_cache)))
        
        self.signature_cache[cache_key] = result
        return result
```

## ✅ АЛГОРИТМИЧЕСКАЯ ВЕРИФИКАЦИЯ

- [x] Проверка подписи: Безопасная валидация с константным временем
- [x] Активация подписки: Корректная обработка всех сценариев
- [x] Уведомления: Персонализированная система с правилами
- [x] Производительность: O(1) для критических операций
- [x] Безопасность: Защита от timing attacks
- [x] Масштабируемость: Batch обработка и кеширование

🎨🎨🎨 **ALGORITHMS CREATIVE PHASE COMPLETE** 🎨🎨🎨 