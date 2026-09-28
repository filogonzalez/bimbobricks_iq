"""Payloads de los formularios y validación de dominio en el backend.

Los nombres de campo son los que envía el HTML (camelCase); extra="allow" deja pasar
campos nuevos que el dueño añada, que se guardan en la columna `raw`.
"""
import os
import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_DOMAINS = tuple(
    d.strip().lower() for d in os.getenv("ALLOWED_DOMAINS", "grupobimbo.com,gbsupport.net").split(",") if d.strip()
)
_EMAIL = re.compile(r"^[^\s@]+@([^\s@]+)$")


def corporate_email(v: str) -> str:
    v = (v or "").strip().lower()
    m = _EMAIL.match(v)
    if not m or m.group(1) not in ALLOWED_DOMAINS:
        raise ValueError("Solo se aceptan correos @" + " o @".join(ALLOWED_DOMAINS))
    return v


class Registration(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str = Field(min_length=2, max_length=200)
    email: str
    country: Optional[str] = Field(default=None, max_length=100)
    area: Optional[str] = Field(default=None, max_length=200)
    kickoff: bool
    kickoff_mode: Optional[Literal["remote", "onsite"]] = Field(default=None, alias="kickoffMode")
    wave: bool
    training_language: Literal["es", "en"] = Field(alias="trainingLanguage")
    self_assessment_done: Optional[bool] = Field(default=None, alias="selfAssessmentDone")
    ui_language: Optional[str] = Field(default=None, alias="uiLanguage", max_length=10)
    submitted_at: Optional[datetime] = Field(default=None, alias="submittedAt")
    source: Optional[str] = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def check_email(cls, v):
        return corporate_email(v)

    @field_validator("name", "country", "area", mode="before")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class _Request(BaseModel):
    """Base de los formularios "Envía tu idea" y "Solicita tu acceso" (una fila por envío)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str = Field(min_length=2, max_length=200)
    email: str
    area: Optional[str] = Field(default=None, max_length=200)
    submitted_at: Optional[datetime] = Field(default=None, alias="submittedAt")
    source: Optional[str] = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def check_email(cls, v):
        return corporate_email(v)

    @field_validator("name", "area", mode="before")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class Idea(_Request):
    idea: str = Field(min_length=10, max_length=500)


class AccessRequest(_Request):
    country: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, max_length=100)
    urgency: Optional[str] = Field(default=None, max_length=50)


class Newsletter(BaseModel):
    model_config = ConfigDict(extra="allow")

    email: str
    lang: Optional[str] = Field(default=None, max_length=10)
    source: Optional[str] = Field(default=None, max_length=100)
    ts: Optional[datetime] = None

    @field_validator("email")
    @classmethod
    def check_email(cls, v):
        return corporate_email(v)
