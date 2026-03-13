# Python 무료 호스팅 매트릭스

기준 날짜: `2026-03-12`

이 문서는 `Python 백엔드만` 어디에 올릴지 결정하기 위한 비교표다.  
중요 기준은 딱 네 가지다.

- `정말 무료가 계속 유지되는가`
- `24시간 계속 떠 있을 수 있는가`
- `슬립/콜드스타트가 있는가`
- `외부 API 호출 제약이 있는가`

## 결론

`영생 무료 + 24시간 상시 실행`에 가장 가까운 선택지는 `Oracle Cloud Always Free VM`이다.

다만 이것도 완전 무결한 건 아니다.

- Always Free 자체는 `무기한`
- 하지만 `idle instance reclamation` 정책이 있다
- 즉 너무 놀고 있으면 Oracle이 회수할 수 있다

그래서 현실적으로는 이렇게 보면 된다.

- `진짜 항상 켜진 Python 서버`: Oracle Cloud Always Free VM
- `무료 forever + 잠들어도 됨`: Render 또는 Koyeb
- `무료 forever이지만 항상 켜진 건 사실상 불가`: Cloud Run, Railway
- `이번 프로젝트엔 비추천`: PythonAnywhere free

## 1. Oracle Cloud Always Free VM

### 왜 1순위인가

공식 Free Tier 문서 기준으로:

- Always Free 서비스는 `unlimited time`
- Compute VM을 만들 수 있음
- `VM.Standard.E2.1.Micro` 최대 2개 또는
- `Ampere A1` 기준 `4 OCPUs / 24 GB memory` 상당의 Always Free 범위가 있음

이건 다른 무료 플랫폼보다 훨씬 `서버다운 진짜 서버`에 가깝다.

### 장점

- Python 프로세스를 24시간 계속 띄울 수 있음
- FastAPI, Flask, Celery, cron, systemd 다 가능
- 외부 네트워크 호출이 자유로움
- DB, reverse proxy, worker를 한 VM에 다 넣을 수도 있음

### 단점

- 운영 난이도가 높음
- 초기 세팅이 귀찮음
- 공식 문서에 `Idle Always Free compute instances may be reclaimed`라고 명시됨
- 7일 기준 CPU/네트워크/메모리 사용률이 낮으면 idle로 간주될 수 있음

### 총평

`영생 무료 토이 프로젝트`라는 조건에 제일 가깝다.  
다만 `완전 방치형`은 아니다.

## 2. Render Free Web Service

### 장점

- Python(FastAPI/Flask) web service 배포가 쉬움
- 무료 web service가 있음
- 매월 `750 free instance hours` 제공
- 웹 서비스 자체는 30일 만료가 아니라 계속 유지 가능

### 단점

- 공식 문서 기준 `15분 inactivity` 후 spin down
- 다음 요청이 오면 다시 켜지며 최대 1분 정도 지연 가능
- 플랫폼이 free 서비스를 언제든 restart할 수 있다고 명시
- free Postgres는 `30일 후 만료`

### 총평

`무료 forever`는 맞지만 `항상 깨어 있는 서버`는 아니다.  
작은 데모 API에는 좋지만 자동매매나 webhook 민감한 서비스엔 불리하다.

## 3. Koyeb

### 장점

- Python 앱 배포 자체는 가능하다
- 공식 docs에 inactivity 시 sleeping 상태가 명시되어 있다
- scale-to-zero 성격의 운영이 가능하다

### 단점

- 공식 docs에 deployment 상태로 `Sleeping due to inactivity`가 명시됨
- 즉 inactivity 시 인스턴스가 멈추고, 새 요청이 와야 다시 뜸
- 현재 공식 pricing 페이지는 `Starter`를 참조하지만 Starter 상세를 명확히 노출하지 않고, compute는 `pay only for what you use` 방식으로 보인다
- 즉 `always-free web service`가 지금도 확실히 존재한다고 보기 어렵다

### 총평

기술적으로는 가능하지만, `영생 무료` 후보로는 지금 시점에 확신을 주기 어렵다.  
후보군에는 넣되 1순위로 추천하진 않는다.

## 4. Google Cloud Run

### 장점

- Python 컨테이너 호스팅이 쉽다
- 공식 Free Tier가 큼
- 요청이 없으면 scale-to-zero

공식 Free Tier 기준:

- `2M requests / month`
- `360,000 GB-seconds / month`
- `180,000 vCPU-seconds / month`

### 단점

- 기본 동작이 scale-to-zero
- 공식 autoscaling 문서 기준 `no traffic`이면 `scaled to zero`
- `minimum instances > 0`로 웜 상태를 유지할 수 있지만, 공식 문서에 `do incur billing costs`라고 명시
- billing account 필요

### 총평

`완전 무료 + 항상 켜짐`에는 안 맞는다.  
`호출형 API`에는 아주 좋다.

## 5. Railway Free

### 장점

- 공식 docs 기준 Free plan이 다시 존재함
- `월 $1 free credit`
- Python 서비스 배포 가능
- Serverless sleep 기능 존재

### 단점

- Free는 결국 `$1/month` 크레딧 기반
- 공식 docs 기준 RAM은 `$10 / GB / month`, CPU는 `$20 / vCPU / month`
- 즉 상시 떠 있는 서버는 무료 크레딧으로 유지되기 사실상 어렵다
- free/trial 플랜은 restart policy에도 제한이 있음
- trial은 30일이고, verification 상태에 따라 outbound network restriction이 생길 수 있음

### 총평

`영생 무료 always-on` 용도로는 부적합하다.  
짧게 테스트하는 건 가능하지만 장기 장난감 서버로는 애매하다.

## 6. PythonAnywhere Free

### 장점

- Python 특화 플랫폼이라 쓰기 쉽다
- 무료 계정이 계속 존재함

### 단점

- 공식 free account features 기준 `1 web app with 1 month expiry`
- free 계정 outbound access는 allowlist 방식
- help 문서에 free users are restricted to `HTTP/HTTPS only, to an allowlist of sites`
- always-on task는 공식 help 기준 `paid account` 기능

### 총평

이번 프로젝트엔 비추천.  
특히 증권사 API처럼 외부 호출이 중요한 서비스와 잘 안 맞는다.

## 한눈에 비교

| 서비스 | 무료 지속성 | 24시간 상시 실행 | 슬립 여부 | 외부 API 제약 | 총평 |
| --- | --- | --- | --- | --- | --- |
| Oracle Always Free VM | 가장 강함 | 가능 | 없음(직접 운영) | 거의 없음 | 최우선 |
| Render Free Web Service | 계속 가능 | 불가 | 15분 idle 후 sleep | 일반 outbound 가능 | 데모용 |
| Koyeb | 가격 정책 재확인 필요 | 불가 | inactivity 시 sleep | 일반 outbound 가능 | 보류 |
| Cloud Run | 무료 한도 기반 | 기본 불가 | 기본 scale-to-zero | 일반 outbound 가능 | 호출형 API |
| Railway Free | $1/mo credit 기반 | 사실상 불가 | serverless sleep 가능 | trial verification 제약 가능 | 테스트용 |
| PythonAnywhere Free | 계속 존재 | 불가 | always-on 없음 | allowlist 제한 | 비추천 |

## 최종 추천

`영생 무료`를 진짜로 우선하면:

1. `Oracle Cloud Always Free VM`
2. 그게 너무 귀찮으면 `Render` 또는 `Koyeb`
3. `Cloud Run`은 무료지만 항상 켜진 서버 관점에서는 아님

즉 네 조건대로라면 답은 거의 하나다.

`Python 호스팅은 Oracle Cloud Always Free VM이 제일 맞다.`

## 공식 문서

- Oracle Cloud Free Tier: https://www.oracle.com/cloud/free/
- Oracle Always Free Resources: https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Render Free: https://render.com/free
- Render Your First Deploy: https://render.com/docs/your-first-deploy
- Koyeb Pricing: https://www.koyeb.com/pricing/
- Koyeb Deployments Reference: https://www.koyeb.com/docs/reference/deployments
- Google Cloud Free Tier: https://docs.cloud.google.com/free/docs/free-cloud-features
- Cloud Run Autoscaling: https://cloud.google.com/run/docs/about-instance-autoscaling
- Cloud Run Minimum Instances: https://cloud.google.com/run/docs/configuring/min-instances
- Railway Pricing Plans: https://docs.railway.com/reference/pricing/plans
- Railway Free Trial: https://docs.railway.com/reference/pricing/free-trial
- Railway Serverless Sleep: https://docs.railway.com/reference/app-sleeping
- Railway Restart Policy: https://docs.railway.com/deployments/restart-policy
- PythonAnywhere Free Accounts Features: https://help.pythonanywhere.com/pages/FreeAccountsFeatures/
- PythonAnywhere Always-on Tasks: https://help.pythonanywhere.com/pages/AlwaysOnTasks/
- PythonAnywhere Free User Networking Limits: https://help.pythonanywhere.com/pages/SMTPForFreeUsers/
