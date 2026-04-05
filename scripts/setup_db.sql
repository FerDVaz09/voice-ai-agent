-- Extension para UUIDs
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Tabla de llamadas
CREATE TABLE IF NOT EXISTS calls (
  id uuid primary key default gen_random_uuid(),
  vapi_call_id text unique,
  caller_number text,
  direction text check (direction in ('inbound', 'outbound')),
  status text default 'initiated',
  duration_seconds integer,
  summary text,
  transcript text,
  extracted_data jsonb default '{}',
  created_at timestamp with time zone default now(),
  ended_at timestamp with time zone
);

-- Tabla de citas agendadas por el agente
create table appointments (
  id uuid primary key default gen_random_uuid(),
  call_id uuid references calls(id),
  name text not null,
  phone text,
  email text,
  date_time timestamp with time zone,
  reason text,
  status text default 'scheduled',
  created_at timestamp with time zone default now()
);

-- Vista resumen para el dashboard
create view call_stats as
select
  count(*) as total_calls,
  count(*) filter (where status = 'ended') as completed_calls,
  avg(duration_seconds) as avg_duration_seconds,
  count(*) filter (where extracted_data->>'appointment_scheduled' = 'true') as appointments_booked
from calls;
