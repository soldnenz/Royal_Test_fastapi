#!/usr/bin/env python3
"""
Скрипт для запуска всех потребителей RabbitMQ одновременно.
Запускает consumer.py, log_consumer.py и telegram_log_bot.py в отдельных процессах.
"""

import asyncio
import subprocess
import sys
import signal
import os
import socket
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict
from urllib.parse import urlparse
from aiogram import Bot
from aiogram.enums import ParseMode

class ConsumerManager:
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.running = True
        self.max_retries = 3
        self.retry_delay = 5
        self.rabbitmq_url = os.getenv("RABBITMQ_URL")
        
        # Telegram settings
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.error_topic = os.getenv("TELEGRAM_ERROR_TOPIC")
        self.bot = Bot(token=self.bot_token)
        
        # Thread pool для чтения вывода процессов
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.read_threads: Dict[int, List[threading.Thread]] = {}
        
        # Event для синхронизации остановки
        self.stop_event = threading.Event()
    
    async def send_telegram_alert(self, message: str) -> None:
        """Отправляет уведомление в Telegram об ошибке"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=f"🚨 <b>RabbitMQ Alert</b>\n\n{message}",
                parse_mode=ParseMode.HTML,
                message_thread_id=int(self.error_topic)
            )
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления в Telegram: {e}")

    def read_output(self, pipe, description: str):
        """Читает вывод процесса в отдельном потоке"""
        try:
            while not self.stop_event.is_set():
                line = pipe.readline()
                if not line:
                    break
                    
                # В текстовом режиме line уже является строкой
                line_str = line.strip()
                if line_str:
                    print(f"[{description}] {line_str}")
                    
                    # Проверяем логи на наличие критических ошибок
                    if "CONNECTION_FORCED" in line_str or "connection closed" in line_str.lower():
                        asyncio.run(self.send_telegram_alert(
                            f"⚠️ Потеряно соединение с RabbitMQ в {description}!\n"
                            f"💬 Сообщение: {line_str}"
                        ))
        except Exception as e:
            print(f"❌ Ошибка чтения вывода {description}: {e}")

    async def check_rabbitmq_connection(self) -> bool:
        """Проверяет доступность RabbitMQ"""
        try:
            url = urlparse(self.rabbitmq_url)
            host = url.hostname or 'localhost'
            port = url.port or 5672
            
            for attempt in range(self.max_retries):
                try:
                    with socket.create_connection((host, port), timeout=5) as sock:
                        return True
                except (socket.timeout, ConnectionRefusedError):
                    if attempt < self.max_retries - 1:
                        print(f"⚠️ RabbitMQ недоступен, попытка {attempt + 1}/{self.max_retries}...")
                        await asyncio.sleep(self.retry_delay)
                    continue
            
            await self.send_telegram_alert(
                "❌ RabbitMQ недоступен после всех попыток подключения!\n"
                f"🔍 Хост: {host}\n"
                f"🔌 Порт: {port}\n"
                "⚠️ Потребители не могут быть запущены."
            )
            print("❌ RabbitMQ недоступен после всех попыток")
            return False
            
        except Exception as e:
            await self.send_telegram_alert(
                f"❌ Ошибка проверки подключения к RabbitMQ:\n"
                f"💬 Сообщение: {str(e)}"
            )
            print(f"❌ Ошибка проверки подключения к RabbitMQ: {e}")
            return False

    async def monitor_process(self, process: subprocess.Popen, description: str):
        """Мониторит процесс и его вывод"""
        if not process:
            return
        
        print(f"📊 Мониторинг {description} (PID: {process.pid})")
        
        # Создаем потоки для чтения stdout и stderr
        stdout_thread = threading.Thread(
            target=self.read_output,
            args=(process.stdout, f"{description} [OUT]"),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=self.read_output,
            args=(process.stderr, f"{description} [ERR]"),
            daemon=True
        )
        
        # Сохраняем потоки для последующей остановки
        self.read_threads[process.pid] = [stdout_thread, stderr_thread]
        
        # Запускаем потоки
        stdout_thread.start()
        stderr_thread.start()
        
        # Ждем завершения процесса
        while process.poll() is None and self.running:
            await asyncio.sleep(1)
        
        # Проверяем код возврата
        if process.returncode is not None and process.returncode != 0:
            await self.send_telegram_alert(
                f"⚠️ Процесс {description} завершился с ошибкой!\n"
                f"🔢 Код возврата: {process.returncode}"
            )
            print(f"⚠️ {description} завершился с кодом {process.returncode}")

    async def start_process(self, script_name: str, description: str) -> Optional[subprocess.Popen]:
        """Запускает процесс с повторными попытками"""
        for attempt in range(self.max_retries):
            try:
                print(f"🚀 Запускаем {description} (попытка {attempt + 1}/{self.max_retries})...")
                
                # Настраиваем окружение для Windows
                env = os.environ.copy()
                if sys.platform == 'win32':
                    env['PYTHONIOENCODING'] = 'utf-8'
                
                process = subprocess.Popen(
                    [sys.executable, script_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,  # Unbuffered output
                    universal_newlines=True,  # Text mode with universal newlines
                    encoding='utf-8',  # Явно указываем кодировку
                    errors='replace',  # Заменяем некорректные символы
                    env=env
                )
                
                print(f"✅ {description} запущен (PID: {process.pid})")
                
                # Создаем и сохраняем задачу мониторинга
                monitor_task = asyncio.create_task(self.monitor_process(process, description))
                
                self.processes.append(process)
                return process
                
            except Exception as e:
                print(f"❌ Ошибка запуска {description}: {e}")
                await self.send_telegram_alert(
                    f"❌ Ошибка запуска {description}:\n"
                    f"💬 Сообщение: {str(e)}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                
        return None

    async def run(self):
        """Запускает все процессы"""
        print("🎯 RabbitMQ Consumer Manager")
        print("=" * 50)

        # Проверяем доступность RabbitMQ
        if not await self.check_rabbitmq_connection():
            return

        # Запускаем процессы
        processes_to_start = [
            ("consumer.py", "Основной потребитель логов"),
            ("log_consumer.py", "Простой потребитель логов"),
            ("telegram_log_bot.py", "Telegram бот для логов")
        ]

        for script, desc in processes_to_start:
            if not await self.start_process(script, desc):
                print(f"❌ Не удалось запустить {desc}")
                await self.stop_all()
                return

        print(f"\n✅ Запущено {len(self.processes)} потребителей")
        print("📋 Нажмите Ctrl+C для остановки всех потребителей")
        print("=" * 50)

        # Ждем завершения всех процессов
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await self.stop_all()

    async def stop_all(self):
        """Останавливает все процессы"""
        print("\n🛑 Останавливаем все потребители...")
        self.running = False
        
        # Устанавливаем событие остановки для потоков чтения
        self.stop_event.set()
        
        # Останавливаем процессы
        for process in self.processes:
            if process and process.poll() is None:  # Процесс еще работает
                try:
                    print(f"📤 Отправлен сигнал завершения процессу {process.pid}")
                    process.terminate()
                except Exception as e:
                    print(f"❌ Ошибка остановки процесса {process.pid}: {e}")
                    await self.send_telegram_alert(
                        f"❌ Ошибка остановки процесса {process.pid}:\n"
                        f"💬 Сообщение: {str(e)}"
                    )
        
        # Ждем завершения всех процессов
        for process in self.processes:
            try:
                process.wait(timeout=5)
                print(f"✅ Процесс {process.pid} завершен")
                
                # Ждем завершения потоков чтения
                if process.pid in self.read_threads:
                    for thread in self.read_threads[process.pid]:
                        thread.join(timeout=2)
                
            except subprocess.TimeoutExpired:
                print(f"⚠️ Процесс {process.pid} не завершился за 5 секунд, принудительно завершаем")
                process.kill()
                await self.send_telegram_alert(
                    f"⚠️ Процесс {process.pid} принудительно завершен по таймауту"
                )
            except Exception as e:
                print(f"❌ Ошибка ожидания завершения процесса {process.pid}: {e}")
        
        # Закрываем ThreadPoolExecutor
        self.executor.shutdown(wait=False)
        
        # Закрываем бота
        await self.bot.session.close()

async def main():
    manager = ConsumerManager()
    
    # Настраиваем обработчики сигналов
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s, f: asyncio.create_task(manager.stop_all()))
    
    try:
        await manager.run()
    except KeyboardInterrupt:
        print("\n📡 Получен KeyboardInterrupt")
    finally:
        await manager.stop_all()

if __name__ == "__main__":
    if sys.platform == 'win32':
        # Используем SelectorEventLoop вместо ProactorEventLoop на Windows
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass 