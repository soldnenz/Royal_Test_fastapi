FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --timeout=300 --retries=5 -r requirements.txt

# Копируем исходный код
COPY . .

# Создание необходимых папок для медиа файлов и логов
RUN mkdir -p logs && \
    mkdir -p video_test/images && \
    mkdir -p video_test/videos && \
    mkdir -p video_test/audio && \
    mkdir -p video_test/documents && \
    mkdir -p static_media && \
    chmod -R 755 video_test static_media logs

# Копируем и делаем исполняемым init скрипт
COPY init_folders.sh /app/
RUN chmod +x /app/init_folders.sh

# Создаем пользователя для безопасности (закомментировано для dev)
# RUN useradd --create-home --shell /bin/bash app && \
#     chown -R app:app /app
# USER app

# Открываем порт
EXPOSE 8000

# Используем ENTRYPOINT для гарантированного создания папок при каждом старте
ENTRYPOINT ["/app/init_folders.sh"]

# Запускаем приложение
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 