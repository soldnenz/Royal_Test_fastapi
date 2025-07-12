# RedisInsight Docker Setup

## Описание
RedisInsight - это графический интерфейс для управления и мониторинга Redis. Этот Docker контейнер запускает RedisInsight с ограничением памяти в 512MB.

## Требования
- Docker Desktop для Windows
- Запущенный Redis (опционально)

## Файлы
- `docker-compose.yml` - конфигурация Docker контейнера
- `start_redisinsight.bat` - скрипт для запуска контейнера
- `stop_redisinsight.bat` - скрипт для остановки контейнера
- `restart_redisinsight.bat` - скрипт для перезапуска контейнера
- `status_redisinsight.bat` - скрипт для проверки статуса контейнера

## Использование

### Запуск RedisInsight
1. Запустите Docker Desktop
2. Запустите `start_redisinsight.bat`
3. Откройте веб-браузер и перейдите по адресу: http://localhost:8012

### Подключение к Redis
1. В веб-интерфейсе RedisInsight нажмите "Add Redis Database"
2. Выберите тип подключения (обычно "Standalone")
3. Введите следующие данные:
   - Host: host.docker.internal (для подключения к локальному Redis)
   - Port: 6379
   - Name: Любое имя для вашего подключения
   - Password: Royal_Redis_1337 (если используется пароль из вашей конфигурации Redis)

### Остановка RedisInsight
Запустите `stop_redisinsight.bat`

### Перезапуск RedisInsight
Запустите `restart_redisinsight.bat`

### Проверка статуса
Запустите `status_redisinsight.bat`

## Настройка
- Порт по умолчанию: 8012
- Ограничение памяти: 512MB
- Данные сохраняются в директории `./data`

## Примечания
- Для подключения к локальному Redis используйте хост `host.docker.internal` вместо `localhost`
- Если вы изменяете порт в `docker-compose.yml`, обновите также информацию в batch-файлах 