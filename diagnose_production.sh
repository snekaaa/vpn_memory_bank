#!/bin/bash

echo "🔍 Диагностика Робокассы на продакшне..."

# Переходим в директорию проекта
cd /path/to/vpn_memory_bank

echo "📦 Обновляем код с новым логированием..."
git pull origin main

echo "🔨 Пересобираем backend..."
cd vpn-service
docker-compose build backend --no-cache
docker-compose up -d backend

echo "⏱️ Ждем запуск backend..."
sleep 15

echo "🧪 Тестируем с вашими параметрами..."
echo "Отправляем запрос:"
echo "OutSum=889.00&InvId=7&SignatureValue=3e5a8b43e842fd47c9b1dd55815d030a&IsTest=1&Culture=ru"

curl -X GET "http://localhost:8000/api/v1/payments/robokassa/success?OutSum=889.00&InvId=7&SignatureValue=3e5a8b43e842fd47c9b1dd55815d030a&IsTest=1&Culture=ru" \
  -H "Content-Type: application/json" -v

echo ""
echo ""
echo "📋 Последние логи backend (ищем ROBOKASSA DEBUG):"
docker-compose logs backend --tail=100 | grep -A 20 -B 5 "ROBOKASSA DEBUG\|SUCCESS SIGNATURE DEBUG\|Invalid\|Error"

echo ""
echo "🔍 Полные логи backend за последние 5 минут:"
echo "docker-compose logs backend --since=5m" 