# 무료 호스팅 기준 아키텍처 메모

이 프로젝트는 이제 `Python 백엔드` 기준으로 잡는 편이 맞다.  
결론부터 말하면 `Flask`보다 `FastAPI`를 추천한다.

이유는 단순하다.

- API 문서가 자동으로 열린다
- 입력 검증을 빨리 붙일 수 있다
- 타입 기반으로 브로커별 계정 입력 스키마를 관리하기 쉽다
- 나중에 비동기 호출, 작업 큐, WebSocket 확장으로 넘어가기 편하다

## Flask vs FastAPI

### Flask

장점:

- 아주 작고 단순하다
- 전통적인 구조라 자료가 많다

단점:

- 요청 검증, 응답 스키마, 문서화를 직접 많이 챙겨야 한다
- toy에서 빨리 시작은 쉬워도, 브로커별 입력 스키마가 늘어나면 코드가 지저분해지기 쉽다

### FastAPI

장점:

- Swagger / ReDoc 문서가 기본 제공된다
- Pydantic 기반 검증이 좋아서 `계좌번호`, `App Key`, `환경값` 검증이 편하다
- REST API 위주 프로젝트에 잘 맞는다
- 나중에 worker나 internal API를 추가하기 좋다

단점:

- Flask보다 개념이 조금 더 많다

## 최종 선택

이 프로젝트는 `FastAPI`로 가는 게 맞다.

특히 네 서비스는 다음이 중요하다.

- 증권사별 입력 폼이 다름
- 사용자별 API 키 구조가 다름
- 요청/응답 포맷을 엄격히 통제해야 함
- 나중에 주문 요청 전에 검증 로직이 많이 붙음

이건 FastAPI 쪽이 훨씬 편하다.

## 추천 스택

현재 프로젝트 기본값:

- `FE`: Cloudflare Pages
- `BE`: FastAPI on Oracle Always Free VM
- `DB`: Neon Postgres
- `리버스 프록시`: nginx on Oracle VM
- `스케줄`: 처음엔 crontab, 나중에 별도 worker

Cloud Run은 호출형 백엔드 기준으로는 좋지만, 이 프로젝트처럼 `계속 살아있는 작은 서버`를 의도하면 Oracle VM 쪽이 더 맞다.

## 대안 스택

- `FE`: React + Vite
- `FE 호스팅`: Cloudflare Pages
- `BE`: FastAPI
- `BE 호스팅`: Google Cloud Run
- `DB`: Neon Postgres
- `스케줄`: Cloud Scheduler
- `캐시/큐`: 처음엔 없음, 나중에 Upstash Redis 또는 별도 큐

## DB 선택: Supabase vs Neon

### 기본 추천: Neon

FastAPI + SQLAlchemy / SQLModel / psycopg 조합이면 `Neon`이 기본 선택으로 제일 깔끔하다.

이유:

- 순수 Postgres처럼 붙이기 쉽다
- 브랜치 기능이 강하다
- 백엔드가 DB를 중심으로 권한과 트랜잭션을 통제하기 좋다
- 무료 플랜이 넓다

공식 가격 페이지 기준 무료 플랜:

- `100 projects`
- `project당 100 compute hours`
- `0.5 GB storage / project`
- 유휴 후 `scale-to-zero`

### Supabase가 맞는 경우

다음까지 한 번에 쓰고 싶다면 Supabase가 낫다.

- 회원 인증
- 파일 저장
- Realtime
- Edge Functions

공식 플랫폼 문서 기준 각 프로젝트는 다음을 포함한다.

- dedicated Postgres
- Auth
- Edge Functions
- Realtime API
- Storage

무료 플랜 기준:

- `2 free projects`
- `500 MB DB`
- `1 GB file storage`
- `5 GB egress`

### 내 추천

- `DB만 필요`: Neon
- `인증/스토리지까지 한 번에`: Supabase

현재는 `Neon 우선`이 더 맞다.

## 무료 호스팅 후보

### 1. Cloudflare Pages

프론트엔드 1순위.

장점:

- 정적 자산 배포가 쉽다
- 무료 플랜에서 프로젝트 수와 빌드 수가 넉넉하다
- React/Vite SPA 배포가 편하다

주의:

- Functions는 Workers 요금/한도를 공유한다
- API까지 몰아넣으면 금방 제약이 생긴다

추천:

- 프론트 전용

### 2. Vercel Hobby

프론트 대안.

장점:

- 배포 UX가 좋다
- Next.js와 궁합이 좋다

주의:

- 공식 문서 기준 `personal, non-commercial use only`
- toy/demo에는 좋지만 서비스 공개 방향이면 애매해질 수 있다

추천:

- 개인 데모
- Next.js 실험

### 3. Google Cloud Run

FastAPI 백엔드 1순위.

장점:

- 컨테이너 기반이라 Python API 서버 올리기 쉽다
- 무료 사용량이 꽤 있다
- scale-to-zero가 된다

공식 Free Tier 기준:

- `2M requests / month`
- `360,000 GB-seconds / month`
- `180,000 vCPU-seconds / month`

주의:

- billing account는 필요하다
- 유휴 시 cold start가 있다
- 24시간 상시 워커 용도는 불리하다

추천:

- 계정 등록 API
- 브로커 목록 API
- 주문 승인 API
- 폴링 기반 전략 실행 엔드포인트

### 4. Cloud Scheduler

Cloud Run과 같이 쓰기 좋다.

공식 가격 기준:

- `3 jobs/month free`

추천:

- 장 시작 직전 준비 작업
- 5분 간격 전략 점검
- 장 종료 후 정리 작업

### 5. Oracle Cloud Always Free

상시 워커가 필요하면 후보가 된다.

장점:

- Always Free VM이 존재한다
- 공식 문서 기준 `VM.Standard.E2.1.Micro 최대 2개` 또는 `Ampere A1 총 4 OCPU / 24 GB memory` 범위가 있다

주의:

- 운영 난이도가 높다
- 인스턴스 확보와 관리가 번거롭다

추천:

- 항상 켜져 있어야 하는 감시 워커
- polling보다 긴 연결이 필요한 경우

### 6. Render / Koyeb

실험용 후보.

#### Render

공식 문서 기준 free web service는 `15분 idle 후 spin down`, `750 free instance hours/month`.

자동매매에는 불리하다.

#### Koyeb

공식 docs에는 inactivity 시 deployment가 sleeping 상태가 되는 흐름이 보인다. 다만 현재 pricing 페이지는 usage-based로 읽히고, `Starter` 상세가 명확하지 않아서 `always-free` 전제로 잡기엔 애매하다.

## 자동매매에서 무료 호스팅의 현실적인 한계

무료 환경에서 가장 먼저 막히는 건 `백그라운드 작업`이다.

예:

- 장중 계속 시세 감시
- WebSocket 장기 연결 유지
- 주문 재시도 큐
- 체결 이벤트 추적

그래서 toy 프로젝트는 처음부터 이렇게 나누는 게 좋다.

- `web`: UI
- `api`: 계정/브로커/전략/주문 승인
- `scheduler`: 주기적으로 api를 깨우는 역할
- `worker`: 나중에 필요해질 상시 실행 컴포넌트

## 권장 배포 시나리오

### 시나리오 A: 가장 무난한 기본값

- `FE`: Cloudflare Pages
- `BE`: FastAPI on Cloud Run
- `DB`: Neon
- `스케줄`: Cloud Scheduler

장점:

- 가장 균형이 좋다
- 구현 난이도와 운영 난이도가 무난하다
- 프론트/백엔드 분리가 깔끔하다

단점:

- billing account 필요
- cold start 있음

### 시나리오 B: auth/storage까지 빨리 붙이고 싶을 때

- `FE`: Cloudflare Pages
- `BE`: FastAPI on Cloud Run
- `DB/Auth/Storage`: Supabase

장점:

- 회원 기능과 파일 업로드를 빨리 붙일 수 있다

단점:

- 권한/인증 책임이 백엔드와 겹칠 수 있다

### 시나리오 C: 상시 워커까지 필요할 때

- `FE`: Cloudflare Pages
- `API`: FastAPI on Cloud Run
- `Worker`: Oracle Always Free VM
- `DB`: Neon

장점:

- API와 상시 워커를 분리 가능

단점:

- 인프라 복잡도 상승

## 추천 폴더 구조

```text
apps/
  web/        # React + Vite
  api/        # FastAPI
docs/
infra/
```

## 토이 프로젝트 기준 1차 범위

1. `web`과 `api` 분리
2. DB는 `Neon`
3. 브로커 목록/상태 조회 API 구현
4. 사용자 증권사 자격증명 등록 API 구현
5. 전략은 실시간 대신 `5분 polling`
6. 주문 실행은 처음엔 mock 또는 sandbox 우선

## 최종 추천

지금 기준 기본값:

- `프론트`: Cloudflare Pages
- `백엔드`: FastAPI
- `백엔드 호스팅`: Cloud Run
- `DB`: Neon
- `Supabase`: 나중에 auth/storage가 필요할 때만 부분 도입

이 구성이 `간단함`, `무료 우선`, `Python 친화적`, `나중 확장 가능`의 균형이 가장 좋다.

## 공식 문서

- Neon Pricing: https://neon.com/pricing
- Supabase Platform: https://supabase.com/docs/guides/platform
- Supabase Billing / Free Plan: https://supabase.com/docs/guides/platform/billing-on-supabase
- Cloudflare Pages Limits: https://developers.cloudflare.com/pages/platform/limits/
- Cloudflare Pages Functions Pricing: https://developers.cloudflare.com/pages/functions/pricing/
- Vercel Pricing: https://vercel.com/pricing
- Vercel Hobby Plan: https://vercel.com/docs/plans/hobby
- Google Cloud Free Tier: https://docs.cloud.google.com/free/docs/free-cloud-features
- Google Cloud Run Quickstart: https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-java-service
- Cloud Scheduler Pricing: https://cloud.google.com/scheduler/pricing
- Oracle Always Free Resources: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Render Free Services: https://render.com/free
- Koyeb Pricing: https://www.koyeb.com/pricing/
