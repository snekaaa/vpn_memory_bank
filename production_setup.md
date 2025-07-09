# Настройка Git на продакшн сервере

## 1. Установка и настройка Git

```bash
# Установка git (если не установлен)
sudo apt update
sudo apt install git -y

# Переходим в директорию где должен быть проект
cd /opt  # или /home/user или где вы хотите разместить

# Клонируем репозиторий
git clone https://github.com/snekaaa/vpn_memory_bank.git
cd vpn_memory_bank

# Настраиваем git для автоматических обновлений
git config pull.rebase false  # merge стратегия
git config credential.helper store  # сохранить токен доступа
```

## 2. Настройка SSH ключей (рекомендуется)

```bash
# Генерируем SSH ключ на сервере
ssh-keygen -t rsa -b 4096 -C "production-server@vpn.local"

# Показываем публичный ключ для добавления в GitHub
cat ~/.ssh/id_rsa.pub

# Добавьте этот ключ в настройки GitHub:
# GitHub → Settings → SSH and GPG keys → New SSH key
```

## 3. Клонирование через SSH (после настройки ключей)

```bash
# Если уже клонировали через HTTPS, переключаемся на SSH
cd /opt/vpn_memory_bank
git remote set-url origin git@github.com:snekaaa/vpn_memory_bank.git

# Тестируем соединение
ssh -T git@github.com
```

## 4. Создание скрипта автообновления

```bash
# Создаем скрипт автообновления
sudo nano /opt/vpn_memory_bank/deploy.sh
```

Содержимое скрипта:

```bash
#!/bin/bash

echo "🚀 Автообновление VPN сервиса..."

# Переходим в директорию проекта
cd /opt/vpn_memory_bank

# Останавливаем сервисы
echo "🛑 Остановка сервисов..."
cd vpn-service
docker-compose down

# Получаем последние изменения
echo "📦 Получение обновлений из репозитория..."
cd /opt/vpn_memory_bank
git fetch origin
git reset --hard origin/main

# Пересобираем и запускаем
echo "🔨 Пересборка сервисов..."
cd vpn-service
docker-compose build --no-cache
docker-compose up -d

# Проверяем статус
echo "✅ Проверка статуса..."
sleep 10
docker-compose ps

echo "🎉 Обновление завершено!"
echo "🔍 Проверьте логи: docker-compose logs backend --tail=20"
```

## 5. Настройка прав и создание алиаса

```bash
# Делаем скрипт исполняемым
chmod +x /opt/vpn_memory_bank/deploy.sh

# Создаем символическую ссылку для удобства
sudo ln -sf /opt/vpn_memory_bank/deploy.sh /usr/local/bin/vpn-deploy

# Теперь можно обновлять просто командой:
# vpn-deploy
```

## 6. Автоматические обновления через webhook (опционально)

```bash
# Установка webhook сервера
sudo apt install webhook -y

# Создание конфигурации webhook
sudo nano /etc/webhook.conf
```

Содержимое webhook.conf:

```json
[
  {
    "id": "vpn-deploy",
    "execute-command": "/opt/vpn_memory_bank/deploy.sh",
    "command-working-directory": "/opt/vpn_memory_bank",
    "response-message": "Deployment started",
    "trigger-rule": {
      "match": {
        "type": "payload-hash-sha1",
        "secret": "YOUR_WEBHOOK_SECRET",
        "parameter": {
          "source": "header",
          "name": "X-Hub-Signature"
        }
      }
    }
  }
]
```

```bash
# Запуск webhook сервера
sudo webhook -hooks /etc/webhook.conf -verbose -port 9000

# Настройка в GitHub:
# Repository → Settings → Webhooks → Add webhook
# Payload URL: http://your-server:9000/hooks/vpn-deploy
# Content type: application/json
# Secret: YOUR_WEBHOOK_SECRET
```

## 7. Быстрое обновление (ручное)

Теперь для обновления на проде просто выполните:

```bash
vpn-deploy
```

Или если не настроили алиас:

```bash
/opt/vpn_memory_bank/deploy.sh
``` 