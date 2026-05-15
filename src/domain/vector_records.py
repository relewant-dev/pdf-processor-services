from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CandidateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    seniority: str | None = Field(default=None, max_length=50)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    address: str | None = None
    competences: dict[str, Any] = Field(default_factory=dict)
    previous_works: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] | dict[str, Any] = Field(default_factory=list)
    current_job_title: str | None = Field(default=None, max_length=150)
    current_company: str | None = Field(default=None, max_length=150)
    availability_date: date | None = None


class InsuranceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insurance_number: str = Field(..., min_length=1, max_length=100)
    candidate_id: UUID | None = None
    insurance_type: str | None = Field(default=None, max_length=100)
    provider_name: str = Field(..., min_length=1, max_length=150)
    policy_holder_first_name: str | None = Field(default=None, max_length=100)
    policy_holder_last_name: str | None = Field(default=None, max_length=100)
    iban: str | None = Field(default=None, max_length=34)
    bic_swift: str | None = Field(default=None, max_length=20)
    monthly_price: Decimal | None = None
    annual_price: Decimal | None = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    coverage_details: dict[str, Any] = Field(default_factory=dict)
    start_date: date
    end_date: date | None = None
    renewal_date: date | None = None
    status: str | None = Field(default=None, max_length=50)
    payment_frequency: str | None = Field(default=None, max_length=50)
    last_payment_date: date | None = None
    beneficiary: dict[str, Any] = Field(default_factory=dict)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None
