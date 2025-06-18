import asyncio
import logging
from .lobby_ws import ws_manager

logger = logging.getLogger(__name__)

class PingTask:
    def __init__(self):
        self.running = False
        self.task = None
        
    async def start(self):
        """Запуск фоновой задачи пинга"""
        if self.running:
            return
            
        self.running = True
        self.task = asyncio.create_task(self._ping_loop())
        logger.info("Ping task started")
        
    async def stop(self):
        """Остановка фоновой задачи пинга"""
        if not self.running:
            return
            
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Ping task stopped")
        
    async def _ping_loop(self):
        """Основной цикл пинга"""
        while self.running:
            try:
                # Проверяем все активные лобби
                lobby_ids = list(ws_manager.connections.keys())
                for lobby_id in lobby_ids:
                    try:
                        await ws_manager.check_connections(lobby_id)
                    except Exception as e:
                        logger.error(f"Error checking connections in lobby {lobby_id}: {str(e)}")
                
                # Ждем интервал проверки
                await asyncio.sleep(ws_manager.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ping loop: {str(e)}")
                await asyncio.sleep(5)  # Короткая пауза при ошибке

# Глобальный экземпляр задачи пинга
ping_task = PingTask() 