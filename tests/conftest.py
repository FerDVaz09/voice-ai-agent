"""
Configuración global de pytest.

Los imports de 'api.main' se hacen DENTRO del fixture (no a nivel de módulo)
para garantizar que sys.path ya esté configurado cuando se ejecutan.
El PYTHONPATH se configura a nivel de job en el workflow de GitHub Actions.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


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

    Los imports se hacen aquí (no a nivel de módulo) para asegurar que
    sys.path ya incluye la raíz del proyecto antes de importar api.main.

    Orden garantizado:
    1. monkeypatch reemplaza api.main.engine con el mock
    2. TestClient inicia → lifespan usa el mock (no Postgres)
    3. Test corre
    4. TestClient cierra al salir del with-block
    """
    # Imports dentro del fixture: sys.path ya está configurado en este punto
    from fastapi.testclient import TestClient
    from api.main import app

    mock_engine = MagicMock()
    mock_engine.begin.return_value = _AsyncContextManager()
    monkeypatch.setattr("api.main.engine", mock_engine)

    with TestClient(app) as c:
        yield c
