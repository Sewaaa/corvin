import re
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}$"
)


class DomainAdd(BaseModel):
    domain: str

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        v = v.strip().lower().rstrip(".")
        # Strip scheme if accidentally included
        v = re.sub(r"^https?://", "", v)
        # Strip path
        v = v.split("/")[0]
        if not DOMAIN_REGEX.match(v):
            raise ValueError(f"'{v}' is not a valid domain name")
        if len(v) > 253:
            raise ValueError("Domain name too long (max 253 characters)")
        return v


class DomainVerifyResponse(BaseModel):
    domain: str
    verification_token: str
    instructions: str


class DomainReport(BaseModel):
    domain: str
    is_verified: bool
    reputation_score: Optional[int] = None
    is_blacklisted: bool
    ssl_expiry: Optional[date] = None
    ssl_days_remaining: Optional[int] = None
    dns_records: Dict
    dmarc_policy: Optional[str] = None
    spf_record: Optional[str] = None
    findings: List[str]
    last_scan_at: Optional[datetime] = None


class DomainResponse(BaseModel):
    id: UUID
    domain: str
    is_verified: bool
    reputation_score: Optional[int] = None
    is_blacklisted: bool
    ssl_expiry: Optional[date] = None
    created_at: datetime

    model_config = {"from_attributes": True}
