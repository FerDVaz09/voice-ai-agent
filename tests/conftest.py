"""
Configuración global de pytest.

El lifespan de la app intenta conectarse a PostgreSQL al arrancar.
Este conftest mockea el engine y provee un fixture de cliente HTTP
que garantiza el mock se aplica ANTES de que el lifespan se ejecute.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from api.main import app


class _AsyncContextManager:
    """Context manager async reutilizable para mockear engine.begin()."""

    def __init__(self):
        self.conn = AsyncMock()
        self.conn.run_sync = AsyncMock()

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def client(monkeypatch):
    """
    Crea un TestClient con el engine de BD mockeado.

    Orden garantizado:
    1. monkeypatch reemplaza api.main.engine con el mock
    2. TestClient inicia (triggerea el lifespan → usa el mock, no Postgres)
    3. Test corre
    4. TestClient cierra el lifespan al salir del with-block
    """
    mock_engine = MagicMock()
    mock_engine.begin.return_value = _AsyncContextManager()
    monkeypatch.setattr("api.main.engine", mock_engine)

    with TestClient(app) as c:
        yield c
