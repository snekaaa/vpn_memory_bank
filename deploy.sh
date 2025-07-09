#!/bin/bash
set -e

echo "🚀 Безопасное обновление продакшн сервера..."

# Определяем директорию скрипта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Проверяем наличие production compose файла
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ Ошибка: не найден docker-compose.prod.yml"
    exit 1
fi

# Получаем последние изменения из master/main ветки
echo "📦 Получение обновлений из репозитория..."
git fetch origin
git reset --hard origin/main

echo "📋 Последние 5 коммитов:"
git log --oneline -5

# Запускаем docker-compose с production файлом
# --build соберет только те сервисы, у которых изменился код
# Docker-compose сам перезапустит только обновленные контейнеры
echo "🔨 Сборка и перезапуск измененных сервисов..."
docker-compose -f docker-compose.prod.yml up -d --build

# Проверяем статус
echo "⏱️ Ждем запуск сервисов (15 секунд)..."
sleep 15

echo "✅ Проверка статуса контейнеров:"
docker-compose -f docker-compose.prod.yml ps

# Проверяем что backend отвечает
echo "🔍 Проверка работы API админки (http://localhost:8001)..."
if curl -s http://localhost:8001/health | grep -q "healthy"; then
    echo "✅ API отвечает"
else
    echo "❌ API не отвечает, проверьте логи: docker-compose -f docker-compose.prod.yml logs backend"
fi

echo ""
echo "🎉 Обновление завершено!"
echo "Теперь все сервисы работают из директории $SCRIPT_DIR и синхронизированы с git."
echo "Следующее обновление - просто запустите ./deploy.sh" 