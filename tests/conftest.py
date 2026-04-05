"""
Configuración global de pytest.

El lifespan de FastAPI captura internamente los errores de conexión a la BD,
por lo que los tests no necesitan mockear el engine de SQLAlchemy.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """
    Cliente HTTP de pruebas. El lifespan falla silenciosamente si no hay
    PostgreSQL disponible, lo que es el comportamiento esperado en CI.
    """
    # Import dentro del fixture: sys.path ya está configurado con PYTHONPATH
    from api.main import app

    with TestClient(app) as c:
        yield c
