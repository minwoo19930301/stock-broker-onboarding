#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import mimetypes
import os
import secrets
import time
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from backend.app.catalog import (
    BROKER_CATALOG,
    BROKER_DETAILS,
    CAPABILITY_META,
    STATUS_META,
    get_broker_or_none,
    validate_broker_values,
)


ROOT = Path(__file__).resolve().parent


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ROOT / ".env")

COOKIE_NAME = "stock_broker_wizard_v2"
BUILD_DATE = "2026-03-14"
PROJECT_TITLE = "AUTO STOCK TRADER(KR)"
PROJECT_SLUG = "auto-stock-trader-kr"
APP_BASE_URL = os.environ.get("APP_BASE_URL", "").strip()
READY_BROKERS = [broker for broker in BROKER_DETAILS if broker["status"] == "ready"]
MODAL_KEYS = {"broker", "symbol", "pattern", "ai"}
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "12"))

# Runtime-only stores for a toy project. They are reset when the process restarts.
OAUTH_PENDING: dict[str, dict] = {}
BROKER_SECRET_STORE: dict[str, dict[str, dict]] = {}
BROKER_BALANCE_CACHE: dict[str, dict] = {}
KIS_TOKEN_CACHE: dict[str, dict] = {}

AUTH_PROVIDERS = [
    {"value": "google", "label": "Google", "subtitle": "Google 계정으로 시작", "className": "auth-google", "email": "gmail.com", "icon": "G"},
    {"value": "kakao", "label": "Kakao", "subtitle": "카카오로 빠르게 시작", "className": "auth-kakao", "email": "kakao.com", "icon": "K"},
    {"value": "naver", "label": "Naver", "subtitle": "네이버 계정으로 연결", "className": "auth-naver", "email": "naver.com", "icon": "N"},
    {"value": "facebook", "label": "Facebook", "subtitle": "Facebook 계정으로 계속", "className": "auth-facebook", "email": "facebook.com", "icon": "f"},
]

PATTERN_OPTIONS = [
    {
        "value": "scheduled",
        "label": "정액 적립식",
        "description": "정해진 시간마다 같은 금액으로 반복 매수하거나 일부 매도합니다.",
    },
    {
        "value": "dip-buy",
        "label": "N% 하락 분할매수",
        "description": "기준 가격 대비 하락 폭이 커질 때마다 나눠서 진입합니다.",
    },
    {
        "value": "breakout",
        "label": "전고점 돌파",
        "description": "돌파 구간에서 진입하고 목표 수익 구간에서 분할 매도합니다.",
    },
    {
        "value": "golden-cross",
        "label": "이동평균 골든크로스",
        "description": "단기선과 장기선의 교차를 기준으로 자동 매매합니다.",
    },
    {
        "value": "rsi",
        "label": "RSI 과매도/과매수",
        "description": "정해진 RSI 값 기준으로 반응하는 정량 룰입니다.",
    },
]

SCHEDULE_OPTIONS = [
    {"value": "market-open", "label": "장 시작 직후"},
    {"value": "every-15m", "label": "15분마다"},
    {"value": "every-30m", "label": "30분마다"},
    {"value": "every-1h", "label": "1시간마다"},
    {"value": "daily", "label": "하루 1회"},
    {"value": "weekly", "label": "주 1회"},
]

AI_PROVIDERS = [
    {"value": "openai", "label": "OpenAI"},
    {"value": "anthropic", "label": "Anthropic"},
    {"value": "google", "label": "Google"},
    {"value": "openrouter", "label": "OpenRouter"},
    {"value": "custom", "label": "직접 입력"},
]

FLASH_MESSAGES = {
    "logged_in": {"kind": "success", "text": "로그인 세션을 시작했습니다."},
    "logged_out": {"kind": "success", "text": "로그아웃했습니다."},
    "sso_started": {"kind": "success", "text": "SSO 인증 페이지로 이동합니다."},
    "sso_not_configured": {"kind": "warning", "text": "선택한 SSO 제공사의 키 설정이 아직 없습니다."},
    "sso_failed": {"kind": "warning", "text": "SSO 인증에 실패했습니다. 다시 시도해 주세요."},
    "signed_up": {"kind": "success", "text": "회원가입이 완료되어 대시보드로 이동했습니다."},
    "find_id_requested": {"kind": "success", "text": "입력한 연락처 기준으로 아이디 안내 절차를 시작했습니다."},
    "find_password_requested": {"kind": "success", "text": "비밀번호 재설정 절차를 시작했습니다."},
    "reset": {"kind": "success", "text": "워크스페이스를 초기화했습니다."},
    "broker_added": {"kind": "success", "text": "증권 계좌를 추가했습니다."},
    "broker_removed": {"kind": "success", "text": "증권 연결을 삭제했습니다."},
    "broker_live_connected": {"kind": "success", "text": "브로커 API 연결 테스트를 통과했습니다."},
    "broker_live_warning": {"kind": "warning", "text": "브로커 연결은 저장했지만 실 API 호출은 실패했습니다. 키와 계좌를 다시 확인해 주세요."},
    "symbol_added": {"kind": "success", "text": "감시 종목을 추가했습니다."},
    "symbol_removed": {"kind": "success", "text": "종목과 연결된 규칙을 삭제했습니다."},
    "pattern_added": {"kind": "success", "text": "자동매매 패턴을 저장했습니다."},
    "pattern_removed": {"kind": "success", "text": "자동매매 패턴을 삭제했습니다."},
    "ai_saved": {"kind": "success", "text": "AI 전략 설정을 저장했습니다."},
    "ai_cleared": {"kind": "success", "text": "AI 전략 설정을 초기화했습니다."},
}

SYMBOL_LIBRARY = {
    "default": [
        {"symbol": "005930", "name": "삼성전자", "market": "KRX", "price": "73,400", "change": "+0.8%"},
        {"symbol": "000660", "name": "SK하이닉스", "market": "KRX", "price": "208,500", "change": "+1.9%"},
        {"symbol": "035420", "name": "NAVER", "market": "KRX", "price": "214,000", "change": "-0.3%"},
        {"symbol": "AAPL", "name": "Apple", "market": "NASDAQ", "price": "$212.51", "change": "+0.4%"},
        {"symbol": "NVDA", "name": "NVIDIA", "market": "NASDAQ", "price": "$918.42", "change": "+2.3%"},
    ],
    "kis": [
        {"symbol": "005930", "name": "삼성전자", "market": "KRX", "price": "73,400", "change": "+0.8%"},
        {"symbol": "005380", "name": "현대차", "market": "KRX", "price": "245,500", "change": "+1.0%"},
        {"symbol": "AAPL", "name": "Apple", "market": "NASDAQ", "price": "$212.51", "change": "+0.4%"},
        {"symbol": "MSFT", "name": "Microsoft", "market": "NASDAQ", "price": "$428.15", "change": "+0.7%"},
    ],
    "kiwoom": [
        {"symbol": "005930", "name": "삼성전자", "market": "KRX", "price": "73,400", "change": "+0.8%"},
        {"symbol": "000660", "name": "SK하이닉스", "market": "KRX", "price": "208,500", "change": "+1.9%"},
        {"symbol": "035720", "name": "카카오", "market": "KRX", "price": "57,300", "change": "-0.6%"},
        {"symbol": "251270", "name": "넷마블", "market": "KRX", "price": "59,600", "change": "+0.2%"},
    ],
    "db": [
        {"symbol": "005930", "name": "삼성전자", "market": "KRX", "price": "73,400", "change": "+0.8%"},
        {"symbol": "035420", "name": "NAVER", "market": "KRX", "price": "214,000", "change": "-0.3%"},
        {"symbol": "TSLA", "name": "Tesla", "market": "NASDAQ", "price": "$178.93", "change": "-1.1%"},
        {"symbol": "QQQ", "name": "Invesco QQQ", "market": "ETF", "price": "$442.80", "change": "+0.5%"},
    ],
    "ls": [
        {"symbol": "005930", "name": "삼성전자", "market": "KRX", "price": "73,400", "change": "+0.8%"},
        {"symbol": "068270", "name": "셀트리온", "market": "KRX", "price": "184,300", "change": "+1.3%"},
        {"symbol": "AMD", "name": "AMD", "market": "NASDAQ", "price": "$178.61", "change": "+1.4%"},
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "market": "ETF", "price": "$509.34", "change": "+0.2%"},
    ],
}


def fresh_draft() -> dict:
    return {
        "profile": {"nickname": "", "email": "", "phone": "", "auth_provider": "", "logged_in_at": "", "session_key": uuid4().hex},
        "brokers": [],
        "symbols": [],
        "patterns": [],
        "ai": {"provider": "", "model": "", "prompt": "", "has_api_key": False, "updated_at": ""},
        "oauth": {"last_state": "", "provider": "", "started_at": ""},
    }


def html(value: object) -> str:
    return escape(str(value), quote=True)


def trim(value: str | None, limit: int) -> str:
    return (value or "").strip()[:limit]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode_cookie_value(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cookie_value(encoded: str) -> dict:
    padding = "=" * (-len(encoded) % 4)
    raw = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
    return json.loads(raw.decode("utf-8"))


def load_draft(cookie_header: str | None) -> dict:
    draft = fresh_draft()
    if not cookie_header:
        return draft

    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:
        return draft

    morsel = jar.get(COOKIE_NAME)
    if not morsel:
        return draft

    try:
        stored = decode_cookie_value(morsel.value)
    except Exception:
        return draft

    if not isinstance(stored, dict):
        return draft

    merged = deepcopy(draft)
    merged["profile"].update(stored.get("profile", {}))
    merged["brokers"] = list(stored.get("brokers", []))[:8]
    merged["symbols"] = list(stored.get("symbols", []))[:20]
    merged["patterns"] = list(stored.get("patterns", []))[:20]
    merged["ai"].update(stored.get("ai", {}))
    merged["oauth"].update(stored.get("oauth", {}))
    if not merged["profile"].get("session_key"):
        merged["profile"]["session_key"] = uuid4().hex
    return merged


def draft_cookie_header(draft: dict) -> str:
    return f"{COOKIE_NAME}={encode_cookie_value(draft)}; Path=/; Max-Age=1209600; SameSite=Lax"


def clear_cookie_header() -> str:
    return f"{COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax"


def checked_attr(enabled: bool) -> str:
    return " checked" if enabled else ""


def selected_attr(current: str | None, expected: str) -> str:
    return " selected" if current == expected else ""


def is_authenticated(draft: dict) -> bool:
    profile = draft["profile"]
    return bool(profile.get("auth_provider") and profile.get("email"))


def provider_meta(provider: str | None) -> dict:
    if provider == "password":
        return {
            "value": "password",
            "label": "ID/PW",
            "subtitle": "아이디와 비밀번호 로그인",
            "className": "auth-password",
            "email": "autostock.kr",
            "icon": "@",
        }
    return next((item for item in AUTH_PROVIDERS if item["value"] == provider), AUTH_PROVIDERS[0])


def provider_label(provider: str | None) -> str:
    if not provider:
        return "미연결"
    return provider_meta(provider)["label"]


def nickname_from_identity(user_id: str) -> str:
    base = trim(user_id, 80)
    if not base:
        return "사용자"
    return (base.split("@", 1)[0] or base)[:24]


def email_from_identity(user_id: str) -> str:
    identity = trim(user_id, 120)
    if "@" in identity:
        return identity
    return f"{identity}@autostock.kr"


def user_runtime_key(draft: dict) -> str:
    profile = draft.get("profile", {})
    return trim(profile.get("email"), 160) or trim(profile.get("session_key"), 64) or "anonymous"


def broker_store_for_user(draft: dict) -> dict[str, dict]:
    key = user_runtime_key(draft)
    if key not in BROKER_SECRET_STORE:
        BROKER_SECRET_STORE[key] = {}
    return BROKER_SECRET_STORE[key]


def store_broker_credentials(draft: dict, broker_entry_id: str, broker_id: str, payload: dict[str, str]) -> None:
    broker_store_for_user(draft)[broker_entry_id] = {"broker_id": broker_id, **payload}


def get_broker_credentials(draft: dict, broker_entry_id: str) -> dict | None:
    return broker_store_for_user(draft).get(broker_entry_id)


def remove_broker_credentials(draft: dict, broker_entry_id: str) -> None:
    broker_store_for_user(draft).pop(broker_entry_id, None)
    BROKER_BALANCE_CACHE.pop(f"{user_runtime_key(draft)}:{broker_entry_id}", None)


def clear_runtime_state(draft: dict) -> None:
    key = user_runtime_key(draft)
    BROKER_SECRET_STORE.pop(key, None)
    for cache_key in list(BROKER_BALANCE_CACHE.keys()):
        if cache_key.startswith(f"{key}:"):
            BROKER_BALANCE_CACHE.pop(cache_key, None)


def parse_int(value: object) -> int:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def format_amount(value: object) -> str:
    return f"{parse_int(value):,}"


def first_non_empty(row: dict, keys: list[str]) -> str:
    for key in keys:
        text = str(row.get(key, "")).strip()
        if text:
            return text
    return ""


def http_json_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: dict | None = None,
    form_body: dict[str, str] | None = None,
) -> dict:
    request_headers = dict(headers or {})
    body: bytes | None = None
    if json_body is not None:
        request_headers["Content-Type"] = "application/json; charset=utf-8"
        body = json.dumps(json_body).encode("utf-8")
    elif form_body is not None:
        request_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"
        body = urlencode(form_body).encode("utf-8")

    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as error:
        payload = error.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {error.code}: {payload[:240] or error.reason}") from error
    except URLError as error:
        raise RuntimeError(f"Network error: {error.reason}") from error


def oauth_provider_settings(provider: str, base_url: str) -> dict:
    upper = provider.upper()
    client_id = os.environ.get(f"SSO_{upper}_CLIENT_ID", "").strip()
    client_secret = os.environ.get(f"SSO_{upper}_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get(f"SSO_{upper}_REDIRECT_URI", "").strip() or f"{base_url}/auth/sso/callback/{provider}"
    return {"client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri}


def oauth_provider_authorize_url(provider: str) -> str:
    return {
        "google": "https://accounts.google.com/o/oauth2/v2/auth",
        "kakao": "https://kauth.kakao.com/oauth/authorize",
        "naver": "https://nid.naver.com/oauth2.0/authorize",
        "facebook": "https://www.facebook.com/v20.0/dialog/oauth",
    }[provider]


def oauth_provider_token_url(provider: str) -> str:
    return {
        "google": "https://oauth2.googleapis.com/token",
        "kakao": "https://kauth.kakao.com/oauth/token",
        "naver": "https://nid.naver.com/oauth2.0/token",
        "facebook": "https://graph.facebook.com/v20.0/oauth/access_token",
    }[provider]


def oauth_is_configured(provider: str, base_url: str) -> bool:
    settings = oauth_provider_settings(provider, base_url)
    return bool(settings["client_id"] and settings["client_secret"])


def oauth_authorize_location(provider: str, base_url: str, state: str) -> str:
    settings = oauth_provider_settings(provider, base_url)
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": settings["client_id"],
        "redirect_uri": settings["redirect_uri"],
        "state": state,
    }
    if provider == "google":
        params["scope"] = "openid email profile"
        params["prompt"] = "select_account"
    elif provider == "kakao":
        params["scope"] = "profile_nickname account_email"
    elif provider == "facebook":
        params["scope"] = "email,public_profile"
    return f"{oauth_provider_authorize_url(provider)}?{urlencode(params)}"


def oauth_exchange_code(provider: str, base_url: str, code: str, state: str) -> str:
    settings = oauth_provider_settings(provider, base_url)
    payload = {
        "grant_type": "authorization_code",
        "client_id": settings["client_id"],
        "client_secret": settings["client_secret"],
        "redirect_uri": settings["redirect_uri"],
        "code": code,
    }
    if provider == "naver":
        payload["state"] = state
    token_data = http_json_request(oauth_provider_token_url(provider), method="POST", form_body=payload)
    access_token = str(token_data.get("access_token", "")).strip()
    if not access_token:
        raise RuntimeError("access_token missing")
    return access_token


def oauth_user_profile(provider: str, access_token: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    if provider == "google":
        payload = http_json_request("https://openidconnect.googleapis.com/v1/userinfo", headers=headers)
        return {"name": trim(payload.get("name"), 80), "email": trim(payload.get("email"), 120)}
    if provider == "kakao":
        payload = http_json_request("https://kapi.kakao.com/v2/user/me", headers=headers)
        account = payload.get("kakao_account", {})
        properties = payload.get("properties", {})
        return {
            "name": trim(account.get("profile", {}).get("nickname") or properties.get("nickname"), 80),
            "email": trim(account.get("email"), 120),
        }
    if provider == "naver":
        payload = http_json_request("https://openapi.naver.com/v1/nid/me", headers=headers)
        response = payload.get("response", {})
        return {
            "name": trim(response.get("name") or response.get("nickname"), 80),
            "email": trim(response.get("email"), 120),
        }
    if provider == "facebook":
        payload = http_json_request(f"https://graph.facebook.com/me?{urlencode({'fields': 'id,name,email', 'access_token': access_token})}")
        return {"name": trim(payload.get("name"), 80), "email": trim(payload.get("email"), 120)}
    raise RuntimeError("unsupported provider")


def kis_base_url(environment: str) -> str:
    if environment == "mock":
        return "https://openapivts.koreainvestment.com:29443"
    return "https://openapi.koreainvestment.com:9443"


def kis_tr_id(environment: str, prod_id: str, mock_id: str) -> str:
    return mock_id if environment == "mock" else prod_id


def kis_access_token(credentials: dict) -> str:
    env = credentials["environment"]
    app_key = credentials["app_key"]
    cache_key = f"{env}:{app_key}"
    cached = KIS_TOKEN_CACHE.get(cache_key)
    now = time.time()
    if cached and cached.get("expires_at", 0) > now + 30:
        return cached["token"]

    base_url = kis_base_url(env)
    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": credentials["app_secret"],
    }
    token_data = http_json_request(f"{base_url}/oauth2/tokenP", method="POST", json_body=payload)
    access_token = str(token_data.get("access_token", "")).strip()
    if not access_token:
        message = trim(token_data.get("msg1"), 240) or "KIS access token 발급 실패"
        raise RuntimeError(message)
    expires_in = parse_int(token_data.get("expires_in"))
    if expires_in <= 0:
        expires_in = 60 * 60 * 12
    KIS_TOKEN_CACHE[cache_key] = {"token": access_token, "expires_at": now + expires_in}
    return access_token


def kis_api_get(credentials: dict, path: str, params: dict[str, str], tr_id: str) -> dict:
    token = kis_access_token(credentials)
    base_url = kis_base_url(credentials["environment"])
    headers = {
        "Authorization": f"Bearer {token}",
        "appkey": credentials["app_key"],
        "appsecret": credentials["app_secret"],
        "tr_id": tr_id,
        "custtype": "P",
    }
    url = f"{base_url}{path}?{urlencode(params)}"
    return http_json_request(url, headers=headers)


def kis_parse_credentials(raw: dict | None) -> dict | None:
    if not raw:
        return None
    if raw.get("broker_id") != "kis":
        return None
    environment = trim(raw.get("environment"), 16) or "production"
    app_key = trim(raw.get("appKey"), 180)
    app_secret = trim(raw.get("appSecret"), 180)
    cano = trim(raw.get("accountPrefix"), 16)
    acnt_prdt_cd = trim(raw.get("accountProductCode"), 8)
    if not cano:
        account_number = trim(raw.get("accountNumber"), 20)
        cano = account_number[:8]
        acnt_prdt_cd = acnt_prdt_cd or account_number[8:10]
    if not acnt_prdt_cd:
        acnt_prdt_cd = "01"
    if not (app_key and app_secret and cano and acnt_prdt_cd):
        return None
    return {
        "environment": environment if environment in {"production", "mock"} else "production",
        "app_key": app_key,
        "app_secret": app_secret,
        "cano": cano,
        "acnt_prdt_cd": acnt_prdt_cd,
    }


def kis_fetch_balance_snapshot(credentials: dict) -> dict:
    params = {
        "CANO": credentials["cano"],
        "ACNT_PRDT_CD": credentials["acnt_prdt_cd"],
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    response = kis_api_get(
        credentials,
        "/uapi/domestic-stock/v1/trading/inquire-balance",
        params,
        kis_tr_id(credentials["environment"], "TTTC8434R", "VTTC8434R"),
    )
    if str(response.get("rt_cd")) != "0":
        raise RuntimeError(trim(response.get("msg1"), 240) or "KIS 잔고 조회 실패")

    holdings = []
    for row in response.get("output1", []) or []:
        symbol = trim(row.get("pdno"), 16)
        if not symbol:
            continue
        quantity = parse_int(row.get("hldg_qty"))
        name = trim(row.get("prdt_name"), 80) or symbol
        price = format_amount(first_non_empty(row, ["prpr", "stck_prpr", "pchs_avg_pric", "avrg_unpr"]))
        change = trim(row.get("evlu_pfls_rt"), 24)
        change_label = f"{change}%" if change else "-"
        holdings.append(
            {
                "symbol": symbol,
                "name": name,
                "market": "KRX",
                "price": price,
                "change": change_label,
                "quantity": quantity,
            }
        )

    output2 = (response.get("output2") or [{}])[0]
    total_eval = first_non_empty(output2, ["tot_evlu_amt", "scts_evlu_amt", "tot_evlu_pfls_amt"])
    cash = first_non_empty(output2, ["dnca_tot_amt", "tot_dncl_amt", "ord_psbl_cash"])
    profit = first_non_empty(output2, ["evlu_pfls_smtl_amt", "tot_evlu_pfls_amt"])
    return {
        "total_eval_amount": format_amount(total_eval),
        "cash_amount": format_amount(cash),
        "profit_amount": format_amount(profit),
        "holdings_count": len(holdings),
        "holdings": holdings,
    }


def kis_fetch_quote(credentials: dict, symbol_code: str) -> dict:
    response = kis_api_get(
        credentials,
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": symbol_code},
        "FHKST01010100",
    )
    if str(response.get("rt_cd")) != "0":
        raise RuntimeError(trim(response.get("msg1"), 240) or "KIS 종목 조회 실패")
    output = response.get("output", {}) or {}
    name = trim(output.get("hts_kor_isnm"), 80) or symbol_code
    price = format_amount(first_non_empty(output, ["stck_prpr", "prpr"]))
    change_rate = trim(output.get("prdy_ctrt"), 24)
    change = f"{change_rate}%" if change_rate else "-"
    return {"symbol": symbol_code, "name": name, "market": "KRX", "price": price, "change": change, "quantity": 0}


def broker_balance_snapshot(draft: dict, broker_entry: dict) -> dict:
    cache_key = f"{user_runtime_key(draft)}:{broker_entry['id']}"
    cached = BROKER_BALANCE_CACHE.get(cache_key)
    now = time.time()
    if cached and cached.get("expires_at", 0) > now:
        return cached

    credentials = kis_parse_credentials(get_broker_credentials(draft, broker_entry["id"]))
    if broker_entry["broker_id"] != "kis" or not credentials:
        payload = {"status": "unsupported", "expires_at": now + 12}
        BROKER_BALANCE_CACHE[cache_key] = payload
        return payload

    try:
        snapshot = kis_fetch_balance_snapshot(credentials)
        payload = {"status": "ok", "snapshot": snapshot, "expires_at": now + 15}
    except Exception as error:
        payload = {"status": "error", "message": trim(str(error), 200), "expires_at": now + 8}
    BROKER_BALANCE_CACHE[cache_key] = payload
    return payload


def broker_symbol_catalog(draft: dict, broker_id: str, symbol_query: str | None = None) -> dict:
    if broker_id != "kis":
        return {"mode": "demo_catalog", "items": get_symbol_catalog(broker_id), "message": ""}

    broker_entry = find_connected_broker(draft, broker_id)
    if not broker_entry:
        return {"mode": "demo_catalog", "items": get_symbol_catalog(broker_id), "message": ""}

    credentials = kis_parse_credentials(get_broker_credentials(draft, broker_entry["id"]))
    if not credentials:
        return {"mode": "demo_catalog", "items": get_symbol_catalog(broker_id), "message": "KIS 실연동 키가 없어 데모 목록으로 표시합니다."}

    try:
        snapshot = kis_fetch_balance_snapshot(credentials)
        items = list(snapshot["holdings"])
        query = trim(symbol_query, 24).upper()
        if query and all(item["symbol"] != query for item in items):
            items.insert(0, kis_fetch_quote(credentials, query))
        return {"mode": "live_broker_api", "items": items[:80], "message": ""}
    except Exception as error:
        return {
            "mode": "live_broker_api_error",
            "items": get_symbol_catalog(broker_id),
            "message": f"실제 KIS 종목/잔고 조회 실패: {trim(str(error), 180)}",
        }


def symbol_choice_from_broker(draft: dict, broker_id: str, symbol_code: str) -> dict | None:
    catalog = broker_symbol_catalog(draft, broker_id, symbol_code)
    for item in catalog.get("items", []):
        if item.get("symbol") == symbol_code:
            return item
    return None


def flash_message_from_query(query: dict[str, list[str]]) -> dict | None:
    flash_key = query.get("flash", [""])[-1]
    return FLASH_MESSAGES.get(flash_key)


def find_connected_broker(draft: dict, broker_id: str) -> dict | None:
    for item in draft["brokers"]:
        if item["broker_id"] == broker_id:
            return item
    return None


def find_symbol(draft: dict, symbol_id: str) -> dict | None:
    for item in draft["symbols"]:
        if item["id"] == symbol_id:
            return item
    return None


def remove_item(items: list[dict], item_id: str) -> list[dict]:
    return [item for item in items if item.get("id") != item_id]


def root_path_for_draft(draft: dict) -> str:
    return "/dashboard" if is_authenticated(draft) else "/login"


def recommended_modal(draft: dict, requested: str | None) -> str | None:
    if requested in MODAL_KEYS:
        return requested
    if not draft["brokers"]:
        return "broker"
    return None


def capability_summary(broker: dict) -> str:
    labels = {"quote": "주가 확인", "buy": "매수", "sell": "매도", "balance": "잔고"}
    parts = []
    for key, label in labels.items():
        capability = CAPABILITY_META[broker["capability"][key]]
        parts.append(f"{label} {capability['label']}")
    return " · ".join(parts)


def get_symbol_catalog(broker_id: str | None) -> list[dict]:
    if not broker_id:
        return SYMBOL_LIBRARY["default"]
    return SYMBOL_LIBRARY.get(broker_id, SYMBOL_LIBRARY["default"])


def collect_broker_secret_payload(broker: dict, values: dict[str, str]) -> dict[str, str]:
    payload: dict[str, str] = {}
    for field in broker.get("fields", []):
        key = field.get("key")
        if key:
            payload[key] = trim(values.get(key), 240)
    payload["environment"] = trim(values.get("environment"), 20) or "production"
    return payload


def upsert_broker_entry(draft: dict, broker: dict, values: dict[str, str]) -> dict:
    account_label = trim(values.get("accountNumber"), 40)
    if not account_label:
        account_prefix = trim(values.get("accountPrefix"), 40)
        product_code = trim(values.get("accountProductCode"), 20)
        if account_prefix:
            account_label = f"{account_prefix}-{product_code}" if product_code else account_prefix
    if not account_label:
        account_label = trim(values.get("htsId"), 40) or "연결 정보"

    existing_match = next(
        (
            item
            for item in draft["brokers"]
            if item["broker_id"] == broker["id"]
            and item["environment"] == values.get("environment", "production")
            and item["account_label"] == account_label
        ),
        None,
    )
    entry = {
        "id": existing_match["id"] if existing_match else uuid4().hex[:10],
        "broker_id": broker["id"],
        "broker_name": broker["name"],
        "environment": values.get("environment", "production"),
        "account_label": account_label,
        "saved_at": now_iso(),
        "capability_summary": capability_summary(broker),
    }
    existing = [
        item
        for item in draft["brokers"]
        if not (
            item["broker_id"] == entry["broker_id"]
            and item["environment"] == entry["environment"]
            and item["account_label"] == entry["account_label"]
        )
    ]
    draft["brokers"] = [entry, *existing][:8]
    return entry


def add_symbol_entry(draft: dict, form: dict[str, str]) -> tuple[bool, str]:
    broker_id = trim(form.get("brokerId"), 40)
    symbol_code = trim(form.get("symbolCode"), 24).upper()
    broker_entry = find_connected_broker(draft, broker_id)
    if not broker_entry:
        return False, "먼저 증권을 연결해야 종목을 고를 수 있습니다."
    if not symbol_code:
        return False, "종목을 먼저 선택해야 합니다."

    symbol_meta = symbol_choice_from_broker(draft, broker_id, symbol_code)
    if not symbol_meta:
        return False, "선택한 종목을 찾지 못했습니다."

    item = {
        "id": uuid4().hex[:10],
        "symbol": symbol_meta["symbol"],
        "name": symbol_meta["name"],
        "market": symbol_meta["market"],
        "price": symbol_meta["price"],
        "change": symbol_meta["change"],
        "broker_id": broker_id,
        "broker_name": broker_entry["broker_name"],
        "saved_at": now_iso(),
    }
    existing = [entry for entry in draft["symbols"] if not (entry["symbol"] == item["symbol"] and entry["broker_id"] == broker_id)]
    draft["symbols"] = [item, *existing][:20]
    return True, f"{item['name']} 종목을 워치리스트에 추가했습니다."


def add_pattern_entry(draft: dict, form: dict[str, str]) -> tuple[bool, str]:
    symbol_id = trim(form.get("symbolId"), 40)
    pattern_type = trim(form.get("patternType"), 40)
    schedule = trim(form.get("schedule"), 40)
    budget = trim(form.get("budget"), 40)
    profit_target = trim(form.get("profitTarget"), 40)
    stop_loss = trim(form.get("stopLoss"), 40)
    note = trim(form.get("note"), 200)
    buy_enabled = form.get("buyEnabled") == "on"
    sell_enabled = form.get("sellEnabled") == "on"

    if not symbol_id or not pattern_type or not schedule:
        return False, "종목, 패턴, 주기를 모두 선택해야 합니다."
    if not buy_enabled and not sell_enabled:
        return False, "자동 매수나 자동 매도 중 하나 이상을 켜야 합니다."

    symbol_entry = find_symbol(draft, symbol_id)
    if not symbol_entry:
        return False, "먼저 종목을 선택해야 합니다."

    pattern_meta = next((item for item in PATTERN_OPTIONS if item["value"] == pattern_type), None)
    schedule_meta = next((item for item in SCHEDULE_OPTIONS if item["value"] == schedule), None)

    draft["patterns"] = [
        {
            "id": uuid4().hex[:10],
            "symbol_id": symbol_entry["id"],
            "symbol": symbol_entry["symbol"],
            "symbol_name": symbol_entry["name"],
            "pattern_type": pattern_type,
            "pattern_label": pattern_meta["label"] if pattern_meta else pattern_type,
            "pattern_description": pattern_meta["description"] if pattern_meta else "",
            "schedule": schedule,
            "schedule_label": schedule_meta["label"] if schedule_meta else schedule,
            "buy_enabled": buy_enabled,
            "sell_enabled": sell_enabled,
            "budget": budget or "예산 미설정",
            "profit_target": profit_target,
            "stop_loss": stop_loss,
            "note": note,
            "saved_at": now_iso(),
        },
        *draft["patterns"],
    ][:20]
    return True, f"{symbol_entry['name']} 전략을 저장했습니다."


def save_ai_entry(draft: dict, form: dict[str, str]) -> tuple[bool, str]:
    provider = trim(form.get("provider"), 40)
    model = trim(form.get("model"), 80)
    prompt = trim(form.get("prompt"), 400)
    api_key = trim(form.get("apiKey"), 240)

    if not provider or not model or not prompt:
        return False, "AI 제공사, 모델, 프롬프트를 모두 입력해야 합니다."

    draft["ai"] = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "has_api_key": bool(api_key),
        "updated_at": now_iso(),
    }
    return True, "AI 전략 설정을 저장했습니다."


def render_select(name: str, label: str, options: list[dict[str, str]], value: str | None, help_text: str, *, required: bool = False) -> str:
    required_tag = '<span class="field-chip">필수</span>' if required else '<span class="field-chip field-chip-muted">선택</span>'
    options_html = "".join(
        f'<option value="{html(option["value"])}"{selected_attr(value, option["value"])}>{html(option["label"])}</option>'
        for option in options
    )
    return f"""
    <div class="field">
      <label for="{html(name)}">{html(label)} {required_tag}</label>
      <select id="{html(name)}" name="{html(name)}">{options_html}</select>
      <small>{html(help_text)}</small>
    </div>
    """


def render_input(
    name: str,
    label: str,
    value: str | None,
    help_text: str,
    *,
    required: bool = False,
    input_type: str = "text",
    placeholder: str = "",
) -> str:
    required_tag = '<span class="field-chip">필수</span>' if required else '<span class="field-chip field-chip-muted">선택</span>'
    return f"""
    <div class="field">
      <label for="{html(name)}">{html(label)} {required_tag}</label>
      <input
        id="{html(name)}"
        name="{html(name)}"
        type="{html(input_type)}"
        value="{html(value or '')}"
        placeholder="{html(placeholder)}"
        autocomplete="off"
      />
      <small>{html(help_text)}</small>
    </div>
    """


def render_textarea(name: str, label: str, value: str | None, help_text: str, *, required: bool = False, placeholder: str = "") -> str:
    required_tag = '<span class="field-chip">필수</span>' if required else '<span class="field-chip field-chip-muted">선택</span>'
    return f"""
    <div class="field field-full">
      <label for="{html(name)}">{html(label)} {required_tag}</label>
      <textarea id="{html(name)}" name="{html(name)}" rows="6" placeholder="{html(placeholder)}">{html(value or '')}</textarea>
      <small>{html(help_text)}</small>
    </div>
    """


def render_message(message: dict | None) -> str:
    if not message:
        return ""
    return f'<div class="message message-{html(message["kind"])}">{html(message["text"])}</div>'


def render_auth_links(current: str) -> str:
    links = [
        ("/signup", "회원가입", current == "signup"),
        ("/find-id", "아이디 찾기", current == "find-id"),
        ("/find-password", "비밀번호 찾기", current == "find-password"),
        ("/login", "로그인", current == "login"),
    ]
    rendered = []
    for href, label, selected in links:
        class_name = "auth-footer-link auth-footer-link-active" if selected else "auth-footer-link"
        rendered.append(f'<a class="{class_name}" href="{href}">{html(label)}</a>')
    return "".join(rendered)


def render_social_icons() -> str:
    buttons = []
    for provider in AUTH_PROVIDERS:
        buttons.append(
            f"""
            <a class="sso-icon-button {html(provider['className'])}" href="/auth/sso/start?provider={html(provider['value'])}" aria-label="{html(provider['label'])}">
              <span>{html(provider['icon'])}</span>
            </a>
            """
        )
    return "".join(buttons)


def render_login_form(values: dict[str, str] | None) -> str:
    current = values or {}
    return f"""
    <form class="auth-form" method="post" action="/auth/login">
      <div class="auth-field">
        <label for="userId">아이디</label>
        <input id="userId" name="userId" type="text" autocomplete="username" placeholder="아이디 또는 이메일" value="{html(current.get('userId', ''))}" />
      </div>
      <div class="auth-field">
        <label for="password">비밀번호</label>
        <input id="password" name="password" type="password" autocomplete="current-password" placeholder="비밀번호" />
      </div>
      <button class="button button-primary auth-submit" type="submit">로그인</button>
    </form>
    """


def render_signup_form(values: dict[str, str] | None) -> str:
    current = values or {}
    return f"""
    <form class="auth-form" method="post" action="/auth/signup">
      <div class="auth-field">
        <label for="nickname">이름</label>
        <input id="nickname" name="nickname" type="text" autocomplete="name" placeholder="이름" value="{html(current.get('nickname', ''))}" />
      </div>
      <div class="auth-field">
        <label for="signupEmail">이메일</label>
        <input id="signupEmail" name="email" type="email" autocomplete="email" placeholder="you@example.com" value="{html(current.get('email', ''))}" />
      </div>
      <div class="auth-field auth-field-split">
        <div>
          <label for="signupPassword">비밀번호</label>
          <input id="signupPassword" name="password" type="password" autocomplete="new-password" placeholder="8자 이상" />
        </div>
        <div>
          <label for="signupPasswordConfirm">비밀번호 확인</label>
          <input id="signupPasswordConfirm" name="passwordConfirm" type="password" autocomplete="new-password" placeholder="한 번 더 입력" />
        </div>
      </div>
      <button class="button button-primary auth-submit" type="submit">회원가입</button>
    </form>
    """


def render_recovery_form(mode: str, values: dict[str, str] | None) -> str:
    current = values or {}
    if mode == "find-id":
        return f"""
        <form class="auth-form" method="post" action="/auth/find-id">
          <div class="auth-field">
            <label for="recoverName">이름</label>
            <input id="recoverName" name="name" type="text" autocomplete="name" placeholder="회원가입 이름" value="{html(current.get('name', ''))}" />
          </div>
          <div class="auth-field">
            <label for="recoverPhone">휴대폰 번호</label>
            <input id="recoverPhone" name="phone" type="tel" autocomplete="tel" placeholder="01012345678" value="{html(current.get('phone', ''))}" />
          </div>
          <button class="button button-primary auth-submit" type="submit">아이디 찾기</button>
        </form>
        """

    return f"""
    <form class="auth-form" method="post" action="/auth/find-password">
      <div class="auth-field">
        <label for="recoverPasswordId">아이디</label>
        <input id="recoverPasswordId" name="userId" type="text" autocomplete="username" placeholder="아이디 또는 이메일" value="{html(current.get('userId', ''))}" />
      </div>
      <div class="auth-field">
        <label for="recoverPasswordEmail">이메일</label>
        <input id="recoverPasswordEmail" name="email" type="email" autocomplete="email" placeholder="가입 이메일" value="{html(current.get('email', ''))}" />
      </div>
      <button class="button button-primary auth-submit" type="submit">비밀번호 재설정</button>
    </form>
    """


def render_auth_page(mode: str, message: dict | None = None, values: dict[str, str] | None = None) -> bytes:
    page_meta = {
        "login": {
            "title": "로그인",
            "subtitle": "아이디와 비밀번호로 로그인하거나 간편 로그인으로 바로 시작하세요.",
            "form": render_login_form(values),
        },
        "signup": {
            "title": "회원가입",
            "subtitle": "새 계정을 만들고 바로 대시보드에서 증권과 전략을 설정하세요.",
            "form": render_signup_form(values),
        },
        "find-id": {
            "title": "아이디 찾기",
            "subtitle": "가입한 이름과 연락처로 아이디 안내를 요청합니다.",
            "form": render_recovery_form("find-id", values),
        },
        "find-password": {
            "title": "비밀번호 찾기",
            "subtitle": "아이디와 이메일을 확인한 뒤 재설정 절차를 시작합니다.",
            "form": render_recovery_form("find-password", values),
        },
    }
    current = page_meta[mode]
    helper = ""
    if mode == "login":
        helper = """
        <div class="auth-divider"><span>간편 로그인</span></div>
        <div class="sso-row">
          {social_icons}
        </div>
        <p class="auth-helper">설정된 OAuth 키로 실제 SSO 인증을 진행합니다.</p>
        """.replace("{social_icons}", render_social_icons())

    html_body = f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html(current['title'])} | {html(PROJECT_TITLE)}</title>
    <link rel="stylesheet" href="/styles.css" />
  </head>
  <body class="login-body">
    <main class="auth-shell">
      <section class="auth-card">
        <div class="auth-brand">
          <span class="brand-mark">AST</span>
          <strong>{html(PROJECT_TITLE)}</strong>
        </div>
        <div class="auth-heading">
          <h1>{html(current['title'])}</h1>
          <p>{html(current['subtitle'])}</p>
        </div>
        {render_message(message)}
        {current['form']}
        {helper}
        <nav class="auth-footer-links" aria-label="계정 메뉴">
          {render_auth_links(mode)}
        </nav>
      </section>
    </main>
  </body>
</html>
"""
    return html_body.encode("utf-8")


def render_topbar(draft: dict) -> str:
    provider = provider_meta(draft["profile"].get("auth_provider"))
    return f"""
    <header class="dashboard-topbar">
      <div>
        <span class="eyebrow">Workspace</span>
        <h1>{html(PROJECT_TITLE)}</h1>
      </div>
      <div class="topbar-actions">
        <span class="user-badge">{html(provider['label'])} · {html(draft['profile'].get('nickname') or '사용자')}</span>
        <a class="button button-subtle button-small" href="/dashboard?modal=broker">증권 추가</a>
        <form method="post" action="/auth/logout">
          <button class="button button-subtle button-small" type="submit">로그아웃</button>
        </form>
      </div>
    </header>
    """


def render_summary_strip(draft: dict) -> str:
    ai_ready = "연결됨" if draft["ai"].get("provider") and draft["ai"].get("has_api_key") else "대기"
    cards = [
        ("연결 증권", f'{len(draft["brokers"])}개', "브로커 계좌"),
        ("감시 종목", f'{len(draft["symbols"])}개', "워치리스트"),
        ("자동 전략", f'{len(draft["patterns"])}개', "정량 패턴"),
        ("AI 전략", ai_ready, provider_label(draft["ai"].get("provider"))),
    ]
    return "".join(
        f"""
        <div class="summary-card">
          <span>{html(label)}</span>
          <strong>{html(value)}</strong>
          <small>{html(note)}</small>
        </div>
        """
        for label, value, note in cards
    )


def render_dashboard_hero(draft: dict) -> str:
    name = draft["profile"].get("nickname") or "사용자"
    return f"""
    <section class="hero-panel">
      <div>
        <span class="eyebrow eyebrow-dark">Dashboard</span>
        <h2>{html(name)}님의 자동매매 워크스페이스</h2>
        <p>먼저 증권을 연결하고, 그 다음 종목을 고른 뒤 정량 패턴을 붙입니다. 숫자로 정의하기 어려운 전략만 AI로 넘깁니다.</p>
      </div>
      <div class="hero-actions">
        <a class="button button-primary" href="/dashboard?modal=broker">증권 연결</a>
        <a class="button button-secondary" href="/dashboard?modal=symbol">종목 추가</a>
      </div>
      <div class="summary-grid">
        {render_summary_strip(draft)}
      </div>
    </section>
    """


def render_connected_brokers(draft: dict) -> str:
    if not draft["brokers"]:
        return """
        <div class="section-empty">
          <h3>아직 연결된 증권이 없습니다.</h3>
          <p>처음에는 빈 상태로 시작합니다. 여기서 바로 증권 계좌를 추가하면 이후 종목 선택이 열립니다.</p>
          <a class="button button-primary" href="/dashboard?modal=broker">증권 추가</a>
        </div>
        """

    cards = []
    for item in draft["brokers"]:
        env_label = "실전" if item["environment"] == "production" else "모의"
        balance = broker_balance_snapshot(draft, item)
        balance_note = ""
        if balance.get("status") == "ok":
            snapshot = balance.get("snapshot", {})
            balance_note = (
                f"평가자산 {html(snapshot.get('total_eval_amount', '-'))}원 · "
                f"현금 {html(snapshot.get('cash_amount', '-'))}원 · "
                f"보유종목 {html(snapshot.get('holdings_count', 0))}개"
            )
        elif balance.get("status") == "error":
            balance_note = f"잔고 조회 실패: {html(balance.get('message', 'unknown error'))}"
        elif item["broker_id"] == "kis":
            balance_note = "KIS API 키/계좌 정보가 없어서 잔고를 조회하지 못했습니다."
        cards.append(
            f"""
            <div class="broker-card">
              <div>
                <strong>{html(item["broker_name"])}</strong>
                <span>{html(item["account_label"])}</span>
                <small>{html(item.get("capability_summary", ""))}</small>
                <small>{balance_note}</small>
              </div>
              <div class="broker-card-actions">
                <span class="status-chip">{html(env_label)}</span>
                <form method="post" action="/dashboard/brokers/remove">
                  <input type="hidden" name="itemId" value="{html(item['id'])}" />
                  <button class="button button-subtle button-small" type="submit">삭제</button>
                </form>
              </div>
            </div>
            """
        )
    return "".join(cards)


def render_watchlist_rows(draft: dict) -> str:
    if not draft["symbols"]:
        return """
        <div class="section-empty">
          <h3>워치리스트가 비어 있습니다.</h3>
          <p>증권 연결 후 브로커 기반 종목 목록에서 종목을 고를 수 있습니다.</p>
          <a class="button button-primary" href="/dashboard?modal=symbol">종목 추가</a>
        </div>
        """

    rows = []
    for item in draft["symbols"]:
        rule_count = sum(1 for pattern in draft["patterns"] if pattern["symbol_id"] == item["id"])
        rows.append(
            f"""
            <div class="watchlist-row">
              <div class="watchlist-main">
                <strong>{html(item["name"])}</strong>
                <span>{html(item["symbol"])} · {html(item["market"])} · {html(item["broker_name"])}</span>
              </div>
              <span>{html(item["price"])}</span>
              <span class="price-change">{html(item["change"])}</span>
              <span>{rule_count}개 규칙</span>
              <form method="post" action="/dashboard/symbols/remove">
                <input type="hidden" name="itemId" value="{html(item['id'])}" />
                <button class="button button-subtle button-small" type="submit">삭제</button>
              </form>
            </div>
            """
        )
    return "".join(rows)


def render_pattern_rows(draft: dict) -> str:
    if not draft["patterns"]:
        return """
        <div class="section-empty">
          <h3>정량 패턴이 아직 없습니다.</h3>
          <p>정액, 정률, 주기 기반 전략은 전략 빌더에서 만드는 쪽이 가장 안정적입니다.</p>
          <a class="button button-primary" href="/dashboard?modal=pattern">패턴 만들기</a>
        </div>
        """

    cards = []
    for item in draft["patterns"]:
        badges = [item["budget"], item["schedule_label"]]
        if item.get("profit_target"):
            badges.append(f'익절 {item["profit_target"]}')
        if item.get("stop_loss"):
            badges.append(f'손절 {item["stop_loss"]}')
        cards.append(
            f"""
            <div class="strategy-card">
              <div class="strategy-head">
                <div>
                  <strong>{html(item["symbol_name"])}</strong>
                  <span>{html(item["pattern_label"])}</span>
                </div>
                <form method="post" action="/dashboard/patterns/remove">
                  <input type="hidden" name="itemId" value="{html(item['id'])}" />
                  <button class="button button-subtle button-small" type="submit">삭제</button>
                </form>
              </div>
              <div class="tag-row">
                {''.join(f'<span class="tag">{html(badge)}</span>' for badge in badges)}
              </div>
              <p>{html(item.get("note") or item.get("pattern_description") or "")}</p>
            </div>
            """
        )
    return "".join(cards)


def render_ai_panel(draft: dict) -> str:
    ai = draft["ai"]
    if not ai.get("provider"):
        return """
        <div class="section-empty">
          <h3>AI 전략은 아직 비어 있습니다.</h3>
          <p>정확한 수치로 정의하기 애매한 조건만 AI 전략으로 분리하는 구성이 좋습니다.</p>
          <a class="button button-secondary" href="/dashboard?modal=ai">AI 전략 추가</a>
        </div>
        """

    return f"""
    <div class="ai-card">
      <strong>{html(provider_label(ai["provider"]))}</strong>
      <span>{html(ai.get("model", "모델 미지정"))}</span>
      <p>{html(ai.get("prompt", ""))}</p>
      <div class="tag-row">
        <span class="tag">{'API 키 입력됨' if ai.get('has_api_key') else 'API 키 미입력'}</span>
        <span class="tag">업데이트 {html((ai.get("updated_at") or "")[:10] or "방금")}</span>
      </div>
      <form method="post" action="/dashboard/ai/clear">
        <button class="button button-subtle button-small" type="submit">초기화</button>
      </form>
    </div>
    """


def render_guide_panel() -> str:
    return """
    <div class="guide-panel">
      <div class="guide-card">
        <strong>정밀 전략</strong>
        <p>정액 매수, 정률 매도, 익절·손절, 시간 주기처럼 수치화 가능한 전략은 패턴 빌더에서 처리합니다.</p>
      </div>
      <div class="guide-card">
        <strong>AI 전략</strong>
        <p>뉴스 반응, 서술형 판단, 애매한 심리 조건처럼 정량화가 어려운 구간만 AI 전략으로 넘깁니다.</p>
      </div>
      <div class="guide-card">
        <strong>실브로커 연동</strong>
        <p>연결된 증권 계좌 기준으로 종목·잔고를 조회하고, 지원하지 않는 브로커는 안내 문구를 노출합니다.</p>
      </div>
    </div>
    """


def render_broker_picker(selected_broker_id: str) -> str:
    chips = []
    for broker in BROKER_DETAILS:
        status = STATUS_META[broker["status"]]
        classes = "broker-tab is-active" if broker["id"] == selected_broker_id else "broker-tab"
        chips.append(
            f"""
            <a class="{classes}" href="/dashboard?modal=broker&broker={html(broker['id'])}">
              <strong>{html(broker["name"])}</strong>
              <span>{html(status["label"])}</span>
            </a>
            """
        )
    return "".join(chips)


def render_modal_shell(title: str, subtitle: str, body: str, message: dict | None = None) -> str:
    return f"""
    <div class="modal-backdrop">
      <a class="modal-dismiss" href="/dashboard" aria-label="닫기"></a>
      <section class="modal-sheet">
        <div class="modal-head">
          <div>
            <span class="eyebrow eyebrow-muted">Workspace Modal</span>
            <h3>{html(title)}</h3>
            <p>{html(subtitle)}</p>
          </div>
          <a class="button button-subtle button-small" href="/dashboard">닫기</a>
        </div>
        {render_message(message)}
        <div class="modal-body">
          {body}
        </div>
      </section>
    </div>
    """


def render_broker_modal(draft: dict, selected_broker_id: str, values: dict[str, str], message: dict | None, validation: dict | None) -> str:
    broker = get_broker_or_none(selected_broker_id) or READY_BROKERS[0]
    status = STATUS_META[broker["status"]]
    guide_items = "".join(f"<li>{html(step)}</li>" for step in broker.get("steps", []))
    source_items = "".join(
        f'<li><a class="inline-link" href="{html(source["url"])}" target="_blank" rel="noreferrer">{html(source["label"])}</a></li>'
        for source in broker.get("sources", [])
    )

    if broker["status"] != "ready":
        body = f"""
        <div class="broker-picker">{render_broker_picker(broker["id"])}</div>
        <div class="unsupported-card">
          <div class="status-row">
            <strong>{html(broker["name"])}</strong>
            <span class="status-chip">{html(status["label"])}</span>
          </div>
          <p>{html(broker["summary"])}</p>
          <div class="capability-row">
            {''.join(f'<span class="tag">{html(label)} {html(CAPABILITY_META[broker["capability"][key]]["label"])}</span>' for key, label in {"quote": "주가", "buy": "매수", "sell": "매도", "balance": "잔고"}.items())}
          </div>
          <div class="modal-split">
            <div>
              <h4>확인 포인트</h4>
              <ol class="bullet-list ordered-list">{guide_items}</ol>
            </div>
            <div>
              <h4>공식 링크</h4>
              <ul class="bullet-list">{source_items}</ul>
            </div>
          </div>
        </div>
        """
        return render_modal_shell("증권 추가", "지원 상태에 맞춰 연결 방식을 확인합니다.", body, message)

    fields_html = []
    for field in broker.get("fields", []):
        if field["type"] == "select":
            fields_html.append(
                render_select(
                    field["key"],
                    field["label"],
                    field.get("options", []),
                    values.get(field["key"]),
                    field.get("help", ""),
                    required=field.get("required", False),
                )
            )
        else:
            fields_html.append(
                render_input(
                    field["key"],
                    field["label"],
                    values.get(field["key"]),
                    field.get("help", ""),
                    required=field.get("required", False),
                    input_type="password" if field["type"] == "password" else "text",
                    placeholder=field.get("placeholder", ""),
                )
            )

    validation_html = ""
    if validation:
        missing = validation.get("missing_fields", [])
        warnings = validation.get("warnings", [])
        validation_html = f"""
        <div class="message message-{'success' if not missing else 'warning'}">
          {'필수 값 검증을 통과했습니다.' if not missing else '필수 입력을 더 채워야 합니다.'}
          {f"<br />누락 필드: {html(', '.join(missing))}" if missing else ""}
          {('<ul class="bullet-list compact-list">' + ''.join(f'<li>{html(item)}</li>' for item in warnings) + '</ul>') if warnings else ''}
        </div>
        """

    body = f"""
    <div class="broker-picker">{render_broker_picker(broker["id"])}</div>
    <div class="modal-split">
      <div class="modal-panel">
        <div class="status-row">
          <strong>{html(broker["name"])}</strong>
          <span class="status-chip">{html(status["label"])}</span>
        </div>
        <p class="panel-copy">{html(broker["summary"])}</p>
        <div class="tag-row">
          {''.join(f'<span class="tag">{html(label)} {html(CAPABILITY_META[broker["capability"][key]]["label"])}</span>' for key, label in {"quote": "주가", "buy": "매수", "sell": "매도", "balance": "잔고"}.items())}
        </div>
        {validation_html}
        <form method="post" action="/dashboard/brokers/add" class="form-grid">
          <input type="hidden" name="selectedBrokerId" value="{html(broker['id'])}" />
          {''.join(fields_html)}
          <div class="field field-full">
            <div class="button-row">
              <button class="button button-primary" type="submit">이 증권 연결</button>
            </div>
            <small>브로커 키는 서버 메모리에만 보관되며 프로세스 재시작 시 초기화됩니다.</small>
          </div>
        </form>
      </div>
      <div class="modal-panel">
        <h4>가이드</h4>
        <ol class="bullet-list ordered-list">{guide_items}</ol>
        <h4>공식 링크</h4>
        <ul class="bullet-list">{source_items}</ul>
      </div>
    </div>
    """
    return render_modal_shell("증권 추가", "빈 대시보드에서 가장 먼저 계좌를 연결합니다.", body, message)


def render_symbol_modal(
    draft: dict,
    selected_broker_id: str | None,
    values: dict[str, str],
    query: dict[str, list[str]],
    message: dict | None,
) -> str:
    if not draft["brokers"]:
        body = """
        <div class="section-empty">
          <h3>먼저 증권을 연결해야 합니다.</h3>
          <p>브로커 연결이 끝나면 해당 브로커 기준의 종목 목록을 고를 수 있습니다.</p>
          <a class="button button-primary" href="/dashboard?modal=broker">증권 연결 열기</a>
        </div>
        """
        return render_modal_shell("종목 추가", "브로커 연결 후 종목 선택이 열립니다.", body, message)

    broker_id = selected_broker_id or values.get("brokerId") or draft["brokers"][0]["broker_id"]
    symbol_query = trim(query.get("q", [""])[-1], 24).upper()
    broker_tabs = []
    for broker in draft["brokers"]:
        classes = "broker-tab is-active" if broker["broker_id"] == broker_id else "broker-tab"
        broker_tabs.append(
            f'<a class="{classes}" href="/dashboard?modal=symbol&broker={html(broker["broker_id"])}"><strong>{html(broker["broker_name"])}</strong><span>{html(broker["account_label"])}</span></a>'
        )

    catalog_payload = broker_symbol_catalog(draft, broker_id, symbol_query)
    catalog = catalog_payload.get("items", [])
    option_label = lambda item: f'{item["name"]} ({item["symbol"]}) · {item["market"]} · {item["price"]} · {item["change"]}'
    symbol_options = [{"value": item["symbol"], "label": option_label(item)} for item in catalog]
    if not symbol_options:
        symbol_options = [{"value": "", "label": "조회된 종목이 없습니다. 종목코드 조회를 먼저 실행하세요."}]
    preview_cards = "".join(
        f"""
        <div class="quote-card">
          <strong>{html(item["name"])}</strong>
          <span>{html(item["symbol"])} · {html(item["market"])}</span>
          <b>{html(item["price"])}</b>
          <small>{html(item["change"])}</small>
        </div>
        """
        for item in catalog[:4]
    )
    mode_text = "실브로커 조회" if catalog_payload.get("mode") == "live_broker_api" else "대체 목록"
    api_message = catalog_payload.get("message", "")
    body = f"""
    <div class="broker-picker">{''.join(broker_tabs)}</div>
    <div class="modal-split">
      <div class="modal-panel">
        <form method="get" action="/dashboard" class="inline-form">
          <input type="hidden" name="modal" value="symbol" />
          <input type="hidden" name="broker" value="{html(broker_id)}" />
          <input class="inline-input" name="q" value="{html(symbol_query)}" placeholder="종목코드(예: 005930) 조회" />
          <button class="button button-secondary button-small" type="submit">코드 조회</button>
        </form>
        {f'<div class="message message-warning">{html(api_message)}</div>' if api_message else ''}
        <form method="post" action="/dashboard/symbols/add" class="form-grid">
          <input type="hidden" name="brokerId" value="{html(broker_id)}" />
          {render_select("symbolCode", "종목 선택", symbol_options, values.get("symbolCode"), "연결한 증권 계좌에서 조회한 종목 또는 코드 조회 결과", required=True)}
          <div class="field field-full">
            <div class="button-row">
              <button class="button button-primary" type="submit">워치리스트에 추가</button>
            </div>
          </div>
        </form>
      </div>
      <div class="modal-panel">
        <h4>브로커 기반 종목 목록</h4>
        <p class="panel-copy">조회 모드: {html(mode_text)} · 종목 수: {html(len(catalog))}개</p>
        <div class="quote-grid">{preview_cards}</div>
      </div>
    </div>
    """
    return render_modal_shell("종목 추가", "연결된 증권 계좌를 기준으로 워치리스트를 채웁니다.", body, message)


def render_pattern_modal(draft: dict, values: dict[str, str], message: dict | None) -> str:
    if not draft["symbols"]:
        body = """
        <div class="section-empty">
          <h3>먼저 종목을 추가해야 합니다.</h3>
          <p>워치리스트에 종목이 들어와야 패턴 빌더가 열립니다.</p>
          <a class="button button-primary" href="/dashboard?modal=symbol">종목 추가 열기</a>
        </div>
        """
        return render_modal_shell("패턴 설정", "정량 패턴은 종목이 있어야 만들 수 있습니다.", body, message)

    symbol_options = [{"value": item["id"], "label": f'{item["name"]} ({item["symbol"]}) · {item["broker_name"]}'} for item in draft["symbols"]]
    pattern_options = [{"value": item["value"], "label": item["label"]} for item in PATTERN_OPTIONS]
    schedule_options = SCHEDULE_OPTIONS
    presets = "".join(
        f"""
        <div class="guide-card">
          <strong>{html(item["label"])}</strong>
          <p>{html(item["description"])}</p>
        </div>
        """
        for item in PATTERN_OPTIONS
    )
    body = f"""
    <div class="modal-split">
      <div class="modal-panel">
        <form method="post" action="/dashboard/patterns/add" class="form-grid">
          {render_select("symbolId", "대상 종목", symbol_options, values.get("symbolId"), "전략을 붙일 종목 선택", required=True)}
          {render_select("patternType", "전략 템플릿", pattern_options, values.get("patternType"), "정확한 숫자로 표현 가능한 전략 위주", required=True)}
          {render_select("schedule", "감시 주기", schedule_options, values.get("schedule"), "얼마나 자주 체크할지", required=True)}
          {render_input("budget", "회당 금액/비율", values.get("budget"), "예: 회당 30만원, 보유분 25%", required=True, placeholder="회당 30만원")}
          {render_input("profitTarget", "익절 조건", values.get("profitTarget"), "예: +6%, +12% 구간 분할매도", placeholder="+6%")}
          {render_input("stopLoss", "손절 조건", values.get("stopLoss"), "예: -3%, -5% 구간 정리", placeholder="-3%")}
          <div class="field">
            <label>주문 방향 <span class="field-chip">필수</span></label>
            <div class="toggle-group">
              <label class="toggle-item"><input type="checkbox" name="buyEnabled"{checked_attr(values.get("buyEnabled") != "off")} /> 자동 매수</label>
              <label class="toggle-item"><input type="checkbox" name="sellEnabled"{checked_attr(values.get("sellEnabled") == "on")} /> 자동 매도</label>
            </div>
            <small>둘 중 하나 이상 켜야 저장됩니다.</small>
          </div>
          {render_textarea("note", "전략 메모", values.get("note"), "예: 5% 하락 시 3번 분할매수, 8% 수익 시 절반 매도", placeholder="전략 설명")}
          <div class="field field-full">
            <div class="button-row">
              <button class="button button-primary" type="submit">패턴 저장</button>
              <a class="button button-secondary" href="/dashboard?modal=ai">애매한 조건은 AI로</a>
            </div>
          </div>
        </form>
      </div>
      <div class="modal-panel">
        <h4>정량 전략 예시</h4>
        <div class="guide-panel">{presets}</div>
      </div>
    </div>
    """
    return render_modal_shell("패턴 설정", "정액·정률·주기 기반 조건은 패턴 빌더에서 정의합니다.", body, message)


def render_ai_modal(draft: dict, values: dict[str, str], message: dict | None) -> str:
    ai = draft["ai"]
    provider_value = values.get("provider") or ai.get("provider") or "openai"
    model_value = values.get("model") or ai.get("model")
    prompt_value = values.get("prompt") or ai.get("prompt")
    body = f"""
    <div class="modal-split">
      <div class="modal-panel">
        <form method="post" action="/dashboard/ai/save" class="form-grid">
          {render_select("provider", "AI 제공사", AI_PROVIDERS, provider_value, "OpenAI, Anthropic, Google 등", required=True)}
          {render_input("model", "모델명", model_value, "예: gpt-5, claude-sonnet, gemini-pro", required=True, placeholder="gpt-5")}
          {render_input("apiKey", "API 키", "", "입력 즉시 사용하고 저장은 하지 않습니다.", required=True, input_type="password", placeholder="sk-...")}
          {render_textarea("prompt", "전략 프롬프트", prompt_value, "정량화하기 어려운 조건만 자연어로 적습니다.", required=True, placeholder="예: 뉴스 급등 이후 거래량이 둔화되면 보수적으로 분할매도")}
          <div class="field field-full">
            <div class="button-row">
              <button class="button button-primary" type="submit">AI 전략 저장</button>
            </div>
          </div>
        </form>
      </div>
      <div class="modal-panel">
        <h4>AI로 넘기는 경우</h4>
        <div class="guide-panel">
          <div class="guide-card">
            <strong>추천 상황</strong>
            <p>정액, 정률, 시간 조건처럼 숫자로 바로 못 정하는 전략</p>
          </div>
          <div class="guide-card">
            <strong>실행 가드레일</strong>
            <p>AI는 신호만 만들고 최종 예산, 중복 주문, 장 시간 검증은 서버가 다시 확인</p>
          </div>
          <div class="guide-card">
            <strong>현재 상태</strong>
            <p>브로커 주문 API 연결 전까지는 전략 입력과 저장 UX를 먼저 검증</p>
          </div>
        </div>
      </div>
    </div>
    """
    return render_modal_shell("AI 전략", "정량화하기 어려운 전략만 AI 쪽으로 분리합니다.", body, message)


def render_modal(draft: dict, modal: str | None, query: dict[str, list[str]], values: dict[str, str] | None, message: dict | None, validation: dict | None) -> str:
    if modal not in MODAL_KEYS:
        return ""

    selected_broker_id = (query.get("broker", [""])[-1] or (values or {}).get("selectedBrokerId") or (values or {}).get("brokerId") or (draft["brokers"][0]["broker_id"] if draft["brokers"] else READY_BROKERS[0]["id"]))

    if modal == "broker":
        return render_broker_modal(draft, selected_broker_id, values or {}, message, validation)
    if modal == "symbol":
        return render_symbol_modal(draft, selected_broker_id, values or {}, query, message)
    if modal == "pattern":
        return render_pattern_modal(draft, values or {}, message)
    if modal == "ai":
        return render_ai_modal(draft, values or {}, message)
    return ""


def render_dashboard_page(
    draft: dict,
    *,
    query: dict[str, list[str]],
    message: dict | None = None,
    values: dict[str, str] | None = None,
    validation: dict | None = None,
) -> bytes:
    modal = recommended_modal(draft, query.get("modal", [""])[-1])
    html_body = f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>대시보드 | {html(PROJECT_TITLE)}</title>
    <link rel="stylesheet" href="/styles.css" />
  </head>
  <body class="dashboard-body">
    <div class="dashboard-shell">
      {render_topbar(draft)}
      {render_dashboard_hero(draft)}
      {render_message(message)}

      <section class="dashboard-grid">
        <article class="panel panel-wide">
          <div class="panel-head">
            <div>
              <h3>워치리스트</h3>
              <p>브로커별 종목 목록을 기반으로 자동매매 대상을 고릅니다.</p>
            </div>
            <a class="button button-secondary button-small" href="/dashboard?modal=symbol">종목 추가</a>
          </div>
          <div class="watchlist-table">{render_watchlist_rows(draft)}</div>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <h3>연결된 증권</h3>
              <p>여러 증권 계좌를 동시에 붙일 수 있습니다.</p>
            </div>
            <a class="button button-secondary button-small" href="/dashboard?modal=broker">증권 추가</a>
          </div>
          <div class="stack-list">{render_connected_brokers(draft)}</div>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <h3>정량 패턴</h3>
              <p>정액, 정률, 주기 같은 수치 기반 전략</p>
            </div>
            <a class="button button-secondary button-small" href="/dashboard?modal=pattern">패턴 설정</a>
          </div>
          <div class="stack-list">{render_pattern_rows(draft)}</div>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <h3>AI 전략</h3>
              <p>애매한 조건은 AI로 분리</p>
            </div>
            <a class="button button-secondary button-small" href="/dashboard?modal=ai">AI 전략</a>
          </div>
          {render_ai_panel(draft)}
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <h3>가이드</h3>
              <p>대시보드는 비워 두고 필요한 작업만 모달로 엽니다.</p>
            </div>
          </div>
          {render_guide_panel()}
        </article>
      </section>
    </div>

    {render_modal(draft, modal, query, values, message if modal else None, validation)}
  </body>
</html>
"""
    return html_body.encode("utf-8")


class AppHandler(BaseHTTPRequestHandler):
    server_version = "AutoStockTraderKR/0.5"

    def _send_bytes(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        *,
        include_body: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _send_html(self, body: bytes, *, include_body: bool = True, extra_headers: dict[str, str] | None = None) -> None:
        self._send_bytes(HTTPStatus.OK, body, "text/html; charset=utf-8", include_body=include_body, extra_headers=extra_headers)

    def _send_json(
        self,
        status: HTTPStatus,
        payload: dict | list,
        *,
        include_body: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8", include_body=include_body, extra_headers=extra_headers)

    def _send_redirect(self, location: str, *, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _send_static(self, path: str, *, include_body: bool) -> bool:
        relative = path.lstrip("/")
        if not relative:
            return False
        target = (ROOT / relative).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            return False
        if not target.is_file():
            return False
        body = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._send_bytes(HTTPStatus.OK, body, content_type, include_body=include_body)
        return True

    def _draft(self) -> dict:
        return load_draft(self.headers.get("Cookie"))

    def _read_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        parsed = parse_qs(raw, keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in parsed.items()}

    def _base_url(self) -> str:
        if APP_BASE_URL:
            return APP_BASE_URL.rstrip("/")
        host = self.headers.get("Host", "127.0.0.1")
        proto = self.headers.get("X-Forwarded-Proto", "http")
        return f"{proto}://{host}"

    def _route_get(self, *, include_body: bool) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)
        draft = self._draft()
        flash = flash_message_from_query(query)

        if path in {"/", "/index.html"}:
            location = root_path_for_draft(draft)
            if include_body:
                self._send_redirect(location)
            else:
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", location)
                self.end_headers()
            return

        if path == "/auth/sso/start":
            provider = trim(query.get("provider", [""])[-1], 24).lower()
            if provider not in {item["value"] for item in AUTH_PROVIDERS}:
                self._send_redirect("/login?flash=sso_failed")
                return
            base_url = self._base_url()
            if not oauth_is_configured(provider, base_url):
                self._send_redirect("/login?flash=sso_not_configured")
                return
            now = time.time()
            for key, value in list(OAUTH_PENDING.items()):
                if now - float(value.get("created_at", now)) > 900:
                    OAUTH_PENDING.pop(key, None)
            state = secrets.token_urlsafe(24)
            OAUTH_PENDING[state] = {"provider": provider, "created_at": now, "session_key": draft["profile"].get("session_key", "")}
            draft["oauth"] = {"last_state": state, "provider": provider, "started_at": now_iso()}
            self._send_redirect(
                oauth_authorize_location(provider, base_url, state),
                extra_headers={"Set-Cookie": draft_cookie_header(draft)},
            )
            return

        if path.startswith("/auth/sso/callback/"):
            provider = trim(path.rsplit("/", 1)[-1], 24).lower()
            state = trim(query.get("state", [""])[-1], 180)
            code = trim(query.get("code", [""])[-1], 240)
            if provider not in {item["value"] for item in AUTH_PROVIDERS}:
                self._send_redirect("/login?flash=sso_failed")
                return
            pending = OAUTH_PENDING.pop(state, None)
            if not pending or pending.get("provider") != provider:
                self._send_redirect("/login?flash=sso_failed")
                return
            if trim(query.get("error", [""])[-1], 64):
                self._send_redirect("/login?flash=sso_failed")
                return
            if not code:
                self._send_redirect("/login?flash=sso_failed")
                return

            try:
                token = oauth_exchange_code(provider, self._base_url(), code, state)
                profile = oauth_user_profile(provider, token)
                email = trim(profile.get("email"), 120)
                if not email:
                    raise RuntimeError("email missing from provider profile")
                nickname = trim(profile.get("name"), 80) or provider_meta(provider)["label"] + " 사용자"
            except Exception:
                self._send_redirect("/login?flash=sso_failed")
                return

            clear_runtime_state(draft)
            draft = fresh_draft()
            draft["profile"] = {
                "nickname": nickname,
                "email": email,
                "phone": "",
                "auth_provider": provider,
                "logged_in_at": now_iso(),
                "session_key": pending.get("session_key") or draft["profile"].get("session_key"),
            }
            self._send_redirect("/dashboard?flash=logged_in", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            return

        if path in {"/login", "/signup", "/find-id", "/find-password"}:
            if is_authenticated(draft):
                self._send_redirect("/dashboard")
                return
            mode = {
                "/login": "login",
                "/signup": "signup",
                "/find-id": "find-id",
                "/find-password": "find-password",
            }[path]
            self._send_html(render_auth_page(mode, flash), include_body=include_body)
            return

        if path == "/dashboard":
            if not is_authenticated(draft):
                self._send_redirect("/login")
                return
            self._send_html(render_dashboard_page(draft, query=query, message=flash), include_body=include_body)
            return

        if path == "/brokers":
            self._send_redirect("/dashboard?modal=broker")
            return

        if path == "/symbols":
            self._send_redirect("/dashboard?modal=symbol")
            return

        if path == "/patterns":
            self._send_redirect("/dashboard?modal=pattern")
            return

        if path == "/ai":
            self._send_redirect("/dashboard?modal=ai")
            return

        if path == "/healthz":
            payload = {
                "status": "ok",
                "service": f"{PROJECT_SLUG}-python",
                "brokers": len(BROKER_DETAILS),
                "build": BUILD_DATE,
            }
            self._send_json(HTTPStatus.OK, payload, include_body=include_body)
            return

        if path == "/api/v1/brokers":
            self._send_json(HTTPStatus.OK, {"items": BROKER_CATALOG}, include_body=include_body)
            return

        if path.startswith("/api/v1/brokers/") and path.endswith("/symbols"):
            broker_id = path.split("/")[-2]
            broker = get_broker_or_none(broker_id)
            if not broker:
                self._send_json(HTTPStatus.NOT_FOUND, {"detail": "broker_not_found"}, include_body=include_body)
                return
            query_symbol = trim(query.get("q", [""])[-1], 24).upper()
            catalog_payload = broker_symbol_catalog(draft, broker_id, query_symbol)
            self._send_json(
                HTTPStatus.OK,
                {
                    "broker_id": broker_id,
                    "mode": catalog_payload.get("mode"),
                    "message": catalog_payload.get("message", ""),
                    "items": catalog_payload.get("items", []),
                },
                include_body=include_body,
            )
            return

        if path.startswith("/api/v1/brokers/"):
            broker_id = path.rsplit("/", 1)[-1]
            broker = get_broker_or_none(broker_id)
            if not broker:
                self._send_json(HTTPStatus.NOT_FOUND, {"detail": "broker_not_found"}, include_body=include_body)
                return
            self._send_json(HTTPStatus.OK, broker, include_body=include_body)
            return

        if path == "/favicon.ico":
            self._send_bytes(HTTPStatus.NO_CONTENT, b"", "image/x-icon", include_body=include_body)
            return

        if self._send_static(path, include_body=include_body):
            return

        self._send_bytes(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8", include_body=include_body)

    def do_GET(self) -> None:
        self._route_get(include_body=True)

    def do_HEAD(self) -> None:
        self._route_get(include_body=False)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        draft = self._draft()

        if path == "/api/v1/account-connections/validate":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            broker = get_broker_or_none(payload.get("broker_id"))
            if not broker:
                self._send_json(HTTPStatus.NOT_FOUND, {"detail": "broker_not_found"})
                return
            result = validate_broker_values(broker, payload.get("values", {}))
            self._send_json(HTTPStatus.OK, result)
            return

        form = self._read_form()

        if path == "/auth/login":
            user_id = trim(form.get("userId"), 120)
            password = trim(form.get("password"), 120)
            if not user_id or not password:
                self._send_html(
                    render_auth_page(
                        "login",
                        {"kind": "warning", "text": "아이디와 비밀번호를 모두 입력해 주세요."},
                        form,
                    )
                )
                return

            clear_runtime_state(draft)
            draft = fresh_draft()
            draft["profile"] = {
                "nickname": nickname_from_identity(user_id),
                "email": email_from_identity(user_id),
                "phone": "",
                "auth_provider": "password",
                "logged_in_at": now_iso(),
            }
            self._send_redirect("/dashboard?flash=logged_in", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            return

        if path == "/auth/signup":
            nickname = trim(form.get("nickname"), 80)
            email = trim(form.get("email"), 120)
            password = trim(form.get("password"), 120)
            password_confirm = trim(form.get("passwordConfirm"), 120)
            if not nickname or not email or not password or not password_confirm:
                self._send_html(
                    render_auth_page(
                        "signup",
                        {"kind": "warning", "text": "이름, 이메일, 비밀번호를 모두 입력해 주세요."},
                        form,
                    )
                )
                return
            if password != password_confirm:
                self._send_html(
                    render_auth_page(
                        "signup",
                        {"kind": "warning", "text": "비밀번호와 비밀번호 확인이 일치하지 않습니다."},
                        form,
                    )
                )
                return

            clear_runtime_state(draft)
            draft = fresh_draft()
            draft["profile"] = {
                "nickname": nickname,
                "email": email,
                "phone": "",
                "auth_provider": "password",
                "logged_in_at": now_iso(),
            }
            self._send_redirect("/dashboard?flash=signed_up", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            return

        if path == "/auth/find-id":
            name = trim(form.get("name"), 80)
            phone = trim(form.get("phone"), 40)
            if not name or not phone:
                self._send_html(
                    render_auth_page(
                        "find-id",
                        {"kind": "warning", "text": "이름과 휴대폰 번호를 입력해 주세요."},
                        form,
                    )
                )
                return
            self._send_redirect("/find-id?flash=find_id_requested")
            return

        if path == "/auth/find-password":
            user_id = trim(form.get("userId"), 120)
            email = trim(form.get("email"), 120)
            if not user_id or not email:
                self._send_html(
                    render_auth_page(
                        "find-password",
                        {"kind": "warning", "text": "아이디와 이메일을 입력해 주세요."},
                        form,
                    )
                )
                return
            self._send_redirect("/find-password?flash=find_password_requested")
            return

        if path == "/auth/demo":
            provider = trim(form.get("provider"), 32)
            if provider not in {item["value"] for item in AUTH_PROVIDERS}:
                self._send_redirect("/login")
                return
            clear_runtime_state(draft)
            meta = provider_meta(provider)
            draft = fresh_draft()
            draft["profile"] = {
                "nickname": meta["label"] + " 사용자",
                "email": f'{provider}.demo@{meta["email"]}',
                "phone": "",
                "auth_provider": provider,
                "logged_in_at": now_iso(),
            }
            self._send_redirect("/dashboard?flash=logged_in", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            return

        if path == "/auth/logout":
            clear_runtime_state(draft)
            self._send_redirect("/login?flash=logged_out", extra_headers={"Set-Cookie": clear_cookie_header()})
            return

        if not is_authenticated(draft):
            self._send_redirect("/login")
            return

        if path == "/dashboard/reset":
            clear_runtime_state(draft)
            self._send_redirect("/login?flash=reset", extra_headers={"Set-Cookie": clear_cookie_header()})
            return

        if path == "/dashboard/brokers/add":
            selected_broker = form.get("selectedBrokerId") or READY_BROKERS[0]["id"]
            broker = get_broker_or_none(selected_broker)
            if not broker:
                body = render_dashboard_page(
                    draft,
                    query={"modal": ["broker"], "broker": [selected_broker]},
                    message={"kind": "warning", "text": "선택한 증권사를 찾지 못했습니다."},
                    values=form,
                )
                self._send_html(body)
                return

            validation = validate_broker_values(broker, form)
            if validation["is_supported"] and not validation["missing_fields"]:
                entry = upsert_broker_entry(draft, broker, form)
                store_broker_credentials(draft, entry["id"], broker["id"], collect_broker_secret_payload(broker, form))
                flash_key = "broker_added"
                if broker["id"] == "kis":
                    credentials = kis_parse_credentials(get_broker_credentials(draft, entry["id"]))
                    if credentials:
                        try:
                            kis_fetch_balance_snapshot(credentials)
                            BROKER_BALANCE_CACHE.pop(f"{user_runtime_key(draft)}:{entry['id']}", None)
                            flash_key = "broker_live_connected"
                        except Exception:
                            flash_key = "broker_live_warning"
                self._send_redirect(
                    f"/dashboard?flash={flash_key}&modal=symbol&broker={html(selected_broker)}",
                    extra_headers={"Set-Cookie": draft_cookie_header(draft)},
                )
                return

            body = render_dashboard_page(
                draft,
                query={"modal": ["broker"], "broker": [selected_broker]},
                message={"kind": "warning", "text": "필수 입력을 채운 뒤 다시 시도해 주세요."},
                values=form,
                validation=validation,
            )
            self._send_html(body)
            return

        if path == "/dashboard/brokers/remove":
            removed_id = trim(form.get("itemId"), 40)
            remove_broker_credentials(draft, removed_id)
            draft["brokers"] = remove_item(draft["brokers"], removed_id)
            remaining_ids = {item["broker_id"] for item in draft["brokers"]}
            draft["symbols"] = [item for item in draft["symbols"] if item["broker_id"] in remaining_ids]
            remaining_symbol_ids = {item["id"] for item in draft["symbols"]}
            draft["patterns"] = [item for item in draft["patterns"] if item["symbol_id"] in remaining_symbol_ids]
            self._send_redirect("/dashboard?flash=broker_removed", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            return

        if path == "/dashboard/symbols/add":
            success, text = add_symbol_entry(draft, form)
            if success:
                self._send_redirect("/dashboard?flash=symbol_added&modal=pattern", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            else:
                body = render_dashboard_page(
                    draft,
                    query={"modal": ["symbol"], "broker": [form.get("brokerId", "")]},
                    message={"kind": "warning", "text": text},
                    values=form,
                )
                self._send_html(body)
            return

        if path == "/dashboard/symbols/remove":
            removed_id = trim(form.get("itemId"), 40)
            draft["symbols"] = remove_item(draft["symbols"], removed_id)
            draft["patterns"] = [pattern for pattern in draft["patterns"] if pattern.get("symbol_id") != removed_id]
            self._send_redirect("/dashboard?flash=symbol_removed", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            return

        if path == "/dashboard/patterns/add":
            success, text = add_pattern_entry(draft, form)
            if success:
                self._send_redirect("/dashboard?flash=pattern_added", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            else:
                body = render_dashboard_page(
                    draft,
                    query={"modal": ["pattern"]},
                    message={"kind": "warning", "text": text},
                    values=form,
                )
                self._send_html(body)
            return

        if path == "/dashboard/patterns/remove":
            draft["patterns"] = remove_item(draft["patterns"], trim(form.get("itemId"), 40))
            self._send_redirect("/dashboard?flash=pattern_removed", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            return

        if path == "/dashboard/ai/save":
            success, text = save_ai_entry(draft, form)
            if success:
                self._send_redirect("/dashboard?flash=ai_saved", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            else:
                body = render_dashboard_page(
                    draft,
                    query={"modal": ["ai"]},
                    message={"kind": "warning", "text": text},
                    values=form,
                )
                self._send_html(body)
            return

        if path == "/dashboard/ai/clear":
            draft["ai"] = {"provider": "", "model": "", "prompt": "", "has_api_key": False, "updated_at": ""}
            self._send_redirect("/dashboard?flash=ai_cleared", extra_headers={"Set-Cookie": draft_cookie_header(draft)})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"detail": "not_found"})


def main() -> None:
    port = int(os.environ.get("PORT", "80"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
