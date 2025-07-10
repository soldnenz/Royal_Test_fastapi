from fastapi import APIRouter, HTTPException, Depends, Request, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from bson.errors import InvalidId


from app.db.database import db
from app.core.security import get_current_actor
from app.core.response import success
from app.schemas.report_schemas import (
    QuestionReportCreate, 
    QuestionReportOut, 
    QuestionReportUpdate,
    ReportStatsOut,
    ReportType,
    ReportStatus
)
from app.admin.permissions import get_current_admin_user
from app.logging import get_logger, LogSection, LogSubsection
from app.rate_limit import rate_limit_ip

logger = get_logger("question_report")
router = APIRouter(tags=["reports"])

async def validate_user_can_report(user_id: str, lobby_id: str) -> dict:
    """Простая валидация прав пользователя"""
    
    # Проверяем лобби (поддерживаем как строковые, так и ObjectId идентификаторы)
    try:
        lobby_filter = {"_id": ObjectId(lobby_id)}
    except InvalidId:
        lobby_filter = {"_id": lobby_id}

    lobby = await db.lobbies.find_one(lobby_filter)
    if not lobby:
        raise HTTPException(status_code=404, detail="Лобби не найдено")
    
    # Проверяем участие в лобби
    participants = lobby.get('participants', [])
    if user_id not in participants:
        raise HTTPException(status_code=403, detail="Вы не участник этого лобби")
    
    # Проверяем дневной лимит
    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_reports = await db.question_reports.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": day_start}
    })
    
    if daily_reports >= 10:  # MAX_REPORTS_PER_DAY = 10
        raise HTTPException(status_code=429, detail="Превышен дневной лимит жалоб")
    
    return lobby


async def check_duplicate_report(user_id: str, lobby_id: str, question_id: str) -> bool:
    """Проверка дублирования жалобы"""
    existing = await db.question_reports.find_one({
        "user_id": user_id,
        "lobby_id": lobby_id,
        "question_id": question_id,
        "status": {"$in": ["sending", "reviewed"]}
    })
    return existing is not None

@router.post("/test/submit", response_model=Dict[str, Any])
@rate_limit_ip("question_report_submit", max_requests=3, window_seconds=300)  # 3 жалобы за 5 минут
async def submit_question_report(
    report_data: QuestionReportCreate = ...,
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """Отправка жалобы на вопрос"""
    try:
        user_id = str(current_user.get('id'))
        ip_address = request.client.host if request and request.client else "unknown"
        
        # Валидация прав
        lobby = await validate_user_can_report(user_id, report_data.lobby_id)
        
        # Проверка существования вопроса в лобби
        lobby_question_ids = lobby.get('question_ids', [])
        question_exists = report_data.question_id in lobby_question_ids
        
        if not question_exists:
            raise HTTPException(status_code=404, detail="Вопрос не найден в лобби")
        
        # Проверка дублирования
        duplicate_exists = await check_duplicate_report(user_id, report_data.lobby_id, report_data.question_id)
        if duplicate_exists:
            raise HTTPException(status_code=400, detail="Вы уже отправили жалобу на этот вопрос")
        
        # Создание жалобы
        report_doc = {
            "_id": str(ObjectId()),
            "lobby_id": report_data.lobby_id,
            "question_id": report_data.question_id,
            "user_id": user_id,
            "report_type": report_data.report_type.value,
            "description": report_data.description,
            "status": "sending",
            "created_at": datetime.utcnow(),
            "ip_address": ip_address
        }
        
        await db.question_reports.insert_one(report_doc)
        
        logger.info(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.REPORT_CREATE,
            message=f"Жалоба создана: пользователь {user_id}, лобби {report_data.lobby_id}, вопрос {report_data.question_id}"
        )
        
        return success(
            data={
                "report_id": report_doc["_id"],
                "status": "sending",
                "message": "Жалоба отправлена на рассмотрение"
            },
            message="Жалоба успешно отправлена"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.REPORT_ERROR,
            message=f"Ошибка при создании жалобы: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/my-reports", response_model=Dict[str, Any])
@rate_limit_ip("question_reports_my", max_requests=60, window_seconds=60)  # 60 запросов в минуту
async def get_my_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    status: Optional[ReportStatus] = Query(None),
    request: Request = None,
    current_user: dict = Depends(get_current_actor)
):
    """Получение списка своих жалоб"""
    try:
        user_id = str(current_user.get('id'))
        
        # Фильтры
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status.value
        
        # Подсчет и получение данных
        total = await db.question_reports.count_documents(filters)
        skip = (page - 1) * limit
        
        reports = await db.question_reports.find(filters)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(None)
        
        # Преобразование данных
        reports_out = [_serialize_report(r, include_ip=True) for r in reports]
        
        return success(
            data={
                "reports": reports_out,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            },
            message="Жалобы получены"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.REPORT_ERROR,
            message=f"Ошибка при получении жалоб: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/admin/list", response_model=Dict[str, Any])
@rate_limit_ip("question_reports_admin_list", max_requests=50, window_seconds=60)  # 50 запросов в минуту
async def get_all_reports_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ReportStatus] = Query(None),
    report_type: Optional[ReportType] = Query(None),
    request: Request = None,
    current_admin: dict = Depends(get_current_admin_user)
):
    """Получение всех жалоб (админ)"""
    try:
        # Фильтры
        filters = {}
        if status:
            filters["status"] = status.value
        if report_type:
            filters["report_type"] = report_type.value
        
        # Подсчет и получение данных
        total = await db.question_reports.count_documents(filters)
        skip = (page - 1) * limit
        
        reports = await db.question_reports.find(filters)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)\
            .to_list(None)
        
        # Преобразование данных
        reports_out = [_serialize_report(r, include_ip=True) for r in reports]
        
        return success(
            data={
                "reports": reports_out,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            },
            message="Жалобы получены"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.REPORT_ERROR,
            message=f"Ошибка при получении жалоб админом: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.put("/admin/{report_id}", response_model=Dict[str, Any])
@rate_limit_ip("question_report_update", max_requests=30, window_seconds=300)  # 30 обновлений за 5 минут
async def update_report_admin(
    report_id: str,
    update_data: QuestionReportUpdate,
    request: Request = None,
    current_admin: dict = Depends(get_current_admin_user)
):
    """Обновление жалобы (админ)"""
    try:
        # Проверка существования
        report = await db.question_reports.find_one({"_id": report_id})
        if not report:
            raise HTTPException(status_code=404, detail="Жалоба не найдена")
        
        # Обновление
        update_doc = {
            "status": update_data.status.value,
            "updated_at": datetime.utcnow(),
            "reviewed_by": str(current_admin["_id"])
        }
        
        if update_data.admin_comment:
            update_doc["admin_comment"] = update_data.admin_comment
        
        await db.question_reports.update_one(
            {"_id": report_id},
            {"$set": update_doc}
        )
        
        logger.info(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.REPORT_UPDATE,
            message=f"Жалоба обновлена: ID {report_id}, админ {current_admin['_id']}, статус {update_data.status.value}"
        )
        
        return success(
            data={"report_id": report_id, "status": update_data.status.value},
            message="Жалоба обновлена"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.REPORT_ERROR,
            message=f"Ошибка при обновлении жалобы: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/admin/stats", response_model=ReportStatsOut)
@rate_limit_ip("question_reports_stats", max_requests=20, window_seconds=60)  # 20 запросов в минуту
async def get_report_stats_admin(
    days: int = Query(30, ge=1, le=365),
    request: Request = None,
    current_admin: dict = Depends(get_current_admin_user)
):
    """Статистика жалоб (админ)"""
    try:
        # Date range
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Основная статистика
        total_reports = await db.question_reports.count_documents({
            "created_at": {"$gte": start_date}
        })
        
        pending_reports = await db.question_reports.count_documents({
            "created_at": {"$gte": start_date},
            "status": "sending"
        })
        
        resolved_reports = await db.question_reports.count_documents({
            "created_at": {"$gte": start_date},
            "status": {"$in": ["resolved", "rejected"]}
        })
        
        # Статистика по типам
        pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {"_id": "$report_type", "count": {"$sum": 1}}}
        ]
        
        type_stats = await db.question_reports.aggregate(pipeline).to_list(None)
        reports_by_type = {item["_id"]: item["count"] for item in type_stats}
        
        # Последние жалобы
        recent_reports = await db.question_reports.find()\
            .sort("created_at", -1)\
            .limit(10)\
            .to_list(None)
        
        recent_reports_out = [_serialize_report(r, trim_description=True) for r in recent_reports]
        
        return ReportStatsOut(
            total_reports=total_reports,
            pending_reports=pending_reports,
            resolved_reports=resolved_reports,
            reports_by_type=reports_by_type,
            recent_reports=recent_reports_out
        )
        
    except Exception as e:
        logger.error(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.REPORT_ERROR,
            message=f"Ошибка при получении статистики: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


def _serialize_report(report: dict, *, include_ip: bool = False, trim_description: bool = False) -> Dict[str, Any]:
    """Преобразует документ MongoDB в безопасный для ответа словарь."""
    description = report.get("description", "")
    if trim_description and len(description) > 100:
        description = description[:100] + "..."

    data = {
        "id": str(report.get("_id")),
        "lobby_id": report.get("lobby_id"),
        "question_id": report.get("question_id"),
        "user_id": report.get("user_id"),
        "report_type": report.get("report_type"),
        "description": description,
        "status": report.get("status"),
        "created_at": report.get("created_at"),
        "updated_at": report.get("updated_at"),
        "admin_comment": report.get("admin_comment"),
    }

    if include_ip:
        data["ip_address"] = report.get("ip_address")

    return data 