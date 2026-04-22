"""Smoke-тесты для базовой проверки, что приложение собирается."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Корневой эндпоинт возвращает имя и версию."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "NoSQL Simulator"


@pytest.mark.asyncio
async def test_health_endpoint_responds():
    """Эндпоинт /health отвечает (содержимое зависит от живых СУБД)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "services" in body
    assert len(body["services"]) == 6
