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
from typing import List

class ConsumerManager:
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.running = True
    
    def start_consumer(self, script_name: str, description: str):
        """Запускает потребителя в отдельном процессе"""
        try:
            print(f"🚀 Запускаем {description}...")
            process = subprocess.Popen(
                [sys.executable, script_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            self.processes.append(process)
            print(f"✅ {description} запущен (PID: {process.pid})")
            return process
        except Exception as e:
            print(f"❌ Ошибка запуска {description}: {e}")
            return None
    
    def monitor_process(self, process: subprocess.Popen, description: str):
        """Мониторит процесс и выводит его логи"""
        if not process:
            return
        
        print(f"📊 Мониторинг {description} (PID: {process.pid})")
        
        while process.poll() is None and self.running:
            try:
                output = process.stdout.readline()
                if output:
                    print(f"[{description}] {output.strip()}")
            except Exception as e:
                print(f"❌ Ошибка мониторинга {description}: {e}")
                break
        
        if process.returncode is not None:
            print(f"⚠️ {description} завершился с кодом {process.returncode}")
    
    def stop_all(self):
        """Останавливает все процессы"""
        print("\n🛑 Останавливаем все потребители...")
        self.running = False
        
        for process in self.processes:
            if process.poll() is None:  # Процесс еще работает
                try:
                    process.terminate()
                    print(f"📤 Отправлен сигнал завершения процессу {process.pid}")
                except Exception as e:
                    print(f"❌ Ошибка остановки процесса {process.pid}: {e}")
        
        # Ждем завершения всех процессов
        for process in self.processes:
            try:
                process.wait(timeout=5)
                print(f"✅ Процесс {process.pid} завершен")
            except subprocess.TimeoutExpired:
                print(f"⚠️ Процесс {process.pid} не завершился за 5 секунд, принудительно завершаем")
                process.kill()
            except Exception as e:
                print(f"❌ Ошибка ожидания завершения процесса {process.pid}: {e}")
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        print(f"\n📡 Получен сигнал {signum}, начинаем graceful shutdown...")
        self.stop_all()
        sys.exit(0)
    
    async def run(self):
        """Основной метод запуска всех потребителей"""
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("🎯 RabbitMQ Consumer Manager")
        print("=" * 50)
        
        # Запускаем потребителей
        consumers = [
            ("consumer.py", "Основной потребитель логов"),
            ("log_consumer.py", "Простой потребитель логов"),
            ("telegram_log_bot.py", "Telegram бот для логов")
        ]
        
        processes = []
        for script, description in consumers:
            process = self.start_consumer(script, description)
            if process:
                processes.append((process, description))
        
        if not processes:
            print("❌ Не удалось запустить ни одного потребителя")
            return
        
        print(f"\n✅ Запущено {len(processes)} потребителей")
        print("📋 Нажмите Ctrl+C для остановки всех потребителей")
        print("=" * 50)
        
        # Мониторим все процессы
        try:
            # Создаем задачи для мониторинга каждого процесса
            tasks = []
            for process, description in processes:
                task = asyncio.create_task(
                    asyncio.to_thread(self.monitor_process, process, description)
                )
                tasks.append(task)
            
            # Ждем завершения всех задач
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except KeyboardInterrupt:
            print("\n📡 Получен KeyboardInterrupt")
        finally:
            self.stop_all()

def main():
    """Точка входа"""
    manager = ConsumerManager()
    
    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        print("\n👋 Программа завершена пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        manager.stop_all()

if __name__ == "__main__":
    main() 