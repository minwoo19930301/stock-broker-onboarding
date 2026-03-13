# FastAPI Backend

토이 프로젝트용 최소 백엔드 골격입니다.

포함 기능:

- `GET /healthz`
- `GET /api/v1/brokers`
- `GET /api/v1/brokers/{broker_id}`
- `POST /api/v1/account-connections/validate`

실행:

```bash
cd "/Users/minwokim/Documents/New project/stock-broker-onboarding/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

문서:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Oracle VM 배포:

- [ORACLE_ALWAYS_FREE_DEPLOY_KR.md](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/ORACLE_ALWAYS_FREE_DEPLOY_KR.md)
