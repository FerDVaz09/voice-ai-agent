from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from api.models import OutboundCallRequest
from api.vapi_client import make_outbound_call
from tools.database_tool import (
    save_call, update_call, schedule_appointment,
    get_call_by_vapi_id, get_all_appointments, get_all_calls,
    engine, Base,
)

load_dotenv()

# ---------------------------------------------------------------------------
# App lifespan (reemplaza el deprecado @app.on_event("startup"))
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        # En entornos de test sin PostgreSQL el startup falla silenciosamente.
        # En producción, revisar DATABASE_URL y que la DB esté disponible.
        print(f"⚠️  DB startup skipped ({type(e).__name__}: {e})")
    yield


# ---------------------------------------------------------------------------
# CORS — restringible vía env var; por defecto permite todo en desarrollo
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [o.strip() for o in _raw_origins.split(",")]

app = FastAPI(
    title="Voice AI Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_utc() -> datetime:
    """Retorna la hora actual en UTC como datetime naive (compatible con PostgreSQL sin tz)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _verify_webhook_secret(x_vapi_secret: str | None) -> None:
    """Valida la firma del webhook de Vapi. Lanza 403 si no coincide."""
    expected = os.getenv("VAPI_WEBHOOK_SECRET", "")
    if expected and x_vapi_secret != expected:
        raise HTTPException(status_code=403, detail="Webhook secret inválido")


# ---------------------------------------------------------------------------
# Webhook principal de Vapi
# ---------------------------------------------------------------------------
@app.post("/webhook/vapi")
async def vapi_webhook(
    request: Request,
    x_vapi_secret: str | None = Header(default=None),
):
    _verify_webhook_secret(x_vapi_secret)

    try:
        body = await request.json()
        message = body.get("message", {})
        event_type = message.get("type")

        print(f"📞 Evento: {event_type}")

        if event_type in ["call.started", "call-started"]:
            call = message["call"]
            await save_call(
                vapi_call_id=call["id"],
                caller_number=call.get("customer", {}).get("number", "unknown"),
                direction=call.get("type", "inbound"),
            )

        elif event_type in ["tool-calls", "tool.calls"]:
            return await handle_tool_call(message)

        elif event_type in ["call.ended", "end-of-call-report"]:
            call_id = message["call"]["id"]
            await update_call(
                vapi_call_id=call_id,
                status="ended",
                ended_at=_now_utc(),                          # ← Bug fix: se guardaba None
                duration_seconds=int(message.get("durationSeconds", 0)),
                summary=message.get("summary", ""),
                transcript=message.get("transcript", ""),
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en webhook: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))   # ← Bug fix: antes retornaba tupla

    return {"received": True}


# ---------------------------------------------------------------------------
# Lógica de tool-calls
# ---------------------------------------------------------------------------
async def handle_tool_call(message: dict) -> dict:
    tool_calls = message.get("toolCalls", [])
    results = []

    for tool_call in tool_calls:
        tool_name = tool_call["function"]["name"]
        args = tool_call["function"]["arguments"]
        if isinstance(args, str):
            args = json.loads(args)

        if tool_name == "schedule_appointment":
            vapi_id = message["call"]["id"]
            db_call = await get_call_by_vapi_id(vapi_id)

            result = await schedule_appointment(
                call_id=db_call.id if db_call else None, **args
            )

            await update_call(
                vapi_call_id=vapi_id,
                extracted_data={"appointment_scheduled": True, **args},
            )
        else:
            result = {"error": f"Tool '{tool_name}' no encontrada"}

        results.append({
            "toolCallId": tool_call["id"],
            "result": str(result),
        })

    return {"results": results}


# ---------------------------------------------------------------------------
# Llamadas salientes — protegidas con API key
# ---------------------------------------------------------------------------
async def _verify_outbound_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("OUTBOUND_API_KEY", "")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=403, detail="API key inválida")


@app.post("/calls/outbound")
async def initiate_outbound_call(
    request: OutboundCallRequest,
    x_api_key: str | None = Header(default=None),
):
    await _verify_outbound_key(x_api_key)
    try:
        call = await make_outbound_call(           # ← Bug fix: ahora es await (async)
            phone_number=request.phone_number,
            customer_name=request.customer_name,
            context={"purpose": request.purpose, **request.context},
        )
        return {"success": True, "call_id": call["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html>
        <head>
            <title>Sofia AI - Control Panel</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <style>body { font-family: 'Inter', sans-serif; }</style>
        </head>
        <body class="bg-slate-50 min-h-screen flex items-center justify-center p-6">
            <div class="max-w-md w-full bg-white rounded-3xl shadow-2xl shadow-slate-200 overflow-hidden border border-slate-100 transition-all hover:scale-[1.02]">
                <div class="bg-indigo-600 p-8 text-white text-center relative overflow-hidden">
                    <div class="absolute top-0 right-0 p-4 opacity-10">
                        <svg class="w-24 h-24" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                        </svg>
                    </div>
                    <h1 class="text-3xl font-bold mb-2">🎙️ Sofia AI</h1>
                    <p class="text-indigo-100 opacity-90">Agente de Citas MedCare</p>
                </div>
                <div class="p-8 text-center">
                    <div class="flex items-center justify-center gap-2 mb-6">
                        <span class="relative flex h-3 w-3">
                          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                          <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                        </span>
                        <span class="text-emerald-600 font-semibold tracking-wide uppercase text-xs">Sistema Online</span>
                    </div>
                    <p class="text-slate-600 mb-8 leading-relaxed">
                        Conectado correctamente. Sofia está lista para agendar citas desde Vapi.
                    </p>
                    <div class="space-y-3">
                        <a href="/dashboard" class="block w-full py-4 px-6 bg-slate-900 hover:bg-black text-white rounded-2xl font-bold transition-all shadow-lg hover:shadow-xl active:scale-95">
                            Ver Dashboard Real-Time
                        </a>
                        <p class="text-[10px] text-slate-400 uppercase tracking-widest">
                            Webhook: /webhook/vapi
                        </p>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(page: int = 1):
    PAGE_SIZE = 50
    appointments = await get_all_appointments(limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE)
    calls = await get_all_calls()

    appointments_html = ""
    for appt in appointments:
        appointments_html += f"""
        <tr class="hover:bg-slate-50 transition-colors border-b border-slate-100">
            <td class="px-6 py-4 font-semibold text-slate-800">{appt.name}</td>
            <td class="px-6 py-4 text-slate-600 text-sm">{appt.phone or 'No registrado'}</td>
            <td class="px-6 py-4 text-slate-600 text-sm italic">{appt.reason}</td>
            <td class="px-6 py-4">
                <span class="px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs font-bold">
                    {appt.date_time}
                </span>
            </td>
        </tr>
        """

    calls_html = ""
    for call in calls:
        status_color = "bg-emerald-100 text-emerald-700" if call.status == "ended" else "bg-amber-100 text-amber-700"
        duration = f"{call.duration_seconds}s" if call.duration_seconds else "—"
        calls_html += f"""
        <div class="flex items-center justify-between p-4 bg-white border border-slate-100 rounded-xl mb-3 shadow-sm">
            <div>
                <p class="text-xs text-slate-400 font-bold uppercase tracking-tighter">ID: {call.vapi_call_id[:8]}…</p>
                <p class="text-sm font-semibold text-slate-700">{call.caller_number}</p>
                <p class="text-xs text-slate-400">{duration}</p>
            </div>
            <div class="text-right">
                <span class="px-2 py-0.5 {status_color} rounded text-[10px] font-bold uppercase tracking-widest">
                    {call.status}
                </span>
                <p class="text-[10px] text-slate-400 mt-1">{call.created_at.strftime('%H:%M:%S') if call.created_at else ''}</p>
            </div>
        </div>
        """

    prev_link = f'<a href="/dashboard?page={page-1}" class="px-3 py-1 bg-slate-200 rounded text-sm">← Anterior</a>' if page > 1 else ""
    next_link = f'<a href="/dashboard?page={page+1}" class="px-3 py-1 bg-slate-200 rounded text-sm">Siguiente →</a>' if len(appointments) == PAGE_SIZE else ""

    return f"""
    <html>
        <head>
            <title>Sofia Dashboard</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <!-- Auto-refresh cada 30 segundos -->
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: 'Inter', sans-serif; background-color: #f8fafc; }}
            </style>
        </head>
        <body class="p-4 md:p-8">
            <div class="max-w-6xl mx-auto">
                <header class="flex flex-col md:flex-row md:items-center justify-between mb-10 gap-4">
                    <div>
                        <h1 class="text-3xl font-bold text-slate-900 tracking-tight">Dashboard de Citas</h1>
                        <p class="text-slate-500">Gestión de MedCare AI — Sofia Agent</p>
                    </div>
                    <div class="flex gap-3 items-center">
                        <div class="px-4 py-2 bg-white rounded-2xl shadow-sm border border-slate-200 flex items-center gap-2">
                            <div class="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></div>
                            <span class="text-sm font-semibold text-slate-600 uppercase tracking-wide">Live</span>
                        </div>
                        <span class="text-xs text-slate-400">Auto-refresh: 30s</span>
                        <button onclick="window.location.reload()" class="px-4 py-2 bg-indigo-600 text-white rounded-2xl font-bold shadow-lg hover:shadow-indigo-200 transition-all hover:-translate-y-0.5 active:translate-y-0">
                            Refrescar
                        </button>
                    </div>
                </header>

                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div class="lg:col-span-2">
                        <div class="bg-white rounded-3xl shadow-xl shadow-slate-200 overflow-hidden border border-slate-100">
                            <div class="px-6 py-4 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
                                <h2 class="font-bold text-slate-800">Citas Agendadas</h2>
                                <span class="bg-indigo-600 text-white text-[10px] px-2 py-0.5 rounded-full">{len(appointments)} en página {page}</span>
                            </div>
                            <div class="overflow-x-auto">
                                <table class="w-full text-left border-collapse">
                                    <thead>
                                        <tr class="text-xs uppercase text-slate-400 tracking-widest border-b border-slate-50">
                                            <th class="px-6 py-4">Paciente</th>
                                            <th class="px-6 py-4">Teléfono</th>
                                            <th class="px-6 py-4">Motivo</th>
                                            <th class="px-6 py-4">Fecha/Hora</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {appointments_html if appointments else '<tr><td colspan="4" class="px-6 py-20 text-center text-slate-400 italic">No hay citas registradas aún.</td></tr>'}
                                    </tbody>
                                </table>
                            </div>
                            <div class="px-6 py-4 flex gap-3 border-t border-slate-100">
                                {prev_link}
                                {next_link}
                            </div>
                        </div>
                    </div>

                    <div class="space-y-8">
                        <div class="bg-indigo-900 text-indigo-100 p-6 rounded-3xl shadow-xl shadow-indigo-200 relative overflow-hidden">
                            <div class="relative z-10">
                                <h3 class="font-bold mb-1">Estado de Sofia</h3>
                                <p class="text-xs opacity-70 mb-4 tracking-wide font-medium">CONECTADA A VAPI</p>
                                <div class="text-4xl font-black mb-2 tracking-tighter text-white">Online</div>
                                <p class="text-sm leading-snug opacity-80 italic">"Lista para ayudar a tus pacientes."</p>
                            </div>
                            <div class="absolute -right-4 -bottom-4 opacity-10">
                                <svg class="w-32 h-32" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                                </svg>
                            </div>
                        </div>

                        <div>
                            <h3 class="font-bold text-slate-800 mb-4 flex items-center justify-between uppercase tracking-widest text-xs">
                                Llamadas Recientes
                                <span class="h-1.5 w-1.5 rounded-full bg-slate-200"></span>
                            </h3>
                            <div class="space-y-3">
                                {calls_html if calls else '<p class="text-center text-slate-400 italic py-10">Sin llamadas registradas.</p>'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """
