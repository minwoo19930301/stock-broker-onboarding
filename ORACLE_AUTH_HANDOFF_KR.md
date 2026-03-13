# Oracle 인증 handoff

지금부터 역할을 이렇게 나누면 된다.

## 네가 할 일

딱 이것만 하면 된다.

1. Oracle Cloud 회원가입
2. 결제수단/본인인증/OTP 등 사람 인증 완료
3. 이 맥에서 아래 명령 실행

```bash
cd "/Users/minwokim/Documents/New project"
stock-broker-onboarding/.tools/oci-cli/bin/oci setup config
```

이 명령이 묻는 값:

- `user OCID`
- `tenancy OCID`
- `region`
- API signing key 경로

키 생성 질문이 나오면 보통 `Yes`로 진행하면 된다.

완료되면 보통 아래 파일이 생긴다.

- `~/.oci/config`
- `~/.oci/oci_api_key.pem`

## 내가 할 일

네가 위 auth 설정만 끝내고 `다 됐다`고 말하면, 그 다음부터는 내가 이어서 한다.

1. OCI CLI로 현재 계정/리전 확인
2. VM shape / image / subnet 조회
3. Always Free VM 생성 명령 작성 또는 실행
4. 공인 IP/보안 규칙 확인
5. FastAPI 배포
6. systemd / nginx 등록
7. health check 확인

## 이미 준비된 것

- 로컬 OCI CLI: [stock-broker-onboarding/.tools/oci-cli/bin/oci](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/.tools/oci-cli/bin/oci)
- Oracle 배포 문서: [ORACLE_ALWAYS_FREE_DEPLOY_KR.md](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/ORACLE_ALWAYS_FREE_DEPLOY_KR.md)
- FastAPI 백엔드: [backend/app/main.py](/Users/minwokim/Documents/New%20project/stock-broker-onboarding/backend/app/main.py)

## 참고

`oci` CLI 버전:

```bash
stock-broker-onboarding/.tools/oci-cli/bin/oci --version
```
