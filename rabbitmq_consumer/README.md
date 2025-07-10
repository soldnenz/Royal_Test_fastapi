# RabbitMQ Consumer Service

This service consumes messages from RabbitMQ and processes them according to their routing keys.

## Docker Setup

### Prerequisites
- Docker
- Docker Compose

### Environment Variables
Create a `.env` file in the root directory with the following variables:

```env
# Telegram Bot Settings
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
TELEGRAM_WARNING_TOPIC=2
TELEGRAM_ERROR_TOPIC=3

# RabbitMQ Settings
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=royal_logger
RABBITMQ_PASSWORD=Royal_Logger_Pass
RABBITMQ_VHOST=royal_logs
RABBITMQ_URL=amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@${RABBITMQ_HOST}:${RABBITMQ_PORT}/${RABBITMQ_VHOST}
RABBITMQ_EXCHANGE=logs_exchange
RABBITMQ_QUEUE=telegram_log_bot_queue

# Debug Settings (1 = True, 0 = False)
DEBUG=0

# Encoding Settings
PYTHONIOENCODING=utf-8
```

### Generate Requirements
To generate requirements.txt with exact versions:

```bash
python generate_requirements.py
```

### Build and Run
1. Build the container:
```bash
docker-compose build
```

2. Start the service:
```bash
docker-compose up -d
```

3. View logs:
```bash
docker-compose logs -f
```

4. Stop the service:
```bash
docker-compose down
```

### Network Configuration
The service connects to the RabbitMQ network automatically through Docker Compose networking. Make sure the RabbitMQ service is running before starting this consumer.

### Resource Limits
The service is configured with the following resource limits:
- Memory: 256MB max
- CPU: 0.5 cores max

### Volumes
- `./logs`: Service logs
- Timezone information is shared from host

### Health Monitoring
Monitor the service status using:
```bash
docker-compose ps
```

## Development

### Local Setup
1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the consumer:
```bash
python start_consumers.py
``` 