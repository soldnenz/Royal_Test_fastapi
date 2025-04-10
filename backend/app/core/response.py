# app/core/response.py

from fastapi.responses import JSONResponse
from datetime import datetime
import uuid

def make_meta(pagination=None):
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "trace_id": str(uuid.uuid4()),
        "pagination": pagination
    }

def success(data=None, message="Операция выполнена успешно", pagination=None):
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "message": message,
            "data": data,
            "meta": make_meta(pagination)
        }
    )

def error(code=400, message="Ошибка", details=None):
    return JSONResponse(
        status_code=code,
        content={
            "status": "error",
            "code": code,
            "message": message,
            "details": details,
            "meta": make_meta()
        }
    )
