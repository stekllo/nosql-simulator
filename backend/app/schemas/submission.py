"""Схемы для запуска запросов и проверки решений."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import SubmissionStatus


class RunRequest(BaseModel):
    """Тело запроса `POST /tasks/{id}/run` и `/submit`."""
    query_text: str = Field(min_length=1, max_length=8000)


class RunResponse(BaseModel):
    """Результат выполнения запроса (dry run)."""
    ok:          bool
    duration_ms: int
    result:      Any | None = None
    error:       str | None = None


class SubmitResponse(BaseModel):
    """Результат отправки решения (сохранено в БД)."""
    model_config = ConfigDict(from_attributes=True)

    submission_id: int
    is_correct:    bool | None
    score:         int  | None
    status:        SubmissionStatus
    duration_ms:   int
    result:        Any | None = None
    error:         str | None = None
    submitted_at:  datetime
