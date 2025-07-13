from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from typing import List, Optional
import logging
from config import MONGO_URI, MONGO_DB_NAME, COLLECTION_NAME
from models import QuestionReport, ReportStatus

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.collection: Optional[Collection] = None
        
    def connect(self):
        """Подключение к MongoDB"""
        try:
            self.client = MongoClient(MONGO_URI)
            self.db = self.client[MONGO_DB_NAME]
            self.collection = self.db[COLLECTION_NAME]
            
            # Проверка подключения
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def disconnect(self):
        """Отключение от MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    def get_pending_reports(self) -> List[QuestionReport]:
        """Получение отчетов со статусом 'sending'"""
        try:
            cursor = self.collection.find({"status": ReportStatus.SENDING})
            reports = []
            
            for doc in cursor:
                try:
                    report = QuestionReport(**doc)
                    reports.append(report)
                except Exception as e:
                    logger.error(f"Error parsing report {doc.get('_id')}: {e}")
                    continue
            
            return reports
            
        except Exception as e:
            logger.error(f"Error getting pending reports: {e}")
            return []
    
    def update_report_status(self, report_id: str, new_status: str):
        """Обновление статуса отчета"""
        try:
            result = self.collection.update_one(
                {"_id": report_id},
                {"$set": {"status": new_status}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated report {report_id} status to {new_status}")
                return True
            else:
                logger.warning(f"No report found with id {report_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating report status: {e}")
            return False
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect() 