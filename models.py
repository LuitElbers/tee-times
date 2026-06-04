from datetime import datetime
from pydantic import BaseModel

class TeeTime(BaseModel):
    course: str
    sub_course: str
    time: str
    timestamp: datetime
    holes: int
    free_slots: int
    total_slots: int
    price_eur: float | None
    is_available: bool
    booking_url: str
