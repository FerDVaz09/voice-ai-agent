"""
Configuración global de pytest.

El lifespan de la app intenta conectarse a PostgreSQL al arrancar.
Este conftest mockea el engine para que los tests unitarios no requieran
una base de datos real.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


class _AsyncContextManager:
    """Context manager async genérico para mockear engine.begin()."""

    def __init__(self):
        self.conn = AsyncMock()
        self.conn.run_sync = AsyncMock()

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def mock_db_engine(monkeypatch):
    """
    Reemplaza el engine de SQLAlchemy en api.main por un mock.
    Esto evita que el lifespan intente abrir una conexión a PostgreSQL
    durante los tests, haciendo la suite ejecutable sin base de datos.
    """
    mock_engine = MagicMock()
    mock_engine.begin.return_value = _AsyncContextManager()

    monkeypatch.setattr("api.main.engine", mock_engine)
    return mock_engine
