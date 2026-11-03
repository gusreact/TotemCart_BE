from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6)
    nombre: str = Field(..., min_length=1, max_length=255)
    role_id: int = Field(default=2, gt=0)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=255)
    password: Optional[str] = Field(default=None, min_length=6)
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role_id: Optional[int] = Field(default=None, gt=0)


class UserOut(BaseModel):
    id: int
    username: str
    nombre: str
    role_id: int
    role: str
    role_es: str
    role_en: str
    created_at: Optional[datetime] = None
