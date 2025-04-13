import os
import random
import string
from datetime import datetime
from typing import List
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from dotenv import load_dotenv
import json
from app.schemas.test_schemas import (
    QuestionCreate,
    QuestionOut,
    QuestionEdit,
    QuestionDelete
)
from app.admin.permissions import get_current_admin_user
from app.db.database import get_database
from app.core.gridfs_utils import save_media_to_gridfs, get_media_file, delete_media_file
import base64
from app.core.config import settings
from app.core.response import success


load_dotenv()

router = APIRouter()

ALLOWED_TYPES = settings.allowed_media_types
MAX_FILE_SIZE_MB = settings.max_file_size_mb

def generate_uid(length: int = 10) -> str:
    """
    Генерирует уникальный идентификатор – строку из случайных цифр заданной длины.
    """
    return ''.join(random.choices(string.digits, k=length))

@router.post("/", response_model=QuestionOut)
async def create_question(
    question_data_str: str = Form(...),
    file: UploadFile = File(None),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Создание вопроса с защитой:
      - Парсит входящую JSON-строку по схеме QuestionCreate.
      - Проверяет, что пользователь имеет достаточные права (например, роль "admin").
      - Валидирует MIME‑тип и размер файла, если он передан.
      - Генерирует уникальный 10-значный uid.
      - Сохраняет медиафайл в GridFS (если передан) с обработкой ошибок.
      - Формирует варианты ответа с метками (A, B, ...).
      - Возвращает созданный вопрос с преобразованием ObjectId в строку.
    """
    # Защищённый парсинг входных данных
    try:
        question_data = QuestionCreate.parse_raw(question_data_str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга JSON: {e}")

    # Проверка прав доступа (требуется роль "admin")
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён. Администратор требуется.")

    # Проверка наличия обязательных полей у пользователя
    if "full_name" not in current_user or "iin" not in current_user:
        raise HTTPException(status_code=400, detail="Данные пользователя неполные.")

    uid = generate_uid(10)
    created_by_name = current_user["full_name"]
    created_by_iin = current_user["iin"]

    media_file_id = None
    media_filename = None
    if file:
        # Проверка MIME типа
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Недопустимый тип файла: {file.content_type}")
        # Проверка размера файла
        if file.size and file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Превышен допустимый размер файла")
        try:
            media_file_id = await save_media_to_gridfs(file, db)
            media_filename = file.filename
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {e}")

    # Формирование вариантов ответа с метками (A, B, C, …)
    try:
        options_with_labels = [
            {"label": string.ascii_uppercase[i], "text": opt.text}
            for i, opt in enumerate(question_data.options)
        ]
        correct_label = string.ascii_uppercase[question_data.correct_index]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка формирования вариантов ответа: {e}")

    question_dict = {
        "question_text": question_data.question_text,
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
        "explanation": question_data.explanation or "данный вопрос без объяснения"
    }

    try:
        result = await db.questions.insert_one(question_dict)
        question_dict["id"] = str(result.inserted_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка записи в базу: {e}")

    return success(data=jsonable_encoder(question_dict, custom_encoder={ObjectId: str}))


@router.put("/", response_model=dict)
async def edit_question(
    payload: str = Form(...),      # Принимаем payload как строку
    new_file: UploadFile = File(None),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    # Разбираем JSON-строку в объект QuestionEdit
    try:
        payload_data = QuestionEdit.parse_raw(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга JSON: {e}")

    update_fields = {}
    labels = list(string.ascii_uppercase)

    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён. Администратор требуется.")

    # Проверка наличия обязательных данных пользователя
    if "full_name" not in current_user or "iin" not in current_user:
        raise HTTPException(status_code=400, detail="Данные пользователя неполные.")

    if payload_data.new_question_text:
        update_fields["question_text"] = payload_data.new_question_text

    if payload_data.new_pdd_section_uids:
        update_fields["pdd_section_uids"] = payload_data.new_pdd_section_uids

    if payload_data.new_options:
        try:
            new_options = [
                {"label": labels[i], "text": opt.text}
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
        update_fields["explanation"] = payload_data.new_explanation

    # Если пользователь решил удалить медиа, сбрасываем поля
    if payload_data.remove_media:
        try:
            # Получаем ID медиа-файла из базы данных
            existing_question = await db.questions.find_one({"uid": payload_data.question_id})
            if existing_question and existing_question.get("media_file_id"):
                await delete_media_file(existing_question["media_file_id"], db)
                update_fields["media_file_id"] = None
                update_fields["media_filename"] = None
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=f"Ошибка удаления медиа файла: {e}")

   # Если выбран новый файл и заменяем старое медиа, обновляем медиа
    if payload_data.replace_media and new_file:
        # Извлекаем документ вопроса по uid, чтобы проверить наличие предыдущего медиа
        existing_question = await db.questions.find_one({"uid": payload_data.question_id})
        if existing_question and existing_question.get("media_file_id"):
            try:
                # Удаляем предыдущий медиа файл
                await delete_media_file(existing_question["media_file_id"], db)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ошибка удаления старого медиа файла: {e}")

        # Далее проверяем новый файл на соответствие допустимым типам и размерам
        if new_file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Недопустимый тип файла: {new_file.content_type}")
        if new_file.size and new_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Превышен допустимый размер файла")
        try:
            # Сохраняем новый файл в GridFS
            file_id = await save_media_to_gridfs(new_file, db)
            update_fields["media_file_id"] = str(file_id)
            update_fields["media_filename"] = new_file.filename
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения нового файла: {e}")


    update_fields["updated_at"] = datetime.utcnow()
    update_fields["modified_by"] = current_user["full_name"]

    # Используем пользовательский uid для поиска документа
    result = await db.questions.update_one(
        {"uid": payload_data.question_id},
        {"$set": update_fields}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Ошибка при обновлении вопроса")
    return success(data={"message": "Вопрос обновлён"})

@router.delete("/", response_model=dict)
async def delete_question(
    payload: QuestionDelete,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_database)
):
    """
    Мягкое удаление вопроса:
      - Обновляет поля deleted, deleted_by и deleted_at.
      - Производит проверку корректности идентификатора.
    """
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён. Администратор требуется.")

    # Проверка наличия обязательных полей у пользователя
    if "full_name" not in current_user or "iin" not in current_user:
        raise HTTPException(status_code=400, detail="Данные пользователя неполные.")

    try:
        question_obj_id = ObjectId(payload.question_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Неверный формат идентификатора: {e}")

    # Получаем документ вопроса и проверяем наличие медиа-файла
    existing_question = await db.questions.find_one({"_id": question_obj_id})
    if existing_question and existing_question.get("media_file_id"):
        try:
            await delete_media_file(existing_question["media_file_id"], db)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=f"Ошибка удаления медиа файла: {e}")

    update_fields = {
        "deleted": True,
        "deleted_by": payload.deleted_by,
        "deleted_at": datetime.utcnow()
    }
    result = await db.questions.update_one(
        {"_id": question_obj_id},
        {"$set": update_fields}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    return success(data={"message": "Вопрос удалён"})

@router.get("/by_uid/{uid}", response_model=dict)
async def get_question_by_uid(
    uid: str,
    current_user: dict = Depends(get_current_admin_user),
    db=Depends(get_database)
):
    if current_user["role"] not in {"admin", "moderator"}:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    question = await db.questions.find_one({"uid": uid, "deleted": False})
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")

    question["id"] = str(question["_id"])
    del question["_id"]

    # Convert media_file_id to string if it exists
    if question.get("media_file_id"):
        question["media_file_id"] = str(question["media_file_id"])

    # Добавляем base64 медиафайл
    if question.get("media_file_id"):
        try:
            file_data = await get_media_file(question["media_file_id"], db)
            question["media_file_base64"] = base64.b64encode(file_data).decode("utf-8")
        except Exception as e:
            print(e)
            question["media_file_base64"] = None

    return success(data=jsonable_encoder(question))

@router.get("/all", response_model=list[dict])
async def get_all_questions(
    current_user: dict = Depends(get_current_admin_user),
    db=Depends(get_database)
):
    """
    Возвращает все активные вопросы (без base64-медиа),
    но с информацией о наличии медиа.
    Доступ только для admin и moderator.
    """
    if "role" not in current_user or current_user["role"] not in {"admin", "moderator"}:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    cursor = db.questions.find({"deleted": False})
    questions = []
    async for q in cursor:
        q["id"] = str(q["_id"])
        del q["_id"]
        # Convert media_file_id to string if it exists
        if q.get("media_file_id"):
            q["media_file_id"] = str(q["media_file_id"])
        # Добавляем признак наличия медиа
        q["has_media"] = bool(q.get("media_file_id") and q.get("media_filename"))
        # Очищаем тяжелые поля
        q.pop("media_file_id", None)
        q.pop("media_filename", None)
        questions.append(q)

    return success(data=questions)
