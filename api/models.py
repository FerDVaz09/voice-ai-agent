from pydantic import BaseModel
from typing import Optional, Any, List
from datetime import datetime

class VapiWebhookEvent(BaseModel):
    message: dict

class CallStarted(BaseModel):
    call_id: str
    caller_number: str
    direction: str

class AppointmentData(BaseModel):
    name: str
    phone: Optional[str]
    email: Optional[str]
    date_time: Optional[str]
    reason: Optional[str]

class OutboundCallRequest(BaseModel):
    phone_number: str
    customer_name: str
    purpose: str  # 'appointment_reminder', 'lead_qualification', 'support'
    context: Optional[dict] = {}
