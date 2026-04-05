import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import String, Integer, Text, ForeignKey, TIMESTAMP, select, update, and_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/voice_ai")

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now_utc() -> datetime:
    """Hora actual en UTC como datetime naive (compatible con PostgreSQL sin tz)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vapi_call_id: Mapped[str] = mapped_column(String, unique=True)
    caller_number: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="initiated")
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[dict] = mapped_column(JSONB, default=lambda: {})   # ← default mutable seguro
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=_now_utc)  # ← no deprecado
    ended_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)

    appointments = relationship("Appointment", back_populates="call")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("calls.id"), nullable=True)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="scheduled")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=_now_utc)  # ← no deprecado

    call = relationship("Call", back_populates="appointments")


# ---------------------------------------------------------------------------
# Operaciones de llamadas
# ---------------------------------------------------------------------------
async def save_call(vapi_call_id: str, caller_number: str, direction: str) -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        new_call = Call(
            vapi_call_id=vapi_call_id,
            caller_number=caller_number,
            direction=direction,
            status="active",
        )
        session.add(new_call)
        await session.commit()
        await session.refresh(new_call)
        return new_call.id


async def update_call(vapi_call_id: str, **kwargs) -> None:
    async with AsyncSessionLocal() as session:
        stmt = update(Call).where(Call.vapi_call_id == vapi_call_id).values(**kwargs)
        await session.execute(stmt)
        await session.commit()


async def get_call_by_vapi_id(vapi_id: str) -> Optional[Call]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Call).where(Call.vapi_call_id == vapi_id))
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Operaciones de citas
# ---------------------------------------------------------------------------
async def schedule_appointment(
    name: str,
    phone: str,
    date_time: str,
    reason: str,
    call_id: Optional[uuid.UUID] = None,
    email: Optional[str] = None,
) -> dict:
    async with AsyncSessionLocal() as session:
        # Parsear fecha
        dt_obj: Optional[datetime] = None
        if date_time:
            try:
                dt_obj = datetime.fromisoformat(date_time.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception as e:
                print(f"⚠️ Error parseando fecha: {e}")

        # ------------------------------------------------------------------
        # Verificación de double-booking: bloquear si ya existe una cita
        # en una ventana de ±30 minutos para la misma fecha/hora.
        # ------------------------------------------------------------------
        if dt_obj:
            window_start = dt_obj - timedelta(minutes=30)
            window_end = dt_obj + timedelta(minutes=30)
            conflict_stmt = select(Appointment).where(
                and_(
                    Appointment.status == "scheduled",
                    Appointment.date_time >= window_start,
                    Appointment.date_time <= window_end,
                )
            )
            conflict_result = await session.execute(conflict_stmt)
            existing = conflict_result.scalar_one_or_none()
            if existing:
                print(f"⚠️ Double-booking detectado para {dt_obj} (conflicto: {existing.id})")
                return {
                    "success": False,
                    "message": (
                        f"Ya existe una cita agendada cerca de esa hora "
                        f"({existing.date_time}). Por favor elige otro horario."
                    ),
                }

        new_apt = Appointment(
            call_id=call_id,
            name=name,
            phone=phone,
            email=email,
            date_time=dt_obj,
            reason=reason,
        )
        session.add(new_apt)
        await session.commit()
        await session.refresh(new_apt)

        return {
            "success": True,
            "appointment_id": str(new_apt.id),
            "message": f"Cita confirmada para {name}",
        }


async def get_all_appointments(limit: int = 50, offset: int = 0) -> list[Appointment]:
    """Retorna citas paginadas, ordenadas de más reciente a más antigua."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Appointment)
            .order_by(Appointment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()


async def get_all_calls(limit: int = 10) -> list[Call]:
    """Retorna las últimas N llamadas."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Call).order_by(Call.created_at.desc()).limit(limit)
        )
        return result.scalars().all()
