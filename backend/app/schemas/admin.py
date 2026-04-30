"""Схемы для админских эндпоинтов /admin/*."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models import UserRole


class AdminUserBrief(BaseModel):
    """Один пользователь в списке /admin/users."""
    model_config = ConfigDict(from_attributes=True)

    user_id:        int
    login:          str
    email:          str
    display_name:   str | None
    role:           UserRole
    created_at:     datetime
    last_login_at:  datetime | None


class AdminUsersResponse(BaseModel):
    """Ответ /admin/users."""
    users:        list[AdminUserBrief]
    total:        int
    by_role:      dict[str, int]   # {"student": N, "teacher": N, "admin": N}


class ChangeUserRoleRequest(BaseModel):
    """Запрос PATCH /admin/users/{id}/role."""
    role: UserRole


class ChangeUserRoleResponse(BaseModel):
    """Ответ PATCH /admin/users/{id}/role."""
    user_id:  int
    old_role: UserRole
    new_role: UserRole
