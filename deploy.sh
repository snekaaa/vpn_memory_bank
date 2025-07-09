#!/bin/bash
set -e

echo "🚀 Отказоустойчивое обновление продакшн сервера..."
cd "$(dirname "$0")" # Переходим в директорию скрипта

# Проверка наличия production compose файла
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ Ошибка: не найден docker-compose.prod.yml"
    exit 1
fi

# 1. Получаем последние изменения
echo "📦 Получение обновлений из git..."
git fetch origin
git reset --hard origin/main

# 2. Полная остановка и очистка предыдущих запусков
# Это помогает избежать багов в старых версиях docker-compose
echo "🧹 Полная очистка предыдущих контейнеров..."
docker-compose -f docker-compose.prod.yml down --remove-orphans

# 3. Принудительная пересборка и запуск
# --force-recreate - ключ к обходу бага 'ContainerConfig'
echo "🔨 Принудительная пересборка и запуск сервисов..."
docker-compose -f docker-compose.prod.yml up -d --build --force-recreate

# 4. Проверка
echo "⏱️ Ожидание запуска сервисов (15 секунд)..."
sleep 15
echo "✅ Статус контейнеров:"
docker-compose -f docker-compose.prod.yml ps

echo "🎉 Обновление завершено!"
echo "🔍 Проверьте админку: https://bezlagov.ru:8443/admin/"
echo "🧪 Проверьте Робокассу. Если снова ошибка, посмотрите логи:"
echo "docker logs vpn_memory_bank_backend_1 --tail 50" 