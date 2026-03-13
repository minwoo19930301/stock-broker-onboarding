from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .catalog import BROKER_CATALOG
from .config import settings
from .schemas import (
    BrokerListResponse,
    BrokerSummary,
    ConnectionValidationRequest,
    ConnectionValidationResponse,
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="다중 증권사 계정/API 키 온보딩용 toy backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_broker_or_404(broker_id: str) -> dict:
    broker = next((item for item in BROKER_CATALOG if item["id"] == broker_id), None)
    if broker is None:
        raise HTTPException(status_code=404, detail="broker_not_found")
    return broker


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/api/v1/brokers", response_model=BrokerListResponse)
def list_brokers() -> BrokerListResponse:
    items = [BrokerSummary(**broker) for broker in BROKER_CATALOG]
    return BrokerListResponse(items=items)


@app.get("/api/v1/brokers/{broker_id}", response_model=BrokerSummary)
def get_broker(broker_id: str) -> BrokerSummary:
    broker = get_broker_or_404(broker_id)
    return BrokerSummary(**broker)


@app.post("/api/v1/account-connections/validate", response_model=ConnectionValidationResponse)
def validate_connection(request: ConnectionValidationRequest) -> ConnectionValidationResponse:
    broker = get_broker_or_404(request.broker_id)
    status = broker["status"]
    accepted_fields = broker["required_fields"] + broker["optional_fields"]

    if status != "ready":
        return ConnectionValidationResponse(
            broker_id=request.broker_id,
            status=status,
            is_supported=False,
            missing_fields=[],
            accepted_fields=accepted_fields,
            warnings=[
                "현재 상태에서는 self-service 입력형 연동을 열지 않는 것이 안전합니다.",
                f"broker_status={status}",
            ],
        )

    missing_fields = []
    for field_name in broker["required_fields"]:
        raw_value = request.values.get(field_name)
        if raw_value is None:
            missing_fields.append(field_name)
            continue

        if isinstance(raw_value, str) and not raw_value.strip():
            missing_fields.append(field_name)

    warnings = []
    extra_fields = sorted(set(request.values.keys()) - set(accepted_fields))
    if extra_fields:
        warnings.append(f"unused_fields={','.join(extra_fields)}")

    if "app_key" in request.values or "app_secret" in request.values:
        warnings.append("toy_project_only_do_not_store_plaintext_secrets_in_production")

    return ConnectionValidationResponse(
        broker_id=request.broker_id,
        status=status,
        is_supported=True,
        missing_fields=missing_fields,
        accepted_fields=accepted_fields,
        warnings=warnings,
    )
