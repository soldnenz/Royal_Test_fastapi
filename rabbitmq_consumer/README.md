# RabbitMQ Log Consumer

Консьюмер для приема и обработки логов из RabbitMQ.

## Установка

1. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

## Настройка

Консьюмер использует следующие переменные окружения:

- `RABBITMQ_URL` - URL подключения к RabbitMQ (по умолчанию: "amqp://guest:guest@localhost:5672/")
- `RABBITMQ_EXCHANGE` - Имя exchange (по умолчанию: "logs")
- `RABBITMQ_ROUTING_KEY` - Routing key для сообщений (по умолчанию: "application.logs")
- `RABBITMQ_QUEUE` - Имя очереди для обработки логов (по умолчанию: "log_processing_queue")

## Запуск

```bash
python consumer.py
```

## Формат логов

Консьюмер ожидает сообщения в следующем формате:

```json
{
    "timestamp": "2024-03-07T14:30:00Z",
    "log_id": "unique_id",
    "level": "WARNING",
    "section": "api",
    "subsection": "auth",
    "message": "Текст сообщения",
    "extra_data": {
        "user_id": "123",
        "ip": "192.168.1.1",
        "additional_info": "..."
    }
}
```

## Обработка логов

По умолчанию консьюмер просто выводит полученные логи в консоль в отформатированном виде. 
Для добавления дополнительной обработки (например, сохранение в базу данных или отправка уведомлений) 
модифицируйте метод `process_log` в классе `LogProcessor`.

## Остановка

Для остановки консьюмера нажмите Ctrl+C. Программа корректно закроет соединение с RabbitMQ перед завершением. 