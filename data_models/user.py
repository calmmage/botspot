from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserData(BaseModel):
    user_id: int
    timezone: str = "UTC"
    location: Optional[dict] = None  # Can store coordinates or location name
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    settings: dict = Field(default_factory=dict)  # For component-specific settings
