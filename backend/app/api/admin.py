"""Админские эндпоинты — управление пользователями.

Только для пользователей с ролью ADMIN. Проверка через `require_role`
на уровне router.dependencies.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, require_role
from app.db import get_db
from app.models import User, UserRole
from app.schemas.admin import (
    AdminUserBrief, AdminUsersResponse,
    ChangeUserRoleRequest, ChangeUserRoleResponse,
)


router = APIRouter(dependencies=[Depends(require_role(UserRole.ADMIN))])


# ---------- /admin/users ----------

@router.get("/users", response_model=AdminUsersResponse)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    role:    UserRole | None = Query(None, description="Фильтр по роли"),
) -> AdminUsersResponse:
    """Список всех пользователей системы.

    Опционально фильтруется по роли. В ответе также возвращаются
    счётчики по ролям для UI-фильтра.
    """
    # Список (с фильтром).
    stmt = select(User).order_by(User.user_id)
    if role is not None:
        stmt = stmt.where(User.role == role)
    result = await session.execute(stmt)
    users  = list(result.scalars().all())

    # Счётчики по ролям (всегда — без учёта фильтра).
    counts_q = await session.execute(
        select(User.role, func.count(User.user_id)).group_by(User.role)
    )
    by_role: dict[str, int] = {r.value: 0 for r in UserRole}
    for r, cnt in counts_q.all():
        by_role[r.value] = cnt

    # Total — с учётом фильтра, чтобы UI мог показать "найдено: N".
    total_q = await session.execute(
        select(func.count(User.user_id)).where(
            User.role == role if role is not None else True
        )
    )
    total = total_q.scalar_one()

    return AdminUsersResponse(
        users   = [AdminUserBrief.model_validate(u) for u in users],
        total   = total,
        by_role = by_role,
    )


# ---------- /admin/users/{id}/role ----------

@router.patch("/users/{user_id}/role", response_model=ChangeUserRoleResponse)
async def change_user_role(
    user_id: int,
    body:    ChangeUserRoleRequest,
    me:      CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChangeUserRoleResponse:
    """Сменить роль пользователю.

    Защита от самоблокировки: админ не может изменить **свою** роль —
    иначе единственный админ может случайно сделать себя студентом и
    потерять доступ к этой странице. Чтобы реально сменить свою роль,
    нужно действовать через другого админа или через psql.
    """
    if user_id == me.user_id:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = "Нельзя менять собственную роль "
                          "(защита от случайной потери прав)",
        )

    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")

    old_role = target.role
    if old_role == body.role:
        # Идемпотентно: если роль уже такая — просто 200 без изменений.
        return ChangeUserRoleResponse(
            user_id  = target.user_id,
            old_role = old_role,
            new_role = old_role,
        )

    target.role = body.role
    await session.commit()
    await session.refresh(target)

    return ChangeUserRoleResponse(
        user_id  = target.user_id,
        old_role = old_role,
        new_role = target.role,
    )
