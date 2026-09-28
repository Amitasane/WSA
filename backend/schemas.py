from pydantic import BaseModel
from datetime import date


class RecordCreate(BaseModel):
    date: date
    auditor_name: str
    shift: str
    line: str
    type: str
    parts_checked: int
    nok: int