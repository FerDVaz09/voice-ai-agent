# 🎙️ Voice AI Agent — Sofia MedCare Assistant

Agente de voz autónomo que recibe y realiza llamadas telefónicas utilizando IA avanzada. Sofia es capaz de mantener conversaciones naturales, agendar citas médicas y extraer información valiosa en tiempo real.

## 🚀 Características
- **Llamadas Autónomas**: Manejo de llamadas entrantes y salientes vía Vapi.
- **Conversación Natural**: Impulsado por Groq (Llama 3) para máxima velocidad y bajo costo.
- **Tools Personalizadas**: El agente puede agendar citas directamente en la base de datos local.
- **Base de Datos Local**: Seguimiento completo en PostgreSQL (Docker).
- **Webhooks**: Procesamiento de eventos en tiempo real con FastAPI.

## 🛠️ Stack Tecnológico
- **Core**: FastAPI (Python)
- **Voz/Telefonía**: Vapi.ai + Deepgram (STT) + ElevenLabs (TTS)
- **IA**: Groq (Llama 3 70B)
- **Base de Datos**: PostgreSQL 16 (Docker)
- **DevOps**: Docker Compose

## 📂 Estructura
```text
voice-ai-agent/
├── api/             # FastAPI + Webhooks + Config
├── tools/           # Herramientas para el agente (DB, Calendar)
├── tests/           # Pruebas unitarias
├── scripts/         # SQL Setup
└── Dockerfile       # Containerización
```

## ⚙️ Configuración
1. Clona el repositorio.
2. Crea un archivo `.env` basado en `.env.example`.
3. Levanta la base de datos: `docker-compose up -d`.
4. Instala dependencias: `pip install -r requirements.txt`.
5. Inicia el servidor: `uvicorn api.main:app --reload`.

## 🧪 Tests
Ejecuta las pruebas con:
```bash
pytest tests/ -v
```
