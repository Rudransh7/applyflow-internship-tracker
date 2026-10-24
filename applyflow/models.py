"""Validated boundaries shared by HTTP requests and CSV imports."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class Status(str, Enum):
    SAVED = "Saved"
    APPLIED = "Applied"
    ASSESSMENT = "Assessment"
    INTERVIEW = "Interview"
    OFFER = "Offer"
    REJECTED = "Rejected"


Company = Annotated[str, Field(min_length=2, max_length=120)]
Role = Annotated[str, Field(min_length=2, max_length=160)]
Location = Annotated[str, Field(max_length=120)]
Notes = Annotated[str, Field(max_length=2000)]
JobURL = Annotated[HttpUrl, Field(max_length=2048)]


class StrictModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def reject_controls(cls, value):
        if isinstance(value, str) and any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("Control characters are not allowed")
        return value


class ApplicationInput(StrictModel):
    company: Company
    role: Role
    location: Location = ""
    url: JobURL | None = None
    deadline: date | None = None
    status: Status = Status.SAVED
    notes: Notes = ""

    @field_validator("url")
    @classmethod
    def no_url_credentials(cls, value):
        if value and (value.username or value.password):
            raise ValueError("Do not include credentials in job URLs")
        return value


class ApplicationPatch(StrictModel):
    company: Company | None = None
    role: Role | None = None
    location: Location | None = None
    url: JobURL | None = None
    deadline: date | None = None
    status: Status | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def valid_patch(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        for name in self.model_fields_set - {"url", "deadline"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        ApplicationInput.no_url_credentials(self.url)
        return self


class Application(ApplicationInput):
    id: int
    created_at: datetime
    updated_at: datetime


class ApplicationPage(BaseModel):
    items: list[Application]
    total: int
    limit: int
    offset: int


class Statistics(BaseModel):
    total: int
    by_status: dict[Status, int]
    due_soon: int
    overdue: int
    today: date


class ImportResult(BaseModel):
    imported: int
