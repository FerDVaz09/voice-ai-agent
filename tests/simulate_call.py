import httpx
import asyncio
import json

BASE_URL = "http://localhost:8000/webhook/vapi"

async def simulate_vapi_flow():
    async with httpx.AsyncClient() as client:
        # 1. Simular inicio de llamada
        print("--- Simulando inicio de llamada ---")
        start_payload = {
            "message": {
                "type": "call.started",
                "call": {
                    "id": "test-call-123",
                    "customer": {"number": "+573001234567"},
                    "type": "inbound"
                }
            }
        }
        resp = await client.post(BASE_URL, json=start_payload)
        print(f"Respuesta inicio: {resp.status_code}")

        # 2. Simular Tool Call (Agendar Cita)
        print("\n--- Simulando Tool Call (Cita) ---")
        tool_payload = {
            "message": {
                "type": "tool-calls",
                "call": {"id": "test-call-123"},
                "toolCalls": [{
                    "id": "tool-1",
                    "function": {
                        "name": "schedule_appointment",
                        "arguments": {
                            "name": "Juan Pérez",
                            "date_time": "2026-03-25T10:00:00Z",
                            "reason": "Control general",
                            "phone": "+573001234567"
                        }
                    }
                }]
            }
        }
        resp = await client.post(BASE_URL, json=tool_payload)
        print(f"Respuesta tool: {resp.status_code}")
        print(f"Contenido: {resp.json()}")

        # 3. Simular fin de llamada
        print("\n--- Simulando fin de llamada ---")
        end_payload = {
            "message": {
                "type": "call.ended",
                "call": {
                    "id": "test-call-123",
                },
                "summary": "El paciente Juan Pérez agendó una cita para el 25 de marzo.",
                "transcript": "Sofia: Hola... Juan: Quiero una cita... Sofia: Claro...",
                "durationSeconds": 45
            }
        }
        resp = await client.post(BASE_URL, json=end_payload)
        print(f"Respuesta fin: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(simulate_vapi_flow())
# Para verificar en la DB después de correr este script:
# docker exec -it voice-ai-db psql -U user -d voice_ai -c "select * from appointments;"
