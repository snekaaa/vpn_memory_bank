#!/bin/bash

echo "🚀 Обновление продакшн сервера..."

# Переходим в директорию проекта на сервере
cd /path/to/vpn_memory_bank

# Получаем последние изменения из репозитория
echo "📦 Получение последних изменений..."
git pull origin main

# Переходим в директорию сервисов
cd vpn-service

# Останавливаем контейнеры
echo "🛑 Остановка контейнеров..."
docker-compose down

# Пересобираем backend контейнер с новыми изменениями
echo "🔨 Пересборка backend контейнера..."
docker-compose build backend

# Запускаем все сервисы
echo "▶️ Запуск обновленных сервисов..."
docker-compose up -d

# Проверяем статус
echo "✅ Проверка статуса сервисов..."
docker-compose ps

# Тестируем исправление Робокассы
echo "🧪 Тестирование исправления Робокассы..."
sleep 10
curl -X GET "http://localhost:8000/api/v1/payments/robokassa/success?OutSum=100.00&InvId=test&SignatureValue=test&IsTest=1" -s | head -c 100

echo ""
echo "🎉 Обновление завершено!"
echo "🔍 Проверьте логи: docker-compose logs backend --tail=50" 