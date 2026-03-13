const STORAGE_KEY = "stock-broker-onboarding-drafts-v1";

const STATUS_META = {
  ready: {
    label: "바로 연결 가능",
    description: "개인 고객 셀프 신청 가능",
    className: "status-ready",
  },
  partner: {
    label: "제휴형",
    description: "회사 단위 승인 필요",
    className: "status-partner",
  },
  limited: {
    label: "레거시/확인 필요",
    description: "공개 문서는 있으나 흐름이 불균일",
    className: "status-limited",
  },
  unavailable: {
    label: "공개 주문 API 미확인",
    description: "공개 주문 API 또는 허용 정책 미확인",
    className: "status-unavailable",
  },
};

const CAPABILITY_META = {
  yes: { label: "가능", className: "cap-yes" },
  partner: { label: "제휴형", className: "cap-partner" },
  limited: { label: "확인 필요", className: "cap-limited" },
  no: { label: "미지원", className: "cap-no" },
};

const FILTERS = [
  { id: "all", label: "전체" },
  { id: "ready", label: "바로 연결" },
  { id: "partner", label: "제휴형" },
  { id: "limited", label: "레거시" },
  { id: "unavailable", label: "미지원" },
];

const BROKERS = [
  {
    id: "kiwoom",
    name: "키움증권",
    subtitle: "REST API",
    status: "ready",
    audience: "개인 고객 self-service",
    summary:
      "국내주식 자동매매 MVP에 가장 바로 붙이기 좋은 공개형 REST API입니다. 계좌 단위 App Key/App Secret을 발급받고, 서버 고정 IP를 사전에 등록해야 합니다.",
    fit: "국내주식 중심 MVP / 조건검색 전략 / 기존 키움 고객 흡수",
    onboardingMode: "계좌 단위 App Key / App Secret",
    capability: {
      quote: "yes",
      buy: "yes",
      sell: "yes",
      balance: "yes",
    },
    fields: [
      {
        key: "environment",
        label: "운영 환경",
        type: "select",
        required: true,
        help: "실전투자와 모의투자 App Key는 서로 다릅니다.",
        options: [
          { value: "production", label: "실전투자" },
          { value: "mock", label: "모의투자" },
        ],
      },
      {
        key: "accountNumber",
        label: "계좌번호",
        type: "text",
        placeholder: "예: 1234567890",
        required: true,
        help: "등록을 마친 실제 주문 계좌번호를 입력합니다.",
      },
      {
        key: "appKey",
        label: "App Key",
        type: "password",
        placeholder: "키움 포털에서 1회 다운로드",
        required: true,
        help: "계좌 App Key 관리 화면에서 다운로드한 값",
      },
      {
        key: "appSecret",
        label: "App Secret",
        type: "password",
        placeholder: "키움 포털에서 1회 다운로드",
        required: true,
        help: "계좌 App Secret 관리 화면에서 다운로드한 값",
      },
      {
        key: "allowedIp",
        label: "허용 IP",
        type: "text",
        placeholder: "예: 203.0.113.10",
        required: true,
        help: "키움 포털에 미리 등록한 서버의 고정 공인 IP",
      },
      {
        key: "accountPassword",
        label: "계좌 비밀번호",
        type: "password",
        placeholder: "포털의 계좌 등록 시 사용한 비밀번호",
        required: false,
        help: "일부 주문/계좌 등록 흐름 확인용 메모로만 보관",
      },
    ],
    steps: [
      "키움증권 계좌를 개설합니다.",
      "REST API 포털의 `API 사용신청`에서 로그인 후 약관 동의를 완료합니다.",
      "실전 또는 모의 계좌용 `계좌 App Key 관리` 화면으로 이동합니다.",
      "주문을 실행할 서버의 고정 IP를 등록합니다. 키움은 허용된 IP에서만 인증을 허용합니다.",
      "계좌 등록하기에서 계좌 비밀번호와 SMS 인증을 완료합니다.",
      "App Key/App Secret 파일을 1회 다운로드합니다.",
      "OAuth 접근 토큰을 발급받아 시세, 주문, 잔고 API 호출에 사용합니다.",
    ],
    notices: [
      "App Key/App Secret 다운로드는 1회만 가능하므로 별도 금고에 보관해야 합니다.",
      "허용 IP는 최대 10개까지 등록 가능합니다.",
      "모의투자 도메인은 KRX만 지원한다는 점이 공식 문서에 명시되어 있습니다.",
    ],
    sources: [
      {
        label: "키움 REST API 이용안내",
        url: "https://openapi.kiwoom.com/intro/serviceInfo",
      },
      {
        label: "키움 OAuth 가이드",
        url: "https://openapi.kiwoom.com/guide/apiguide",
      },
      {
        label: "키움 REST API 소개",
        url: "https://openapi.kiwoom.com/",
      },
    ],
  },
  {
    id: "kis",
    name: "한국투자증권",
    subtitle: "Open API",
    status: "ready",
    audience: "개인/법인 self-use",
    summary:
      "문서, 테스트베드, GitHub 샘플이 가장 잘 정리된 편입니다. 국내주식뿐 아니라 해외주식, 선물옵션, 채권까지 공개 문서 범위가 넓습니다.",
    fit: "문서 품질 우선 / 해외주식 확장 / 빠른 프로토타이핑",
    onboardingMode: "계좌 App Key / App Secret + 선택적 HTS ID",
    capability: {
      quote: "yes",
      buy: "yes",
      sell: "yes",
      balance: "yes",
    },
    fields: [
      {
        key: "environment",
        label: "운영 환경",
        type: "select",
        required: true,
        help: "실전과 모의투자용 키를 구분해 두는 편이 안전합니다.",
        options: [
          { value: "production", label: "실전투자" },
          { value: "mock", label: "모의투자" },
        ],
      },
      {
        key: "accountPrefix",
        label: "계좌번호 앞 8자리",
        type: "text",
        placeholder: "예: 12345678",
        required: true,
        help: "KIS 샘플 구조에서 CANO에 해당합니다.",
      },
      {
        key: "accountProductCode",
        label: "계좌 상품코드 뒤 2자리",
        type: "text",
        placeholder: "예: 01",
        required: true,
        help: "KIS 샘플 구조에서 ACNT_PRDT_CD에 해당합니다.",
      },
      {
        key: "appKey",
        label: "App Key",
        type: "password",
        placeholder: "한국투자 API 신청 후 발급",
        required: true,
        help: "REST 토큰 발급에 사용됩니다.",
      },
      {
        key: "appSecret",
        label: "App Secret",
        type: "password",
        placeholder: "한국투자 API 신청 후 발급",
        required: true,
        help: "REST 토큰 발급에 사용됩니다.",
      },
      {
        key: "htsId",
        label: "HTS ID",
        type: "text",
        placeholder: "선택 입력",
        required: false,
        help: "체결통보, 일부 웹소켓/조건 목록 확인용으로 필요할 수 있습니다.",
      },
    ],
    steps: [
      "한국투자증권 계좌를 개설하고 계정 ID 연결을 마칩니다.",
      "한국투자 홈페이지 또는 앱에서 Open API 서비스를 신청합니다.",
      "App Key와 App Secret을 발급받습니다.",
      "REST 호출 시에는 계좌 App Key/App Secret으로 토큰을 발급받습니다.",
      "실시간 웹소켓을 쓸 경우 접속키와 HTS ID가 필요한 흐름을 따릅니다.",
      "테스트베드와 GitHub 샘플 코드로 시세/주문/잔고 흐름을 먼저 검증합니다.",
    ],
    notices: [
      "개인/법인은 본인 자산을 매매하는 목적의 self-use 흐름이 공식 문서에 정리되어 있습니다.",
      "고객 대상 제3자 서비스는 제휴/규제 검토가 별도로 필요하며, 공식 제휴 안내에는 제도권 금융회사만 대상이라고 적혀 있습니다.",
      "실시간 웹소켓을 붙일 경우 HTS ID 정확성을 별도로 확인해야 합니다.",
    ],
    sources: [
      {
        label: "한국투자 Open API 포털",
        url: "https://apiportal.koreainvestment.com/intro",
      },
      {
        label: "한국투자 제휴/대상 안내",
        url: "https://apiportal.koreainvestment.com/provider-apply",
      },
      {
        label: "한국투자 공식 GitHub 샘플",
        url: "https://github.com/koreainvestment/open-trading-api",
      },
    ],
  },
  {
    id: "db",
    name: "DB증권",
    subtitle: "OPEN API",
    status: "ready",
    audience: "개인/법인 self-service",
    summary:
      "계좌 개설, Open API 신청, 토큰 발급 절차가 공개 문서에 비교적 자세히 열려 있습니다. 국내주식, 해외주식, 선물옵션, 채권, 실시간 시세까지 범위가 넓습니다.",
    fit: "국내+해외 상품 범위 확보 / 절차 문서가 명확한 증권사 추가",
    onboardingMode: "계좌 단위 App Key / App Secret",
    capability: {
      quote: "yes",
      buy: "yes",
      sell: "yes",
      balance: "yes",
    },
    fields: [
      {
        key: "environment",
        label: "운영 환경",
        type: "select",
        required: true,
        help: "모의투자 키는 별도 발급됩니다.",
        options: [
          { value: "production", label: "실전투자" },
          { value: "mock", label: "모의투자" },
        ],
      },
      {
        key: "accountNumber",
        label: "계좌번호",
        type: "text",
        placeholder: "예: 1234567890",
        required: true,
        help: "Open API 신청을 완료한 계좌번호",
      },
      {
        key: "accountPassword",
        label: "계좌 비밀번호",
        type: "password",
        placeholder: "선택 입력",
        required: false,
        help: "일부 계좌성 API에서 요구될 수 있어 내부 금고 저장 필요",
      },
      {
        key: "appKey",
        label: "App Key",
        type: "password",
        placeholder: "DB증권 홈페이지에서 확인",
        required: true,
        help: "OPEN API 신청 완료 후 발급된 키",
      },
      {
        key: "appSecret",
        label: "App Secret",
        type: "password",
        placeholder: "DB증권 홈페이지에서 확인",
        required: true,
        help: "OPEN API 신청 완료 후 발급된 시크릿",
      },
    ],
    steps: [
      "DB증권 계좌를 개설합니다.",
      "DB증권 홈페이지에 공동인증서로 로그인합니다.",
      "`온라인지점 > OpenAPI > OpenAPI 신청`으로 이동합니다.",
      "신청 가능한 계좌 상태를 확인하고 사용할 계좌를 선택해 신청합니다. 공식 문서에는 최대 3계좌까지 신청 가능하다고 안내됩니다.",
      "신청 완료 후 App Key와 App Secret을 확인합니다.",
      "OAuth 토큰을 발급받고 시세/주문/잔고 API에 사용합니다.",
    ],
    notices: [
      "공식 문서 기준으로 개인 App Key/App Secret 유효기간은 신청일로부터 1년입니다.",
      "접근 토큰 유효기간은 발급 시점부터 24시간입니다.",
      "모의투자 키는 실전투자와 별도로 발급됩니다.",
    ],
    sources: [
      {
        label: "DB증권 이용절차 안내",
        url: "https://openapi.db-fi.com/howto-use",
      },
      {
        label: "DB증권 API 서비스 목록",
        url: "https://openapi.db-fi.com/apiservice",
      },
      {
        label: "DB증권 테스트베드 콘솔",
        url: "https://openapi.db-fi.com/testbed-console",
      },
    ],
  },
  {
    id: "ls",
    name: "LS증권",
    subtitle: "OPEN API",
    status: "ready",
    audience: "개인/법인 self-service",
    summary:
      "LS증권은 xingAPI 신청 후 OPEN API를 신청하는 2단계 구조입니다. 공개 문서에서 투자정보, 계좌정보, 매매주문과 테스트베드를 모두 확인할 수 있습니다.",
    fit: "계좌/주문 중심 API 추가 / 테스트베드 기반 검증",
    onboardingMode: "계좌 단위 App Key / App Secret",
    capability: {
      quote: "yes",
      buy: "yes",
      sell: "yes",
      balance: "yes",
    },
    fields: [
      {
        key: "environment",
        label: "운영 환경",
        type: "select",
        required: true,
        help: "실전/모의 구분을 같이 기록합니다.",
        options: [
          { value: "production", label: "실전투자" },
          { value: "mock", label: "모의투자" },
        ],
      },
      {
        key: "accountNumber",
        label: "계좌번호",
        type: "text",
        placeholder: "예: 1234567890",
        required: true,
        help: "OPEN API 사용신청을 마친 계좌번호",
      },
      {
        key: "accountPassword",
        label: "계좌 비밀번호",
        type: "password",
        placeholder: "선택 입력",
        required: false,
        help: "공식 이용안내에 계좌번호/계좌비밀번호 조회 흐름이 함께 언급됩니다.",
      },
      {
        key: "appKey",
        label: "App Key",
        type: "password",
        placeholder: "LS증권 신청 완료 후 수신",
        required: true,
        help: "이메일 또는 신청 결과 화면에서 받은 App Key",
      },
      {
        key: "appSecret",
        label: "App Secret",
        type: "password",
        placeholder: "LS증권 신청 완료 후 수신",
        required: true,
        help: "이메일 또는 신청 결과 화면에서 받은 App Secret",
      },
    ],
    steps: [
      "LS증권 계좌를 개설합니다.",
      "LS증권 홈페이지에 공동인증서로 로그인합니다.",
      "`고객센터 > 매매시스템 > API > 사용등록/해지`에서 xingAPI를 먼저 신청합니다.",
      "이후 OPEN API 사용신청을 진행하고 계좌 단위 App Key/App Secret을 발급받습니다.",
      "OAuth 접근 토큰을 발급받습니다. 공식 문서 예시는 `grant_type=client_credentials`와 `scope=oob`를 사용합니다.",
      "테스트베드 개발자 콘솔에서 호출을 검증한 뒤 실제 주문 로직에 연결합니다.",
    ],
    notices: [
      "공식 문서에 xingAPI 신청 후 OPEN API 신청이 필수라고 명시되어 있습니다.",
      "접근 토큰은 익일 07시까지 유효하므로 매일 재발급 전략이 필요합니다.",
      "법인 이용자는 별도 제휴 승인 절차가 필요할 수 있습니다.",
    ],
    sources: [
      {
        label: "LS증권 OPEN API 소개",
        url: "https://openapi.ls-sec.co.kr/about-openapi",
      },
      {
        label: "LS증권 OPEN API 이용안내",
        url: "https://openapi.ls-sec.co.kr/howto-use",
      },
      {
        label: "LS증권 테스트베드 소개",
        url: "https://openapi.ls-sec.co.kr/testbed-intro",
      },
    ],
  },
  {
    id: "kb",
    name: "KB증권",
    subtitle: "핀테크스토어",
    status: "partner",
    audience: "회사 단위 파트너",
    summary:
      "오픈 API 자체는 존재하지만, 공개 문서 기준으로 기관 유형 선택과 관리자 승인, 제휴 검토를 거치는 파트너 구조입니다. 개인 투자자 셀프 입력형으로는 바로 열기 어렵습니다.",
    fit: "회사 제휴가 이미 있는 경우",
    onboardingMode: "기관 승인 후 제휴형",
    capability: {
      quote: "partner",
      buy: "partner",
      sell: "partner",
      balance: "partner",
    },
    steps: [
      "기관 유형을 선택하여 가입 신청합니다.",
      "관리자 승인 후 API 마켓, 개발 가이드, 테스트베드 사용이 가능합니다.",
      "제휴 혜택 소개 페이지에는 주식 주문, 시세 조회, 잔고 확인 등 핵심 API가 파트너사 앱에 제공된다고 안내됩니다.",
    ],
    notices: [
      "개인 고객 self-service 흐름이 아니라 파트너사 승인 모델입니다.",
      "회사 자료와 연락처를 보내고 검토받는 제휴 절차가 공식 페이지에 명시되어 있습니다.",
    ],
    sources: [
      {
        label: "KB증권 오픈 API 마켓",
        url: "https://store.kbsec.com/open-api-market",
      },
      {
        label: "KB증권 파트너 제휴 안내",
        url: "https://store.kbsec.com/aboutpartner",
      },
      {
        label: "KB증권 제휴 등록",
        url: "https://store.kbsec.com/register",
      },
    ],
  },
  {
    id: "nh",
    name: "NH투자증권",
    subtitle: "QV Open API",
    status: "limited",
    audience: "레거시/개별 검증 필요",
    summary:
      "NH는 QV Open API와 Auto 트레이드 안내가 존재하지만, 현재 공개 문서 표면은 키움/KIS/DB/LS 대비 덜 일관됩니다. 우선은 조사 대상에 포함하고, 추후 어댑터를 붙일 때 세부 인증 흐름을 따로 검증하는 편이 안전합니다.",
    fit: "후순위 조사 대상",
    onboardingMode: "추가 검증 필요",
    capability: {
      quote: "limited",
      buy: "limited",
      sell: "limited",
      balance: "limited",
    },
    steps: [
      "공개 페이지에서 `QV Open API`와 `NH Trader Auto 트레이드` 안내를 확인할 수 있습니다.",
      "실제 주문 어댑터를 만들기 전에는 인증 수단, 토큰 정책, 배포 제약을 별도로 검증해야 합니다.",
    ],
    notices: [
      "바로 사용자 입력 폼을 열어도 되는 수준의 공개 신청 문서를 아직 충분히 확인하지 못했습니다.",
      "초기 MVP에서는 키움/KIS/DB/LS를 먼저 붙이고 NH는 후속 확장으로 두는 편이 낫습니다.",
    ],
    sources: [
      {
        label: "NH QV 사이트",
        url: "https://wts.nhqv.com/",
      },
      {
        label: "NH QV Open API 안내 진입",
        url: "https://directtrading.nhqv.com/main?nexturl=/quics?page=C040606",
      },
    ],
  },
  {
    id: "toss",
    name: "토스 / 토스증권",
    subtitle: "앱인토스 / 공개 주문 API 미확인",
    status: "unavailable",
    audience: "플랫폼 정책 제한",
    summary:
      "토스 개발자 문서는 앱인토스와 로그인, 인증 같은 플랫폼 기능을 제공하지만, 토스증권 외부 공개 주문 API는 현재 공개 문서에서 확인되지 않았습니다.",
    fit: "주문 엔진 기반으로는 비추천",
    onboardingMode: "공개 주문 API 미확인",
    capability: {
      quote: "no",
      buy: "no",
      sell: "no",
      balance: "no",
    },
    steps: [
      "앱인토스는 미니앱을 토스 앱 안에서 서비스하는 플랫폼입니다.",
      "공식 서비스 오픈 정책에는 금융 상품 중개/판매/광고와 투자 자문, 리딩방, 유료 정보 제공 서비스가 출시 불가 항목으로 명시되어 있습니다.",
    ],
    notices: [
      "토스 앱 안에 자동매매 서비스를 넣는 방향은 현재 정책과 맞지 않습니다.",
      "토스 로그인이나 인증은 별도 UX 요소로 검토할 수 있지만, 주문 실행 브로커로 쓰기에는 공개 근거가 부족합니다.",
    ],
    sources: [
      {
        label: "앱인토스 개요",
        url: "https://developers-apps-in-toss.toss.im/intro/overview.html",
      },
      {
        label: "앱인토스 서비스 오픈 정책",
        url: "https://developers-apps-in-toss.toss.im/intro/guide.html",
      },
    ],
  },
  {
    id: "kakaopay",
    name: "카카오페이 / 카카오페이증권",
    subtitle: "공개 주문 API 미확인",
    status: "unavailable",
    audience: "소비자 앱은 있으나 외부 API 공개 근거 부족",
    summary:
      "카카오페이증권의 소비자용 투자 서비스는 존재하고 자동투자 기능도 소개되어 있지만, 개발자 문서는 결제 API 중심으로 보입니다. 외부 개발자가 붙일 수 있는 공개 주식 주문 API는 확인되지 않았습니다.",
    fit: "주문 브로커 기반으로는 비추천",
    onboardingMode: "공개 주문 API 미확인",
    capability: {
      quote: "no",
      buy: "no",
      sell: "no",
      balance: "no",
    },
    steps: [
      "카카오페이 투자 서비스 페이지는 투자 기능이 카카오페이증권에서 제공된다고 안내합니다.",
      "같은 시점 개발자센터 공개 문서는 온라인 결제 API 위주입니다.",
    ],
    notices: [
      "카카오페이는 투자 서비스 및 상품 판매·중개에 관여하지 않는다고 공식 페이지에서 밝힙니다.",
      "자동매매용 외부 주문 API가 공개되기 전까지는 자체 주문 브로커로 쓰기 어렵습니다.",
    ],
    sources: [
      {
        label: "카카오페이 투자 서비스",
        url: "https://www.kakaopay.com/services/finance/investment",
      },
      {
        label: "카카오페이 개발자센터",
        url: "https://developers.kakaopay.com/",
      },
    ],
  },
  {
    id: "naverpay",
    name: "네이버페이",
    subtitle: "커머스/로그인 API 중심",
    status: "unavailable",
    audience: "증권 주문 API 공개 근거 없음",
    summary:
      "네이버 오픈 API는 로그인, 검색, 데이터랩 등 범용 기능과 커머스/결제 파트너 API 중심입니다. 공개 문서 기준으로 증권 주문/잔고 API는 확인되지 않았습니다.",
    fit: "프론트 로그인/결제는 검토 가능, 주문 브로커는 아님",
    onboardingMode: "증권 주문 API 미확인",
    capability: {
      quote: "no",
      buy: "no",
      sell: "no",
      balance: "no",
    },
    steps: [
      "네이버 개발자센터 공개 API 목록은 로그인, 검색, 캘린더, 데이터랩 등 범용 API를 안내합니다.",
      "네이버페이 파트너 API는 주문형 가맹점 등 결제/커머스용 흐름입니다.",
    ],
    notices: [
      "네이버페이는 증권 주문 엔진 대신 로그인/상거래 기능과 분리해서 봐야 합니다.",
      "범용 자동매매 서비스의 브로커 후보로는 적합하지 않습니다.",
    ],
    sources: [
      {
        label: "네이버 오픈 API 목록",
        url: "https://developers.naver.com/docs/common/openapiguide/apilist.md",
      },
      {
        label: "네이버페이 파트너 API",
        url: "https://api.pay.naver.com/npay/partner",
      },
    ],
  },
];

const state = {
  filter: "all",
  selectedId: BROKERS[0].id,
  drafts: loadDrafts(),
};

const summaryCardsEl = document.getElementById("summaryCards");
const filterPillsEl = document.getElementById("filterPills");
const brokerListEl = document.getElementById("brokerList");
const brokerDetailEl = document.getElementById("brokerDetail");

renderApp();

filterPillsEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) {
    return;
  }

  state.filter = button.dataset.filter;
  const visibleBrokers = getVisibleBrokers();
  if (!visibleBrokers.some((broker) => broker.id === state.selectedId)) {
    state.selectedId = visibleBrokers[0]?.id ?? BROKERS[0].id;
  }
  renderApp();
});

brokerListEl.addEventListener("click", (event) => {
  const card = event.target.closest("[data-broker-id]");
  if (!card) {
    return;
  }

  state.selectedId = card.dataset.brokerId;
  renderDetail();
  renderBrokerList();
});

brokerDetailEl.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) {
    return;
  }

  const broker = getSelectedBroker();
  if (!broker) {
    return;
  }

  if (target.dataset.action === "save-draft") {
    const form = document.getElementById(`form-${broker.id}`);
    if (!form) {
      return;
    }
    const values = serializeForm(form, broker.fields);
    state.drafts[broker.id] = values;
    persistDrafts();
    showHelperMessage(`${broker.name} 설정을 이 브라우저에 임시 저장했습니다.`);
  }

  if (target.dataset.action === "clear-draft") {
    delete state.drafts[broker.id];
    persistDrafts();
    renderDetail();
    showHelperMessage(`${broker.name} 저장값을 비웠습니다.`);
  }

  if (target.dataset.action === "export-json") {
    const form = document.getElementById(`form-${broker.id}`);
    if (!form) {
      return;
    }
    const values = serializeForm(form, broker.fields);
    downloadJson(`${broker.id}-credentials.json`, {
      brokerId: broker.id,
      brokerName: broker.name,
      exportedAt: new Date().toISOString(),
      values,
    });
    showHelperMessage(`${broker.name} 설정을 JSON으로 내보냈습니다.`);
  }
});

function renderApp() {
  renderSummary();
  renderFilters();
  renderBrokerList();
  renderDetail();
}

function renderSummary() {
  const counts = BROKERS.reduce(
    (accumulator, broker) => {
      accumulator.total += 1;
      accumulator[broker.status] += 1;
      return accumulator;
    },
    { total: 0, ready: 0, partner: 0, limited: 0, unavailable: 0 },
  );

  summaryCardsEl.innerHTML = [
    {
      label: "전체 증권사/앱",
      value: counts.total,
      note: "현재 목록에 포함된 대상",
    },
    {
      label: "바로 연결 가능",
      value: counts.ready,
      note: "self-service 공개 API 확인",
    },
    {
      label: "제휴형/레거시",
      value: counts.partner + counts.limited,
      note: "회사 승인 또는 추가 검증 필요",
    },
    {
      label: "공개 주문 API 미확인",
      value: counts.unavailable,
      note: "화면에는 사유만 우선 표시",
    },
  ]
    .map(
      (card) => `
        <div class="summary-card">
          <span>${card.label}</span>
          <strong>${card.value}</strong>
          <span>${card.note}</span>
        </div>
      `,
    )
    .join("");
}

function renderFilters() {
  filterPillsEl.innerHTML = FILTERS.map(
    (filter) => `
      <button
        type="button"
        class="filter-pill ${state.filter === filter.id ? "is-active" : ""}"
        data-filter="${filter.id}"
      >
        ${filter.label}
      </button>
    `,
  ).join("");
}

function renderBrokerList() {
  const visibleBrokers = getVisibleBrokers();

  brokerListEl.innerHTML = visibleBrokers
    .map((broker) => {
      const status = STATUS_META[broker.status];
      const capabilities = [
        { label: "시세", value: broker.capability.quote },
        { label: "매수", value: broker.capability.buy },
        { label: "매도", value: broker.capability.sell },
        { label: "잔고", value: broker.capability.balance },
      ];

      return `
        <button
          type="button"
          class="broker-card ${broker.id === state.selectedId ? "is-selected" : ""}"
          data-broker-id="${broker.id}"
        >
          <div class="broker-head">
            <div class="broker-name-wrap">
              <h3 class="broker-name">${broker.name}</h3>
              <p class="broker-subtitle">${broker.subtitle}</p>
            </div>
            <span class="status-badge ${status.className}">${status.label}</span>
          </div>
          <p class="broker-summary">${broker.summary}</p>
          <div class="cap-grid-compact">
            ${capabilities
              .map((item) => {
                const meta = CAPABILITY_META[item.value];
                return `
                 <div class="compact-item">
                    <span>${item.label}</span>
                    <strong class="cap-pill ${meta.className}">${meta.label}</strong>
                  </div>
                `;
              })
              .join("")}
          </div>
        </button>
      `;
    })
    .join("");
}

function renderDetail() {
  const broker = getSelectedBroker();
  if (!broker) {
    brokerDetailEl.innerHTML = `
      <div class="empty-state">
        <h3>표시할 증권사가 없습니다.</h3>
        <p>현재 필터에 맞는 대상이 없습니다. 다른 필터를 선택해 보세요.</p>
      </div>
    `;
    return;
  }

  const status = STATUS_META[broker.status];
  const draft = state.drafts[broker.id] ?? {};
  const capabilityCards = [
    { key: "quote", label: "주식 확인" },
    { key: "buy", label: "주식 사기" },
    { key: "sell", label: "주식 팔기" },
    { key: "balance", label: "계좌 잔고 확인" },
  ];

  brokerDetailEl.innerHTML = `
    <article class="detail-card">
      <section class="detail-hero">
        <div class="detail-topline">
          <p class="section-label">Broker Detail</p>
          <span class="status-badge ${status.className}">${status.label}</span>
          <span class="mini-badge">${broker.audience}</span>
        </div>
        <h2 class="detail-title">${broker.name}</h2>
        <p class="detail-summary">${broker.summary}</p>
        <div class="callout-strip">
          <div class="callout">
            <span>적합한 용도</span>
            <strong>${broker.fit}</strong>
          </div>
          <div class="callout">
            <span>온보딩 방식</span>
            <strong>${broker.onboardingMode}</strong>
          </div>
          <div class="callout">
            <span>저장 상태</span>
            <strong>${draft && Object.keys(draft).length > 0 ? "임시 저장값 있음" : "아직 저장 없음"}</strong>
          </div>
        </div>
      </section>

      <section class="capability-matrix">
        ${capabilityCards
          .map((item) => {
            const meta = CAPABILITY_META[broker.capability[item.key]];
            return `
              <div class="capability-card">
                <h3>${item.label}</h3>
                <span class="cap-pill ${meta.className}">${meta.label}</span>
              </div>
            `;
          })
          .join("")}
      </section>

      <section class="detail-grid">
        <div class="stack-card">
          <h3>신청 가이드</h3>
          <ol class="guide-list">
            ${broker.steps.map((step) => `<li>${step}</li>`).join("")}
          </ol>
        </div>

        ${renderCredentialPanel(broker, draft)}
      </section>

      <section class="detail-grid">
        <div class="stack-card">
          <h3>주의사항</h3>
          <ul class="note-list">
            ${broker.notices.map((note) => `<li>${note}</li>`).join("")}
          </ul>
        </div>
        <div class="stack-card">
          <h3>공식 링크</h3>
          <ul class="source-list">
            ${broker.sources
              .map(
                (source) =>
                  `<li><a class="inline-link" href="${source.url}" target="_blank" rel="noreferrer">${source.label}</a></li>`,
              )
              .join("")}
          </ul>
        </div>
      </section>
    </article>
  `;
}

function renderCredentialPanel(broker, draft) {
  if (broker.status !== "ready") {
    const status = STATUS_META[broker.status];
    return `
      <div class="stack-card">
        <h3>계정/API 입력</h3>
        <div class="empty-state">
          <h3>${status.label}</h3>
          <p>
            ${status.description} 상태라서, 현재 버전에서는 이 증권사 전용 입력 폼을 열지 않았습니다.
            먼저 안내 문구와 공식 링크를 검토한 뒤, 실제 제휴 승인 또는 세부 인증 검증이 끝나면 전용 폼을 추가하는 흐름이 안전합니다.
          </p>
        </div>
      </div>
    `;
  }

  return `
    <div class="stack-card">
      <h3>계정/API 입력</h3>
      <p class="security-banner">
        현재는 <strong>브라우저 localStorage에만 임시 저장</strong>합니다.
        실서비스 전환 시에는 서버에서 KMS 또는 Secrets Manager로 암호화 저장해야 합니다.
      </p>
      <form id="form-${broker.id}">
        <div class="form-grid">
          ${broker.fields.map((field) => renderField(field, draft[field.key])).join("")}
        </div>
      </form>
      <div class="actions">
        <button type="button" class="action-btn action-primary" data-action="save-draft">이 브라우저에 임시 저장</button>
        <button type="button" class="action-btn action-secondary" data-action="export-json">JSON 내보내기</button>
        <button type="button" class="action-btn action-ghost" data-action="clear-draft">저장값 비우기</button>
      </div>
      <p id="helper-message" class="helper-text">
        서버 구현 전까지는 이 값을 실제 주문 키로 사용하지 말고, 화면 설계와 키 구조를 먼저 맞추는 용도로만 써주세요.
      </p>
    </div>
  `;
}

function renderField(field, value) {
  const required = field.required
    ? `<span class="required-mark">필수</span>`
    : `<span class="required-mark">선택</span>`;

  if (field.type === "select") {
    return `
      <div class="field">
        <label for="${field.key}">
          ${field.label}
          ${required}
        </label>
        <select id="${field.key}" name="${field.key}">
          ${field.options
            .map(
              (option) => `
                <option value="${option.value}" ${value === option.value ? "selected" : ""}>
                  ${option.label}
                </option>
              `,
            )
            .join("")}
        </select>
        <small>${field.help}</small>
      </div>
    `;
  }

  return `
    <div class="field">
      <label for="${field.key}">
        ${field.label}
        ${required}
      </label>
      <input
        id="${field.key}"
        name="${field.key}"
        type="${field.type}"
        value="${escapeAttribute(value ?? "")}"
        placeholder="${escapeAttribute(field.placeholder ?? "")}"
        autocomplete="off"
      />
      <small>${field.help}</small>
    </div>
  `;
}

function getVisibleBrokers() {
  if (state.filter === "all") {
    return BROKERS;
  }

  return BROKERS.filter((broker) => broker.status === state.filter);
}

function getSelectedBroker() {
  return BROKERS.find((broker) => broker.id === state.selectedId);
}

function loadDrafts() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function persistDrafts() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.drafts));
}

function serializeForm(form, fields) {
  const formData = new FormData(form);
  return fields.reduce((accumulator, field) => {
    accumulator[field.key] = formData.get(field.key) ?? "";
    return accumulator;
  }, {});
}

function downloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function showHelperMessage(message) {
  const helper = document.getElementById("helper-message");
  if (helper) {
    helper.textContent = message;
  }
}

function escapeAttribute(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
