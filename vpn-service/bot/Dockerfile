FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование requirements.txt из корня проекта
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Установка зависимостей для PostgreSQL
RUN pip install --no-cache-dir sqlalchemy psycopg2-binary asyncpg

# Копирование кода бота
COPY . .

# Добавляем директорию backend в PYTHONPATH
ENV PYTHONPATH=/app:/app/backend
ENV DATABASE_URL=postgresql+asyncpg://vpn_user:vpn_password@db:5432/vpn_db

# Создание пользователя для безопасности
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Команда запуска
CMD ["python", "main.py"] 