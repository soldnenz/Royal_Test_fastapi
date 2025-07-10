import os
import random
import string
from datetime import datetime
from typing import List
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.encoders import jsonable_encoder
from dotenv import load_dotenv
import json
from app.schemas.test_schemas import (
    QuestionCreate,
    QuestionOut,
    QuestionEdit,
    QuestionDelete,
    MultilingualText
)
from app.admin.permissions import get_current_admin_user
from app.db.database import get_database
from app.core.media_manager import media_manager
import base64
from app.core.config import settings
from app.core.response import success
from app.logging import get_logger, LogSection, LogSubsection
import time
from app.rate_limit import rate_limit_ip
from fastapi import Request


load_dotenv()

router = APIRouter()

ALLOWED_TYPES = settings.MEDIA_ALLOWED_TYPES
MAX_FILE_SIZE_MB = settings.MEDIA_MAX_FILE_SIZE_MB  # Используем настройку из конфига

logger = get_logger(__name__)

def generate_uid(length: int = 10) -> str:
    """
    Генерирует уникальный идентификатор – строку из случайных цифр заданной длины.
    """
    return ''.join(random.choices(string.digits, k=length))

def generate_safe_filename(original_filename: str, file_extension: str = None) -> str:
    """
    Генерирует безопасное ASCII имя файла из случайных символов
    """
    # Генерируем случайную строку из 8 символов (цифры и буквы)
    random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    # Определяем расширение файла
    if not file_extension:
        if '.' in original_filename:
            file_extension = original_filename.split('.')[-1].lower()
            # Проверяем, что расширение содержит только ASCII символы
            try:
                file_extension.encode('ascii')
            except UnicodeEncodeError:
                file_extension = 'bin'  # Используем безопасное расширение
        else:
            file_extension = 'bin'
    
    # Ограничиваем длину расширения для безопасности
    if len(file_extension) > 10:
        file_extension = 'bin'
    
    return f"{random_name}.{file_extension}"

@router.post("/", response_model=QuestionOut)
@rate_limit_ip("test_question_create", max_requests=5, window_seconds=120)
async def create_question(
    request: Request,
    question_data_str: str = Form(...),
    file: UploadFile = File(None),
    after_answer_file: UploadFile = File(None),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Создание вопроса с защитой:
      - Парсит входящую JSON-строку по схеме QuestionCreate.
      - Проверяет, что пользователь имеет достаточные права (админ или создатель тестов).
      - Валидирует MIME‑тип и размер файла, если он передан.
      - Генерирует уникальный 10-значный uid.
      - Сохраняет медиафайлы через MediaManager (если переданы) с обработкой ошибок.
      - Формирует варианты ответа с метками (A, B, ...).
      - Возвращает созданный вопрос с преобразованием ObjectId в строку.
    """
    # Защищённый парсинг входных данных
    try:
        question_data = QuestionCreate.parse_raw(question_data_str)
    except Exception as e:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Ошибка парсинга JSON при создании вопроса от пользователя {current_user.get('iin', 'неизвестен')}: {str(e)}"
        )
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга JSON: {e}")

    # Проверка прав доступа (требуется роль "admin" или "tests_creator")
    if not current_user or current_user.get("role") not in ["admin", "tests_creator"]:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка создания вопроса от пользователя без прав: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён. Требуется роль администратора или создателя тестов.")

    # Проверка наличия обязательных полей у пользователя
    if "full_name" not in current_user or "iin" not in current_user:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Пользователь с неполными данными пытался создать вопрос: {current_user}"
        )
        raise HTTPException(status_code=400, detail="Данные пользователя неполные.")

    uid = generate_uid(10)
    created_by_name = current_user["full_name"]
    created_by_iin = current_user["iin"]
    
    logger.info(
        section=LogSection.TEST,
        subsection=LogSubsection.TEST.QUESTION_CREATE,
        message=f"Пользователь {created_by_name} (IIN: {created_by_iin}) начинает создание вопроса с UID {uid} - валидация данных пройдена"
    )

    # Обработка основного медиафайла
    media_file_id = None
    media_filename = None
    if file:
        # Проверка MIME типа
        if file.content_type not in ALLOWED_TYPES:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Отклонён недопустимый тип основного файла {file.content_type} от пользователя {created_by_iin}"
            )
            raise HTTPException(status_code=400, detail=f"Недопустимый тип файла: {file.content_type}")
        # Проверка размера файла
        if file.size and file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Отклонён слишком большой основной файл {file.size} байт от пользователя {created_by_iin} (лимит: {MAX_FILE_SIZE_MB} МБ)"
            )
            raise HTTPException(status_code=400, detail=f"Превышен допустимый размер файла (макс. {MAX_FILE_SIZE_MB} МБ)")
        try:
            # Создаем информацию о создателе для MediaManager
            created_by = {
                "full_name": created_by_name,
                "iin": created_by_iin,
                "role": current_user.get("role", "admin")
            }
            
            # Сохраняем основной медиафайл через MediaManager
            media_result = await media_manager.save_media_file(file, db, created_by)
            media_file_id = media_result["id"]
            media_filename = file.filename
            
            # Проверяем, был ли это дубликат
            if media_result.get("is_duplicate"):
                logger.info(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.UPLOAD,
                    message=f"Использован существующий медиафайл {media_filename} (ID: {media_file_id}) для вопроса {uid} пользователем {created_by_iin} (дубликат)"
                )
            else:
                logger.info(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.UPLOAD,
                    message=f"Успешно загружен основной медиафайл {media_filename} (ID: {media_file_id}) для вопроса {uid} пользователем {created_by_iin}"
                )
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка сохранения основного медиафайла для вопроса {uid} пользователем {created_by_iin}: {str(e)}"
            )
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {e}")

    # Обработка дополнительного медиафайла (после ответа)
    after_answer_media_file_id = None
    after_answer_media_filename = None
    if after_answer_file:
        # Проверка MIME типа
        if after_answer_file.content_type not in ALLOWED_TYPES:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Отклонён недопустимый тип дополнительного файла {after_answer_file.content_type} от пользователя {created_by_iin}"
            )
            raise HTTPException(status_code=400, detail=f"Недопустимый тип дополнительного файла: {after_answer_file.content_type}")
        # Проверка размера файла
        if after_answer_file.size and after_answer_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            logger.warning(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.VALIDATION,
                message=f"Отклонён слишком большой дополнительный файл {after_answer_file.size} байт от пользователя {created_by_iin} (лимит: {MAX_FILE_SIZE_MB} МБ)"
            )
            raise HTTPException(status_code=400, detail=f"Превышен допустимый размер дополнительного файла (макс. {MAX_FILE_SIZE_MB} МБ)")
        try:
            # Создаем информацию о создателе для MediaManager
            created_by = {
                "full_name": created_by_name,
                "iin": created_by_iin,
                "role": current_user.get("role", "admin")
            }
            
            # Сохраняем дополнительный медиафайл через MediaManager
            after_answer_media_result = await media_manager.save_media_file(after_answer_file, db, created_by)
            after_answer_media_file_id = after_answer_media_result["id"]
            after_answer_media_filename = after_answer_file.filename
            
            # Проверяем, был ли это дубликат
            if after_answer_media_result.get("is_duplicate"):
                logger.info(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.UPLOAD,
                    message=f"Использован существующий дополнительный медиафайл {after_answer_media_filename} (ID: {after_answer_media_file_id}) для вопроса {uid} пользователем {created_by_iin} (дубликат)"
                )
            else:
                logger.info(
                    section=LogSection.FILES,
                    subsection=LogSubsection.FILES.UPLOAD,
                    message=f"Успешно загружен дополнительный медиафайл {after_answer_media_filename} (ID: {after_answer_media_file_id}) для вопроса {uid} пользователем {created_by_iin}"
                )
        except Exception as e:
            # Если произошла ошибка при сохранении дополнительного файла, но основной был сохранен,
            # нужно удалить основной файл, чтобы не создавать "мусор" в MediaManager
            if media_file_id:
                try:
                    await media_manager.delete_media_file(str(media_file_id), db)
                    logger.error(
                        section=LogSection.FILES,
                        subsection=LogSubsection.FILES.DELETE,
                        message=f"Удалён основной медиафайл {media_file_id} из-за ошибки сохранения дополнительного файла"
                    )
                except Exception:
                    pass  # Игнорируем ошибку при удалении
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка сохранения дополнительного медиафайла для вопроса {uid} пользователем {created_by_iin}: {str(e)}"
            )
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения дополнительного файла: {e}")

    # Формирование вариантов ответа с метками (A, B, C, …)
    try:
        options_with_labels = [
            {"label": string.ascii_uppercase[i], "text": opt.text.dict()}
            for i, opt in enumerate(question_data.options)
        ]
        correct_label = string.ascii_uppercase[question_data.correct_index]
    except Exception as e:
        # Если произошла ошибка, нужно удалить сохраненные медиафайлы
        if media_file_id:
            try:
                await media_manager.delete_media_file(str(media_file_id), db)
            except Exception:
                pass
        if after_answer_media_file_id:
            try:
                await media_manager.delete_media_file(str(after_answer_media_file_id), db)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=f"Ошибка формирования вариантов ответа: {e}")

    # Подготовка объяснения
    explanation = question_data.explanation.dict() if question_data.explanation else {
        "ru": "данный вопрос без объяснения",
        "kz": "бұл сұрақтың түсіндірмесі жоқ",
        "en": "this question has no explanation"
    }

    question_dict = {
        "question_text": question_data.question_text.dict(),
        "options": options_with_labels,
        "correct_label": correct_label,
        "categories": question_data.categories,
        "pdd_section_uids": question_data.pdd_section_uids,
        "created_by_name": created_by_name,
        "created_by_iin": created_by_iin,
        "uid": uid,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": None,
        "deleted": False,
        "deleted_by": None,
        "deleted_at": None,
        "media_file_id": str(media_file_id) if media_file_id else None,
        "media_filename": media_filename,
        "after_answer_media_file_id": str(after_answer_media_file_id) if after_answer_media_file_id else None,
        "after_answer_media_id": str(after_answer_media_file_id) if after_answer_media_file_id else None,  # Добавляем для совместимости
        "after_answer_media_filename": after_answer_media_filename,
        "explanation": explanation,
        # Добавляем флаги наличия медиа для фронтенда
        "has_media": bool(media_file_id and media_filename),
        "has_after_answer_media": bool(after_answer_media_file_id and after_answer_media_filename),
        "has_after_media": bool(after_answer_media_file_id and after_answer_media_filename)  # Добавляем для совместимости
    }

    try:
        result = await db.questions.insert_one(question_dict)
        question_dict["id"] = str(result.inserted_id)
        
        logger.info(
            section=LogSection.TEST,
            subsection=LogSubsection.TEST.QUESTION_CREATE,
            message=f"Успешно создан вопрос {uid} (ID: {result.inserted_id}) пользователем {created_by_name} (IIN: {created_by_iin}) с {len(question_data.options)} вариантами ответа"
        )
    except Exception as e:
        # Если произошла ошибка при записи в БД, удаляем сохраненные медиафайлы
        if media_file_id:
            try:
                await media_manager.delete_media_file(str(media_file_id), db)
            except Exception:
                pass
        if after_answer_media_file_id:
            try:
                await media_manager.delete_media_file(str(after_answer_media_file_id), db)
            except Exception:
                pass
        logger.error(
            section=LogSection.DATABASE,
            subsection=LogSubsection.DATABASE.ERROR,
            message=f"Критическая ошибка при записи вопроса {uid} в базу данных пользователем {created_by_iin}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Ошибка записи в базу: {e}")

    return success(data=jsonable_encoder(question_dict, custom_encoder={ObjectId: str}))


@router.put("/", response_model=dict)
@rate_limit_ip("test_question_edit", max_requests=15, window_seconds=300)
async def edit_question(
    request: Request,
    payload: str = Form(...),      # Принимаем payload как строку
    new_file: UploadFile = File(None),
    new_after_answer_file: UploadFile = File(None),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    # Разбираем JSON-строку в объект QuestionEdit
    try:
        payload_data = QuestionEdit.parse_raw(payload)
    except Exception as e:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Ошибка парсинга JSON при редактировании вопроса от пользователя {current_user.get('iin', 'неизвестен')}: {str(e)}"
        )
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга JSON: {e}")
    
    logger.info(
        section=LogSection.TEST,
        subsection=LogSubsection.TEST.QUESTION_UPDATE,
        message=f"Пользователь {current_user['full_name']} (IIN: {current_user['iin']}) начинает редактирование вопроса {payload_data.question_id}"
    )

    update_fields = {}
    labels = list(string.ascii_uppercase)

    if not current_user or current_user.get("role") not in ["admin", "tests_creator"]:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка редактирования вопроса от пользователя без прав: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён. Требуется роль администратора или создателя тестов.")

    # Проверка наличия обязательных данных пользователя
    if "full_name" not in current_user or "iin" not in current_user:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Пользователь с неполными данными пытался отредактировать вопрос: {current_user}"
        )
        raise HTTPException(status_code=400, detail="Данные пользователя неполные.")

    if payload_data.new_question_text:
        update_fields["question_text"] = payload_data.new_question_text.dict()

    if payload_data.new_pdd_section_uids:
        update_fields["pdd_section_uids"] = payload_data.new_pdd_section_uids

    if payload_data.new_options:
        try:
            new_options = [
                {"label": labels[i], "text": opt.text.dict()}
                for i, opt in enumerate(payload_data.new_options)
            ]
            update_fields["options"] = new_options
            if payload_data.new_correct_index is not None:
                if payload_data.new_correct_index >= len(payload_data.new_options):
                    raise HTTPException(status_code=400, detail="Неверный индекс правильного ответа")
                update_fields["correct_label"] = labels[payload_data.new_correct_index]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка обработки новых вариантов: {e}")

    if payload_data.new_categories:
        update_fields["categories"] = payload_data.new_categories

    if payload_data.new_explanation:
        update_fields["explanation"] = payload_data.new_explanation.dict()

    # Получаем текущие данные вопроса
    existing_question = await db.questions.find_one({"uid": payload_data.question_id})
    if not existing_question:
        logger.warning(
            section=LogSection.TEST,
            subsection=LogSubsection.TEST.VALIDATION,
            message=f"Пользователь {current_user['iin']} пытался отредактировать несуществующий вопрос: {payload_data.question_id}"
        )
        raise HTTPException(status_code=404, detail="Вопрос не найден")

    # Если пользователь решил удалить основное медиа, удаляем соответствующие поля
    if payload_data.remove_media:
        try:
            if existing_question.get("media_file_id"):
                media_file_id = existing_question["media_file_id"]
                # Проверяем существует ли файл перед удалением
                file_exists = await media_manager.get_media_file(media_file_id, db)
                if file_exists:
                    await media_manager.delete_media_file(media_file_id, db)
                    logger.info(
                        section=LogSection.FILES,
                        subsection=LogSubsection.FILES.DELETE,
                        message=f"Удалён основной медиафайл {media_file_id} по запросу пользователя {current_user['iin']}"
                    )
                else:
                    logger.warning(
                        section=LogSection.FILES,
                        subsection=LogSubsection.FILES.ERROR,
                        message=f"Медиафайл {media_file_id} не найден при попытке удаления по запросу пользователя {current_user['iin']}"
                    )
                update_fields["media_file_id"] = None
                update_fields["media_filename"] = None
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка удаления основного медиафайла {media_file_id}: {str(e)}"
            )
            update_fields["media_file_id"] = None
            update_fields["media_filename"] = None

    # Если пользователь решил удалить дополнительное медиа (после ответа), удаляем соответствующие поля
    if payload_data.remove_after_answer_media:
        try:
            if existing_question.get("after_answer_media_file_id"):
                after_answer_media_file_id = existing_question["after_answer_media_file_id"]
                # Проверяем существует ли файл перед удалением
                file_exists = await media_manager.get_media_file(after_answer_media_file_id, db)
                if file_exists:
                    await media_manager.delete_media_file(after_answer_media_file_id, db)
                else:
                    logger.warning(
                        section=LogSection.FILES,
                        subsection=LogSubsection.FILES.ERROR,
                        message=f"Файл {after_answer_media_file_id} не найден при попытке удаления"
                    )
                update_fields["after_answer_media_file_id"] = None
                update_fields["after_answer_media_filename"] = None
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка удаления дополнительного медиафайла {after_answer_media_file_id}: {str(e)}"
            )
            update_fields["after_answer_media_file_id"] = None
            update_fields["after_answer_media_filename"] = None

    # Если выбран новый основной файл и заменяем старое медиа, обновляем медиа
    if new_file:
        if payload_data.replace_media:
            # Удаляем предыдущий основной медиа файл, если он существует
            if existing_question.get("media_file_id"):
                try:
                    media_file_id = existing_question["media_file_id"]
                    # Проверяем существует ли файл перед удалением
                    file_exists = await media_manager.get_media_file(media_file_id, db)
                    if file_exists:
                        await media_manager.delete_media_file(media_file_id, db)
                    else:
                        logger.warning(
                            section=LogSection.FILES,
                            subsection=LogSubsection.FILES.ERROR,
                            message=f"Файл {media_file_id} не найден при попытке замены"
                        )
                except Exception as e:
                    logger.error(
                        section=LogSection.FILES,
                        subsection=LogSubsection.FILES.ERROR,
                        message=f"Ошибка удаления старого основного медиафайла {media_file_id}: {str(e)}"
                    )
        elif existing_question.get("media_file_id"):
            # Если файл уже существует и replace_media=false - не заменяем
            raise HTTPException(status_code=400, detail="Основной медиафайл уже существует. Для замены укажите replace_media=true")

        # Проверяем новый основной файл на соответствие допустимым типам и размерам
        if new_file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Недопустимый тип основного файла: {new_file.content_type}")
        if new_file.size and new_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"Превышен допустимый размер основного файла (макс. {MAX_FILE_SIZE_MB} МБ)")
        try:
            # Создаем информацию о создателе для MediaManager
            created_by = {
                "full_name": current_user["full_name"],
                "iin": current_user["iin"],
                "role": current_user.get("role", "admin")
            }
            
            # Сохраняем новый основной файл через MediaManager
            media_result = await media_manager.save_media_file(new_file, db, created_by)
            file_id = media_result["id"]
            update_fields["media_file_id"] = str(file_id)
            update_fields["media_filename"] = new_file.filename
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения нового основного файла: {e}")

    # Если выбран новый дополнительный файл и заменяем старое дополнительное медиа, обновляем его
    if new_after_answer_file:
        if payload_data.replace_after_answer_media:
            # Удаляем предыдущий дополнительный медиа файл, если он существует
            if existing_question.get("after_answer_media_file_id"):
                try:
                    after_answer_media_file_id = existing_question["after_answer_media_file_id"]
                    # Проверяем существует ли файл перед удалением
                    file_exists = await media_manager.get_media_file(after_answer_media_file_id, db)
                    if file_exists:
                        await media_manager.delete_media_file(after_answer_media_file_id, db)
                    else:
                        logger.warning(
                            section=LogSection.FILES,
                            subsection=LogSubsection.FILES.ERROR,
                            message=f"Файл {after_answer_media_file_id} не найден при попытке замены"
                        )
                except Exception as e:
                    logger.error(
                        section=LogSection.FILES,
                        subsection=LogSubsection.FILES.ERROR,
                        message=f"Ошибка удаления старого дополнительного медиафайла {after_answer_media_file_id}: {str(e)}"
                    )
        elif existing_question.get("after_answer_media_file_id"):
            # Если дополнительный файл уже существует и replace_after_answer_media=false - не заменяем
            raise HTTPException(status_code=400, detail="Дополнительный медиафайл уже существует. Для замены укажите replace_after_answer_media=true")

        # Проверяем новый дополнительный файл на соответствие допустимым типам и размерам
        if new_after_answer_file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Недопустимый тип дополнительного файла: {new_after_answer_file.content_type}")
        if new_after_answer_file.size and new_after_answer_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"Превышен допустимый размер дополнительного файла (макс. {MAX_FILE_SIZE_MB} МБ)")
        try:
            # Создаем информацию о создателе для MediaManager
            created_by = {
                "full_name": current_user["full_name"],
                "iin": current_user["iin"],
                "role": current_user.get("role", "admin")
            }
            
            # Сохраняем новый дополнительный файл через MediaManager
            after_answer_media_result = await media_manager.save_media_file(new_after_answer_file, db, created_by)
            file_id = after_answer_media_result["id"]
            update_fields["after_answer_media_file_id"] = str(file_id)
            update_fields["after_answer_media_filename"] = new_after_answer_file.filename
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения нового дополнительного файла: {e}")

    # Пересчитываем флаги наличия медиа перед обновлением
    # Это исправит несоответствия, если медиа было добавлено/удалено при редактировании
    
    # Определяем конечное состояние медиа полей
    final_media_id = update_fields.get("media_file_id", existing_question.get("media_file_id"))
    final_media_filename = update_fields.get("media_filename", existing_question.get("media_filename"))
    final_after_media_id = update_fields.get("after_answer_media_file_id", existing_question.get("after_answer_media_file_id"))
    final_after_media_filename = update_fields.get("after_answer_media_filename", existing_question.get("after_answer_media_filename"))

    # Обновляем флаги в словаре update_fields
    update_fields["has_media"] = bool(final_media_id and final_media_filename)
    update_fields["has_after_answer_media"] = bool(final_after_media_id and final_after_media_filename)
    update_fields["has_after_media"] = update_fields["has_after_answer_media"]  # Для обратной совместимости

    update_fields["updated_at"] = datetime.utcnow()
    update_fields["modified_by"] = current_user["full_name"]

    # Используем пользовательский uid для поиска документа
    result = await db.questions.update_one(
        {"uid": payload_data.question_id},
        {"$set": update_fields}
    )
    if result.modified_count == 0:
        logger.error(
            section=LogSection.DATABASE,
            subsection=LogSubsection.DATABASE.ERROR,
            message=f"Не удалось обновить вопрос {payload_data.question_id} в базе данных - операция не внесла изменений (пользователь: {current_user['iin']})"
        )
        raise HTTPException(status_code=400, detail="Ошибка при обновлении вопроса")
    
    logger.info(
        section=LogSection.TEST,
        subsection=LogSubsection.TEST.QUESTION_UPDATE,
        message=f"Успешно обновлён вопрос {payload_data.question_id} пользователем {current_user['full_name']} (IIN: {current_user['iin']})"
    )
    
    # Получаем обновленные данные вопроса
    updated_question = await db.questions.find_one({"uid": payload_data.question_id})
    if updated_question:
        updated_question["id"] = str(updated_question["_id"])
        del updated_question["_id"]
        
        # Конвертируем ID в строки
        if updated_question.get("media_file_id"):
            updated_question["media_file_id"] = str(updated_question["media_file_id"])
        if updated_question.get("after_answer_media_file_id"):
            updated_question["after_answer_media_file_id"] = str(updated_question["after_answer_media_file_id"])
            updated_question["after_answer_media_id"] = str(updated_question["after_answer_media_file_id"])
        
        # Добавляем информацию о наличии медиа
        updated_question["has_media"] = bool(updated_question.get("media_file_id") and updated_question.get("media_filename"))
        updated_question["has_after_answer_media"] = bool(updated_question.get("after_answer_media_file_id") and updated_question.get("after_answer_media_filename"))
        updated_question["has_after_media"] = updated_question["has_after_answer_media"]
        
        return success(data={"message": "Вопрос обновлён", "question": jsonable_encoder(updated_question)})
    
    return success(data={"message": "Вопрос обновлён"})

@router.delete("/", response_model=dict)
@rate_limit_ip("test_question_delete", max_requests=15, window_seconds=300)
async def delete_question(
    payload: QuestionDelete,
    request: Request,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Мягкое удаление вопроса:
      - Обновляет поля deleted, deleted_by и deleted_at.
      - Производит проверку корректности идентификатора.
      - Удаляет связанные медиафайлы через MediaManager.
    """
    # Используем данные текущего пользователя для deleted_by
    deleted_by = current_user.get("full_name", "Неизвестный пользователь")
    logger.info(
        section=LogSection.TEST,
        subsection=LogSubsection.TEST.QUESTION_DELETE,
        message=f"Получен запрос на удаление вопроса {payload.question_id} от пользователя {deleted_by} (IIN: {current_user.get('iin', 'неизвестен')})"
    )
    
    if not current_user or current_user.get("role") not in ["admin", "tests_creator"]:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка удаления вопроса от пользователя без прав: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён. Требуется роль администратора или создателя тестов.")

    # Проверка наличия обязательных полей у пользователя
    if "full_name" not in current_user or "iin" not in current_user:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.VALIDATION,
            message=f"Пользователь с неполными данными пытался удалить вопрос: {current_user}"
        )
        raise HTTPException(status_code=400, detail="Данные пользователя неполные.")

    # Сначала ищем вопрос по uid (предпочтительный формат)
    existing_question = await db.questions.find_one({"uid": payload.question_id})
    
    # Если не нашли, пробуем найти по ObjectId
    if not existing_question:
        try:
            question_obj_id = ObjectId(payload.question_id)
            existing_question = await db.questions.find_one({"_id": question_obj_id})
            logger.info(
                section=LogSection.TEST,
                subsection=LogSubsection.TEST.QUESTION_DELETE,
                message=f"Найден вопрос по ObjectId: {question_obj_id}"
            )
        except Exception as e:
            logger.warning(
                section=LogSection.SECURITY,
                subsection=LogSubsection.SECURITY.VALIDATION,
                message=f"Неверный формат идентификатора вопроса {payload.question_id} от пользователя {current_user['iin']}: {str(e)}"
            )
            raise HTTPException(status_code=400, detail=f"Неверный формат идентификатора: {e}")
    else:
        logger.info(
            section=LogSection.TEST,
            subsection=LogSubsection.TEST.QUESTION_DELETE,
            message=f"Найден вопрос по UID: {payload.question_id}"
        )
    
    if not existing_question:
        logger.warning(
            section=LogSection.TEST,
            subsection=LogSubsection.TEST.VALIDATION,
            message=f"Вопрос {payload.question_id} не найден для удаления пользователем {current_user['iin']}"
        )
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    
    # Получаем информацию о наличии медиафайлов
    has_main_media = bool(existing_question.get("media_file_id"))
    has_additional_media = bool(existing_question.get("after_answer_media_file_id"))
    
    logger.info(
        section=LogSection.TEST,
        subsection=LogSubsection.TEST.MEDIA_PROCESSING,
        message=f"Вопрос {payload.question_id} содержит основной медиафайл: {has_main_media}, дополнительный медиафайл: {has_additional_media}"
    )
    
    # Удаляем медиа-файлы из GridFS
    deleted_main_media = False
    deleted_additional_media = False
    
    if has_main_media:
        try:
            await media_manager.delete_media_file(existing_question["media_file_id"], db)
            deleted_main_media = True
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.DELETE,
                message=f"Успешно удалён основной медиафайл {existing_question['media_file_id']} при удалении вопроса {payload.question_id}"
            )
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка удаления основного медиафайла {existing_question['media_file_id']}: {str(e)}"
            )
    
    if has_additional_media:
        try:
            await media_manager.delete_media_file(existing_question["after_answer_media_file_id"], db)
            deleted_additional_media = True
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.DELETE,
                message=f"Успешно удалён дополнительный медиафайл {existing_question['after_answer_media_file_id']} при удалении вопроса {payload.question_id}"
            )
        except Exception as e:
            logger.error(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.ERROR,
                message=f"Ошибка удаления дополнительного медиафайла {existing_question['after_answer_media_file_id']}: {str(e)}"
            )

    # Обновляем флаги удаления в документе
    update_fields = {
        "deleted": True,
        "deleted_by": deleted_by,
        "deleted_at": datetime.utcnow()
    }
    
    # Определяем ID для обновления (используем _id если он есть, иначе uid)
    if "_id" in existing_question:
        result = await db.questions.update_one(
            {"_id": existing_question["_id"]},
            {"$set": update_fields}
        )
    else:
        result = await db.questions.update_one(
            {"uid": existing_question["uid"]},
            {"$set": update_fields}
        )
    
    if result.modified_count == 0:
        logger.error(
            section=LogSection.DATABASE,
            subsection=LogSubsection.DATABASE.ERROR,
            message=f"Не удалось обновить статус удаления вопроса {payload.question_id} в базе данных"
        )
        raise HTTPException(status_code=400, detail="Ошибка при удалении вопроса")
    
    logger.info(
        section=LogSection.TEST,
        subsection=LogSubsection.TEST.QUESTION_DELETE,
        message=f"Вопрос {payload.question_id} успешно помечен как удалённый пользователем {deleted_by} (IIN: {current_user['iin']})"
    )
    
    # Формируем детальный ответ
    response_data = {
        "message": "Вопрос успешно удален",
        "question_id": existing_question.get("uid", str(existing_question.get("_id"))),
        "media_deleted": {
            "main_media": deleted_main_media,
            "additional_media": deleted_additional_media
        }
    }
    
    return success(data=response_data)

@router.get("/by_uid/{uid}", response_model=dict)
@rate_limit_ip("test_question_view", max_requests=100, window_seconds=60)
async def get_question_by_uid(
    uid: str,
    request: Request,
    current_user: dict = Depends(get_current_admin_user),
    db=Depends(get_database)
):
    start_time = time.time()
    
    if current_user["role"] not in {"admin", "moderator", "tests_creator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка получения вопроса от пользователя без прав: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # Stage 1: Database lookup
    db_start_time = time.time()
    question = await db.questions.find_one({"uid": uid, "deleted": False})
    db_time = time.time() - db_start_time
    logger.info(
        section=LogSection.API,
        subsection=LogSubsection.API.PERFORMANCE,
        message=f"Поиск вопроса {uid} в базе данных занял {db_time:.4f} секунд"
    )
    
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")

    # Stage 2: Processing question data
    processing_start_time = time.time()
    question["id"] = str(question["_id"])
    del question["_id"]

    # Convert media_file_id to string if it exists
    if question.get("media_file_id"):
        question["media_file_id"] = str(question["media_file_id"])
    if question.get("after_answer_media_file_id"):
        question["after_answer_media_file_id"] = str(question["after_answer_media_file_id"])
        # Добавляем совместимый ключ для фронтенда
        question["after_answer_media_id"] = str(question["after_answer_media_file_id"])

    # Добавляем флаги наличия медиа
    question["has_media"] = bool(question.get("media_file_id") and question.get("media_filename"))
    question["has_after_answer_media"] = bool(question.get("after_answer_media_file_id") and question.get("after_answer_media_filename"))
    question["has_after_media"] = question["has_after_answer_media"]  # Для совместимости
    
    processing_time = time.time() - processing_start_time
    logger.info(
        section=LogSection.API,
        subsection=LogSubsection.API.PERFORMANCE,
        message=f"Обработка базовых данных вопроса {uid} заняла {processing_time:.4f} секунд"
    )

    # Stage 3: Media file IDs are already available, no need to load base64 data
    # Frontend will use direct URLs to /api/tests/media/{media_id}
    
    # Stage 3: Multilingual text processing
    ml_start_time = time.time()
    # Преобразование данных из БД к модели MultilingualText
    # Если данные старые (до обновления) и хранятся как строка
    if isinstance(question.get("question_text"), str):
        question["question_text"] = {
            "ru": question["question_text"],
            "kz": question["question_text"], 
            "en": question["question_text"]
        }
    
    if isinstance(question.get("explanation"), str):
        question["explanation"] = {
            "ru": question["explanation"],
            "kz": question["explanation"],
            "en": question["explanation"]
        }
    
    # Обработка вариантов ответа
    if "options" in question:
        for option in question["options"]:
            if isinstance(option.get("text"), str):
                option["text"] = {
                    "ru": option["text"],
                    "kz": option["text"],
                    "en": option["text"]
                }
    
    ml_time = time.time() - ml_start_time
    logger.info(
        section=LogSection.API,
        subsection=LogSubsection.API.PERFORMANCE,
        message=f"Обработка многоязычного текста для вопроса {uid} заняла {ml_time:.4f} секунд"
    )

    total_time = time.time() - start_time
    logger.info(
        section=LogSection.API,
        subsection=LogSubsection.API.PERFORMANCE,
        message=f"Общее время обработки запроса вопроса {uid}: {total_time:.4f} секунд"
    )

    return success(data=jsonable_encoder(question))

@router.get("/all", response_model=list[dict])
@rate_limit_ip("test_questions_list", max_requests=120, window_seconds=30)
async def get_all_questions(
    request: Request,
    current_user: dict = Depends(get_current_admin_user),
    db=Depends(get_database)
):
    """
    Возвращает все активные вопросы (без base64-медиа),
    но с информацией о наличии медиа.
    Доступ для admin, moderator и tests_creator.
    """
    if "role" not in current_user or current_user["role"] not in {"admin", "moderator", "tests_creator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка получения списка вопросов от пользователя без прав: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    logger.info(
        section=LogSection.TEST,
        subsection=LogSubsection.TEST.QUESTION_LOAD,
        message=f"Пользователь {current_user.get('full_name', 'неизвестен')} (IIN: {current_user.get('iin', 'неизвестен')}) запрашивает список всех вопросов"
    )

    cursor = db.questions.find({"deleted": False})
    questions = []
    async for q in cursor:
        q["id"] = str(q["_id"])
        del q["_id"]
        # Convert media_file_id to string if it exists
        if q.get("media_file_id"):
            q["media_file_id"] = str(q["media_file_id"])
        if q.get("after_answer_media_file_id"):
            q["after_answer_media_file_id"] = str(q["after_answer_media_file_id"])
            # Добавляем дополнительный ключ для совместимости
            q["after_answer_media_id"] = str(q["after_answer_media_file_id"])
            
        # Добавляем признаки наличия медиа
        q["has_media"] = bool(q.get("media_file_id") and q.get("media_filename"))
        q["has_after_answer_media"] = bool(q.get("after_answer_media_file_id") and q.get("after_answer_media_filename"))
        # Добавляем дополнительный ключ для совместимости
        q["has_after_media"] = q["has_after_answer_media"]

        # Преобразование данных из БД к модели MultilingualText
        # Если данные старые (до обновления) и хранятся как строка
        if isinstance(q.get("question_text"), str):
            q["question_text"] = {
                "ru": q["question_text"],
                "kz": q["question_text"], 
                "en": q["question_text"]
            }
        
        if isinstance(q.get("explanation"), str):
            q["explanation"] = {
                "ru": q["explanation"],
                "kz": q["explanation"],
                "en": q["explanation"]
            }
        
        # Обработка вариантов ответа
        if "options" in q:
            for option in q["options"]:
                if isinstance(option.get("text"), str):
                    option["text"] = {
                        "ru": option["text"],
                        "kz": option["text"],
                        "en": option["text"]
                    }

        # Очищаем тяжелые поля, но оставляем ID медиафайлов для фронтенда
        q.pop("media_filename", None)
        q.pop("after_answer_media_filename", None)
        questions.append(q)

    logger.info(
        section=LogSection.TEST,
        subsection=LogSubsection.TEST.QUESTION_LOAD,
        message=f"Возвращено {len(questions)} вопросов пользователю {current_user.get('full_name', 'неизвестен')} (IIN: {current_user.get('iin', 'неизвестен')})"
    )

    return success(data=jsonable_encoder(questions))

@router.get("/media/{media_id}", response_model=dict)
@rate_limit_ip("media_download", max_requests=100, window_seconds=60)
async def get_media_by_id(
    media_id: str,
    request: Request,
    current_user: dict = Depends(get_current_admin_user),
    db=Depends(get_database)
):
    """
    Получение медиафайла по ID с поддержкой потоковой передачи.
    Доступ только для администраторов.
    """
    if current_user["role"] not in {"admin", "moderator", "tests_creator"}:
        logger.warning(
            section=LogSection.SECURITY,
            subsection=LogSubsection.SECURITY.ACCESS_DENIED,
            message=f"Попытка получения медиафайла от пользователя без прав: {current_user.get('iin', 'неизвестен')} (роль: {current_user.get('role', 'неизвестна')})"
        )
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    logger.info(
        section=LogSection.FILES,
        subsection=LogSubsection.FILES.ACCESS,
        message=f"Пользователь {current_user.get('full_name', 'неизвестен')} (IIN: {current_user.get('iin', 'неизвестен')}) запрашивает медиафайл {media_id}"
    )

    try:
        # Получаем информацию о файле через MediaManager
        file_info = await media_manager.get_media_file(media_id, db)
        if not file_info:
            raise HTTPException(status_code=404, detail="Медиафайл не найден")

        # Файл будет отдан напрямую через nginx, загружать не нужно
        
        # Определяем тип контента
        content_type = file_info.get("content_type", "application/octet-stream")
        
        # Генерируем безопасное случайное имя файла для HTTP заголовка
        filename = file_info.get('original_filename', 'media')
        try:
            # Попытка закодировать имя файла в latin-1
            filename.encode('latin-1')
            safe_filename = filename  # Если успешно - оставляем оригинальное имя
        except UnicodeEncodeError:
            # Только если есть кириллица - генерируем случайное имя
            safe_filename = generate_safe_filename(filename)
            logger.info(
                section=LogSection.FILES,
                subsection=LogSubsection.FILES.SECURITY,
                message=f"Файл с кириллическим именем переименован для безопасности: {filename} → {safe_filename}"
            )
        
        content_disposition = f"inline; filename={safe_filename}"
        
        logger.info(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.DOWNLOAD,
            message=f"Успешно предоставлен медиафайл {media_id} ({content_type}, {file_info.get('file_size', 0)} байт) пользователю {current_user.get('iin', 'неизвестен')}"
        )
        
        # Используем X-Accel-Redirect для прямой отдачи файла через nginx
        return StreamingResponse(
            iter([]),  # Пустой итератор, так как nginx сам отдаст файл
            media_type=content_type,
            headers={
                "X-Accel-Redirect": f"/media/{file_info['relative_path']}",
                "Content-Type": content_type,
                "Content-Disposition": content_disposition,
                "Content-Length": str(file_info.get("file_size", 0))
            }
        )
    except Exception as e:
        logger.error(
            section=LogSection.FILES,
            subsection=LogSubsection.FILES.ERROR,
            message=f"Ошибка при получении медиафайла {media_id} пользователем {current_user.get('iin', 'неизвестен')}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Ошибка при получении медиафайла: {str(e)}")

@router.get("/test-rate-limit")
@rate_limit_ip("test_rate_limit", max_requests=3, window_seconds=30)
async def test_rate_limit(request: Request):
    """Тестовый эндпоинт для проверки рейт лимитов"""
    return {"message": "Rate limit test successful"}
