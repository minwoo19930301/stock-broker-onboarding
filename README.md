# AUTO STOCK TRADER(KR)

국내 증권사 자동매매 서비스를 위한 Python 중심 프로토타입입니다.

핵심 목표:

- 증권사별 공개 API 상태를 한 화면에서 분류
- 바로 연결 가능한 증권사는 계좌/API 키 입력 폼 제공
- 제휴형 또는 공개 주문 API 미확인 증권사는 사유와 공식 링크 선고지
- 사용자가 각 증권사에서 직접 회원가입/계좌개설 후 필요한 값만 수집

현재 포함 상태:

- `바로 연결 가능`: 키움증권, 한국투자증권, DB증권, LS증권
- `제휴형`: KB증권
- `레거시/확인 필요`: NH투자증권
- `공개 주문 API 미확인`: 토스/토스증권, 카카오페이/카카오페이증권, 네이버페이

실동작 기능:

- Google / Kakao / Naver / Facebook OAuth2 SSO 로그인
- 한국투자증권(KIS) 연결 시 계좌 잔고/보유종목 실조회
- KIS 종목코드 직접 조회(현재가 기반) 후 워치리스트 추가

주의:

- 브로커 키는 서버 메모리에만 저장됩니다. 서버 재시작 시 초기화됩니다.
- 현재 실브로커 조회는 `KIS` 위주로 구현되어 있고, 다른 브로커는 확장 포인트만 열려 있습니다.
- 실서비스에서는 입력값을 서버 측 암호화 저장소로 옮기고 감사로그를 남겨야 합니다.
- 한국투자증권처럼 개인 self-use와 고객 대상 제휴 흐름이 분리된 증권사는 약관/제휴 요건을 별도로 검토해야 합니다.

실행:

1. Python 서버를 실행합니다.
2. 브라우저에서 로컬 페이지 또는 배포 주소로 접속합니다.

예시:

```bash
cd "/Users/minwokim/Documents/New project/stock-broker-onboarding"
PORT=4321 python3 server.py
```

그 다음 브라우저에서 `http://localhost:4321` 로 접속합니다.

환경변수(SSO):

```bash
export APP_BASE_URL="https://your-domain.example"
export SSO_GOOGLE_CLIENT_ID="..."
export SSO_GOOGLE_CLIENT_SECRET="..."
export SSO_KAKAO_CLIENT_ID="..."
export SSO_KAKAO_CLIENT_SECRET="..."
export SSO_NAVER_CLIENT_ID="..."
export SSO_NAVER_CLIENT_SECRET="..."
export SSO_FACEBOOK_CLIENT_ID="..."
export SSO_FACEBOOK_CLIENT_SECRET="..."
```

옵션:

- `SSO_<PROVIDER>_REDIRECT_URI`를 지정하면 기본 콜백 URL(`{APP_BASE_URL}/auth/sso/callback/<provider>`) 대신 사용합니다.
- `REQUEST_TIMEOUT_SECONDS`로 외부 API 타임아웃을 조정할 수 있습니다.

주요 엔드포인트:

- `/` 메인 온보딩 화면
- `/healthz` 서비스 상태 확인
- `/api/v1/brokers` 브로커 요약 목록
- `/api/v1/brokers/{broker_id}` 브로커 상세
- `/api/v1/brokers/{broker_id}/symbols?q=005930` 브로커 종목/조회 결과
- `/api/v1/account-connections/validate` JSON 기반 입력 검증
