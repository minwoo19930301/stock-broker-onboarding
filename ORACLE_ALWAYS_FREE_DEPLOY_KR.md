# Oracle Always Free 배포 가이드

이 문서는 `FastAPI 백엔드`를 `Oracle Cloud Always Free VM`에 올리는 기준 문서다.

전제:

- 이 프로젝트는 toy project
- Python 백엔드는 `FastAPI`
- 오라클 VM에 `24시간 켜진 서버`로 배포
- 프론트는 별도 정적 호스팅 또는 나중에 같은 VM에서 서빙 가능

## 왜 Oracle인가

공식 문서 기준:

- Always Free 리소스는 `for the life of the account`
- `VM.Standard.E2.1.Micro` 최대 2개 또는
- `VM.Standard.A1.Flex` 기준 월 `3,000 OCPU hours / 18,000 GB hours`
- Always Free tenancies 기준 `4 OCPUs / 24 GB memory` 상당

즉 무료 플랫폼 중에서 가장 `진짜 서버`에 가깝다.

주의:

- `Idle Always Free compute instances may be reclaimed`
- 너무 놀고 있으면 회수될 수 있다
- 항상 켜두는 것과 영원히 방치 가능한 것은 다르다

## 권장 인스턴스

우선순위:

1. `VM.Standard.A1.Flex`
2. 안 되면 `VM.Standard.E2.1.Micro`

이유:

- A1이 메모리와 CPU 여유가 훨씬 좋다
- FastAPI + nginx + 향후 worker까지 붙이기 편하다

운영체제:

- `Ubuntu 24.04 LTS` 또는 `Ubuntu 22.04 LTS`

## 오라클 콘솔에서 먼저 할 일

1. Always Free 가능한 홈 리전에 VM 생성
2. 공인 IP 할당
3. SSH 키 등록
4. VCN Security List 또는 NSG에 ingress 추가

권장 포트:

- `22/tcp` for SSH
- `80/tcp` for HTTP
- `443/tcp` for HTTPS

공식 네트워크 문서 기준으로 보안 규칙은 VCN의 Security List 또는 NSG에서 추가한다.

## 서버 접속 후 배포 순서

### 1. 저장소 가져오기

```bash
sudo mkdir -p /opt
sudo chown "$USER":"$USER" /opt
cd /opt
git clone <YOUR_REPO_URL> stock-broker-onboarding
cd stock-broker-onboarding
```

이미 파일을 올려둔 상태면 clone 대신 그대로 진행하면 된다.

### 2. 부트스트랩 스크립트 실행

```bash
cd /opt/stock-broker-onboarding
chmod +x infra/oracle/scripts/bootstrap_oracle_ubuntu.sh
APP_USER="$USER" \
SERVER_NAME="_" \
./infra/oracle/scripts/bootstrap_oracle_ubuntu.sh
```

기본 동작:

- apt 패키지 설치
- Python venv 생성
- requirements 설치
- `/etc/stock-broker-onboarding/api.env` 생성
- `systemd` 서비스 파일 설치
- `nginx` 사이트 설정 설치
- 서비스 시작 및 활성화

## 환경 변수 파일

기본 위치:

- `/etc/stock-broker-onboarding/api.env`

처음 생성되는 값은 [backend/.env.example](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/backend/.env.example)를 바탕으로 한다.

수정 후 반영:

```bash
sudo systemctl restart stock-broker-onboarding-api
```

## 서비스 확인

```bash
systemctl status stock-broker-onboarding-api
curl http://127.0.0.1:8000/healthz
curl http://<YOUR_PUBLIC_IP>/healthz
```

Swagger 문서:

- `http://<YOUR_PUBLIC_IP>/docs`

## 업데이트 배포

코드 변경 후:

```bash
cd /opt/stock-broker-onboarding
git pull
./infra/oracle/scripts/update_backend.sh
```

이 스크립트는:

- venv 유지
- requirements 재설치
- systemd 재시작

## HTTPS 붙이기

도메인이 있다면 nginx 위에 certbot을 얹으면 된다.

예시:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.example.com
```

이 경우 `SERVER_NAME`도 도메인으로 맞춰두는 편이 낫다.

## Oracle에서 자주 막히는 지점

### 1. 인스턴스 생성이 안 됨

공식 Always Free 문서에 `out of host capacity` 가능성이 적혀 있다.  
이 경우:

- 다른 Availability Domain 시도
- 시간 두고 재시도
- 다른 Always Free shape 시도

### 2. 포트를 열었는데 접속이 안 됨

둘 다 확인해야 한다.

- Oracle VCN Security List / NSG
- 서버 OS 방화벽 또는 nginx 상태

### 3. VM이 회수될까 걱정됨

공식 문서상 idle 회수 가능성은 있다.  
이건 단순 ping으로 해결된다고 장담할 수 없다.

현실적으로는:

- 실제 서비스 트래픽
- 주기적 작업
- 로그와 메트릭 확인

이런 정상적인 사용 패턴이 있는 편이 낫다.

## 포함된 배포 파일

- [infra/oracle/scripts/bootstrap_oracle_ubuntu.sh](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/infra/oracle/scripts/bootstrap_oracle_ubuntu.sh)
- [infra/oracle/scripts/update_backend.sh](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/infra/oracle/scripts/update_backend.sh)
- [infra/oracle/templates/stock-broker-onboarding-api.service.tpl](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/infra/oracle/templates/stock-broker-onboarding-api.service.tpl)
- [infra/oracle/templates/nginx-stock-broker-onboarding.conf.tpl](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/infra/oracle/templates/nginx-stock-broker-onboarding.conf.tpl)
- [backend/.env.example](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/backend/.env.example)

## 공식 문서

- [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)
- [Oracle Always Free Resources](https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Updating Rules in a Security List](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/update-securitylist.htm)
