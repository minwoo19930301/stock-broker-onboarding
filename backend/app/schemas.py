from typing import Any

from pydantic import BaseModel, Field


class BrokerSummary(BaseModel):
    id: str
    name: str
    status: str
    required_fields: list[str]
    optional_fields: list[str]


class BrokerListResponse(BaseModel):
    items: list[BrokerSummary]


class ConnectionValidationRequest(BaseModel):
    broker_id: str = Field(..., description="지원 브로커 식별자")
    values: dict[str, Any] = Field(default_factory=dict, description="사용자가 입력한 원본 값")


class ConnectionValidationResponse(BaseModel):
    broker_id: str
    status: str
    is_supported: bool
    missing_fields: list[str]
    accepted_fields: list[str]
    warnings: list[str]
