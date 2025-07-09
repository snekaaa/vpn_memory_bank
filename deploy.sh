#!/bin/bash

echo "🚀 Автообновление VPN сервиса..."

# Определяем директорию скрипта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Проверяем что мы в правильной директории
if [ ! -f "vpn-service/docker-compose.yml" ]; then
    echo "❌ Ошибка: не найден docker-compose.yml в vpn-service/"
    echo "Убедитесь что скрипт запущен из корня проекта"
    exit 1
fi

# Останавливаем сервисы
echo "🛑 Остановка сервисов..."
cd vpn-service
docker-compose down

# Получаем последние изменения
echo "📦 Получение обновлений из репозитория..."
cd "$SCRIPT_DIR"
git fetch origin
echo "Текущий коммит: $(git rev-parse HEAD)"
git reset --hard origin/main
echo "Новый коммит: $(git rev-parse HEAD)"

# Показываем что изменилось
echo "📋 Список изменений:"
git log --oneline -5

# Пересобираем и запускаем
echo "🔨 Пересборка backend сервиса..."
cd vpn-service
docker-compose build backend --no-cache

echo "▶️ Запуск всех сервисов..."
docker-compose up -d

# Проверяем статус
echo "⏱️ Ждем запуск сервисов..."
sleep 15

echo "✅ Проверка статуса сервисов:"
docker-compose ps

# Проверяем что backend отвечает
echo "🔍 Проверка работы API..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ API отвечает"
else
    echo "❌ API не отвечает, проверьте логи"
fi

echo ""
echo "🎉 Обновление завершено!"
echo "🔍 Для просмотра логов: docker-compose logs backend --tail=50"
echo "🧪 Тест Робокассы: curl 'http://localhost:8000/api/v1/payments/robokassa/success?OutSum=889.00&InvId=7&SignatureValue=3e5a8b43e842fd47c9b1dd55815d030a&IsTest=1'" 