import os

import httpx
from dotenv import load_dotenv

from api.agent_config import VAPI_ASSISTANT_CONFIG

load_dotenv()

VAPI_BASE_URL = "https://api.vapi.ai"


def _get_headers() -> dict:
    """
    Construye los headers en tiempo de llamada para que VAPI_API_KEY
    siempre refleje el valor actual del entorno (evita headers vacíos
    si load_dotenv() se ejecuta después de la importación del módulo).
    """
    return {
        "Authorization": f"Bearer {os.getenv('VAPI_API_KEY', '')}",
        "Content-Type": "application/json",
    }


async def create_assistant() -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VAPI_BASE_URL}/assistant",
            headers=_get_headers(),
            json=VAPI_ASSISTANT_CONFIG,
        )
        response.raise_for_status()
        return response.json()


async def make_outbound_call(
    phone_number: str,
    customer_name: str,
    context: dict = {},
) -> dict:
    payload = {
        "phoneNumberId": os.getenv("VAPI_PHONE_NUMBER_ID", ""),
        "assistantId": os.getenv("VAPI_ASSISTANT_ID", ""),
        "customer": {
            "number": phone_number,
            "name": customer_name,
        },
        "assistantOverrides": {
            "variableValues": {
                "customer_name": customer_name,
                **context,
            }
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VAPI_BASE_URL}/call/phone",
            headers=_get_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def get_call_details(call_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{VAPI_BASE_URL}/call/{call_id}",
            headers=_get_headers(),
        )
        response.raise_for_status()
        return response.json()
