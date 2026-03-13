#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import mimetypes
import os
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
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
COOKIE_NAME = "stock_broker_wizard_v1"
BUILD_DATE = "2026-03-13"
READY_BROKERS = [broker for broker in BROKER_DETAILS if broker["status"] == "ready"]
PATTERN_OPTIONS = [
    {"value": "dip-buy", "label": "N% 하락 시 분할매수"},
    {"value": "breakout", "label": "전고점 돌파 매수"},
    {"value": "golden-cross", "label": "이동평균 골든크로스"},
    {"value": "rsi", "label": "RSI 과매도/과매수"},
    {"value": "scheduled", "label": "정해진 시간 정액 매매"},
    {"value": "ai-assisted", "label": "AI 판단 보조"},
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
STEP_CONFIG = [
    {"number": 1, "label": "회원가입", "key": "profile"},
    {"number": 2, "label": "주가 목록", "key": "overview"},
    {"number": 3, "label": "증권 추가", "key": "brokers"},
    {"number": 4, "label": "종목 추가", "key": "symbols"},
    {"number": 5, "label": "패턴 설정", "key": "patterns"},
    {"number": 6, "label": "AI API", "key": "ai"},
]


def fresh_draft() -> dict:
    return {
        "profile": {"nickname": "", "email": "", "phone": ""},
        "brokers": [],
        "symbols": [],
        "patterns": [],
        "ai": {"provider": "", "model": "", "prompt": "", "has_api_key": False},
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
    merged["brokers"] = list(stored.get("brokers", []))[:4]
    merged["symbols"] = list(stored.get("symbols", []))[:12]
    merged["patterns"] = list(stored.get("patterns", []))[:12]
    merged["ai"].update(stored.get("ai", {}))
    return merged


def draft_cookie_header(draft: dict) -> str:
    return f"{COOKIE_NAME}={encode_cookie_value(draft)}; Path=/; Max-Age=1209600; SameSite=Lax"


def clear_cookie_header() -> str:
    return f"{COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax"


def checked_attr(enabled: bool) -> str:
    return " checked" if enabled else ""


def selected_attr(current: str | None, expected: str) -> str:
    return " selected" if current == expected else ""


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


def compute_step_state(draft: dict) -> dict[str, bool]:
    profile = draft["profile"]
    ai = draft["ai"]
    return {
        "profile": bool(profile.get("nickname") and profile.get("email")),
        "overview": bool(draft["brokers"] or draft["symbols"] or draft["patterns"] or ai.get("provider")),
        "brokers": bool(draft["brokers"]),
        "symbols": bool(draft["symbols"]),
        "patterns": bool(draft["patterns"]),
        "ai": bool(ai.get("provider") and ai.get("has_api_key")),
    }


def primary_account_label(values: dict[str, str]) -> str:
    if values.get("accountNumber"):
        return values["accountNumber"]
    if values.get("accountPrefix"):
        suffix = values.get("accountProductCode", "")
        return f"{values['accountPrefix']}-{suffix}" if suffix else values["accountPrefix"]
    if values.get("htsId"):
        return values["htsId"]
    return "연결 정보"


def upsert_broker_entry(draft: dict, broker: dict, values: dict[str, str]) -> None:
    account_label = primary_account_label(values)
    entry = {
        "id": uuid4().hex[:10],
        "broker_id": broker["id"],
        "broker_name": broker["name"],
        "environment": values.get("environment", "production"),
        "account_label": account_label,
        "saved_at": now_iso(),
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
    draft["brokers"] = [entry, *existing][:4]


def add_symbol_entry(draft: dict, form: dict[str, str]) -> tuple[bool, str]:
    broker_id = trim(form.get("brokerId"), 40)
    symbol = trim(form.get("symbol"), 24).upper()
    name = trim(form.get("symbolName"), 32) or symbol
    market = trim(form.get("market"), 16) or "KRX"

    if not broker_id or not symbol:
        return False, "종목 코드와 연결할 증권사를 입력해야 합니다."

    broker_entry = find_connected_broker(draft, broker_id)
    if not broker_entry:
        return False, "먼저 증권사를 추가해야 종목을 연결할 수 있습니다."

    item = {
        "id": uuid4().hex[:10],
        "symbol": symbol,
        "name": name,
        "market": market,
        "broker_id": broker_id,
        "broker_name": broker_entry["broker_name"],
    }

    existing = [entry for entry in draft["symbols"] if not (entry["symbol"] == symbol and entry["broker_id"] == broker_id)]
    draft["symbols"] = [item, *existing][:12]
    return True, f"{name} 종목을 목록에 추가했습니다."


def add_pattern_entry(draft: dict, form: dict[str, str]) -> tuple[bool, str]:
    symbol_id = trim(form.get("symbolId"), 40)
    pattern_type = trim(form.get("patternType"), 40)
    schedule = trim(form.get("schedule"), 40)
    budget = trim(form.get("budget"), 40)
    note = trim(form.get("note"), 160)
    buy_enabled = form.get("buyEnabled") == "on"
    sell_enabled = form.get("sellEnabled") == "on"

    if not symbol_id or not pattern_type or not schedule:
        return False, "종목, 패턴, 주기를 모두 골라야 합니다."
    if not buy_enabled and not sell_enabled:
        return False, "자동 매수나 자동 매도 중 하나 이상을 켜야 합니다."

    symbol_entry = find_symbol(draft, symbol_id)
    if not symbol_entry:
        return False, "먼저 종목을 추가한 뒤 패턴을 만들 수 있습니다."

    pattern_label = next((item["label"] for item in PATTERN_OPTIONS if item["value"] == pattern_type), pattern_type)
    schedule_label = next((item["label"] for item in SCHEDULE_OPTIONS if item["value"] == schedule), schedule)

    draft["patterns"] = [
        {
            "id": uuid4().hex[:10],
            "symbol_id": symbol_entry["id"],
            "symbol": symbol_entry["symbol"],
            "symbol_name": symbol_entry["name"],
            "pattern_type": pattern_type,
            "pattern_label": pattern_label,
            "schedule": schedule,
            "schedule_label": schedule_label,
            "buy_enabled": buy_enabled,
            "sell_enabled": sell_enabled,
            "budget": budget,
            "note": note,
        },
        *draft["patterns"],
    ][:12]
    return True, f"{symbol_entry['name']} 종목에 패턴을 추가했습니다."


def save_ai_entry(draft: dict, form: dict[str, str]) -> tuple[bool, str]:
    provider = trim(form.get("provider"), 40)
    model = trim(form.get("model"), 80)
    prompt = trim(form.get("prompt"), 320)
    api_key = trim(form.get("apiKey"), 240)

    if not provider or not model:
        return False, "AI 제공사와 모델명을 먼저 입력해야 합니다."

    draft["ai"] = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "has_api_key": bool(api_key),
        "updated_at": now_iso(),
    }
    return True, "AI 설정을 저장했습니다. API 키는 서버에 보관하지 않았습니다."


def remove_item(items: list[dict], item_id: str) -> list[dict]:
    return [item for item in items if item.get("id") != item_id]


def render_select(name: str, label: str, options: list[dict[str, str]], value: str | None, help_text: str, required: bool = False) -> str:
    required_tag = '<span class="field-chip">필수</span>' if required else '<span class="field-chip field-chip-muted">선택</span>'
    options_html = "".join(
        f'<option value="{html(option["value"])}"{selected_attr(value, option["value"])}>{html(option["label"])}</option>'
        for option in options
    )
    return f"""
    <div class="field">
      <label for="{html(name)}">{html(label)} {required_tag}</label>
      <select id="{html(name)}" name="{html(name)}">
        {options_html}
      </select>
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
      <textarea id="{html(name)}" name="{html(name)}" rows="5" placeholder="{html(placeholder)}">{html(value or '')}</textarea>
      <small>{html(help_text)}</small>
    </div>
    """


def render_message(message: dict | None) -> str:
    if not message:
        return ""
    return f'<div class="message message-{html(message["kind"])}">{html(message["text"])}</div>'


def render_progress(draft: dict) -> str:
    state = compute_step_state(draft)
    items = []
    for step in STEP_CONFIG:
        status = "완료" if state[step["key"]] else "대기"
        classes = "progress-item is-complete" if state[step["key"]] else "progress-item"
        items.append(
            f"""
            <div class="{classes}">
              <span class="progress-number">{step["number"]}</span>
              <div>
                <strong>{html(step["label"])}</strong>
                <span>{status}</span>
              </div>
            </div>
            """
        )
    return "".join(items)


def render_metric_cards(draft: dict) -> str:
    cards = [
        ("연결된 증권", len(draft["brokers"]), "API 키는 저장하지 않고 연결 메타 정보만 보관"),
        ("등록된 종목", len(draft["symbols"]), "처음에는 비어 있고 직접 추가해야 시작됩니다"),
        ("자동매매 규칙", len(draft["patterns"]), "종목별 매수/매도 조건과 주기를 관리"),
        ("AI 설정", "설정됨" if draft["ai"].get("provider") else "미설정", "AI 판단 보조는 마지막 단계에서 추가"),
    ]
    return "".join(
        f"""
        <div class="metric-card">
          <span>{html(label)}</span>
          <strong>{html(value)}</strong>
          <p>{html(note)}</p>
        </div>
        """
        for label, value, note in cards
    )


def render_profile_section(draft: dict, message: dict | None) -> str:
    profile = draft["profile"]
    return f"""
    <section id="step-1" class="section-card">
      <div class="section-header">
        <div>
          <span class="section-step">1</span>
          <h2>회원가입</h2>
          <p>서비스 기본 프로필을 먼저 잡아둡니다. 실제 인증은 나중에 붙여도 되지만, 흐름상 첫 단계에 두는 게 자연스럽습니다.</p>
        </div>
      </div>
      {render_message(message)}
      <form method="post" action="/wizard/profile" class="section-layout">
        <div class="form-panel">
          <div class="form-grid">
            {render_input("nickname", "닉네임", profile.get("nickname"), "대시보드 상단에 표시할 이름", required=True, placeholder="예: 민우")}
            {render_input("email", "이메일", profile.get("email"), "알림 메일이나 계정 복구에 쓸 주소", required=True, input_type="email", placeholder="name@example.com")}
            {render_input("phone", "연락처", profile.get("phone"), "선택 사항. 추후 주문 알림용", placeholder="010-0000-0000")}
          </div>
          <div class="button-row">
            <button class="button button-primary" type="submit">프로필 저장</button>
          </div>
        </div>
        <div class="aside-panel">
          <h3>이 단계에서 결정되는 것</h3>
          <ul class="bullet-list">
            <li>누가 이 자동매매 워크스페이스를 쓰는지</li>
            <li>이후 단계에서 보여줄 기본 사용자 정보</li>
            <li>알림/승인 흐름을 넣을 때 기준이 되는 계정 프로필</li>
          </ul>
        </div>
      </form>
    </section>
    """


def render_connected_brokers(draft: dict) -> str:
    if not draft["brokers"]:
        return """
        <div class="empty-card">
          <h3>아직 연결된 증권이 없습니다.</h3>
          <p>아래 3단계에서 키움, 한국투자, DB, LS 중 하나를 먼저 추가하면 여기부터 채워집니다.</p>
        </div>
        """

    cards = []
    for item in draft["brokers"]:
        env_label = "실전" if item["environment"] == "production" else "모의"
        cards.append(
            f"""
            <div class="list-card">
              <div class="list-card-head">
                <div>
                  <strong>{html(item["broker_name"])}</strong>
                  <span>{html(item["account_label"])}</span>
                </div>
                <span class="mini-status">{html(env_label)}</span>
              </div>
              <form method="post" action="/wizard/brokers/remove" class="inline-form">
                <input type="hidden" name="itemId" value="{html(item['id'])}" />
                <button class="button button-ghost button-small" type="submit">삭제</button>
              </form>
            </div>
            """
        )
    return "".join(cards)


def render_symbol_rows(draft: dict) -> str:
    if not draft["symbols"]:
        return """
        <div class="empty-card">
          <h3>주가 목록이 비어 있습니다.</h3>
          <p>종목을 추가하면 여기서 연결된 증권사와 함께 관리됩니다. 현재가는 아직 미연동 상태라 빈 값으로 남겨둡니다.</p>
        </div>
        """

    rows = []
    for item in draft["symbols"]:
        rule_count = sum(1 for pattern in draft["patterns"] if pattern["symbol_id"] == item["id"])
        rows.append(
            f"""
            <div class="table-row">
              <div>
                <strong>{html(item["name"])}</strong>
                <span>{html(item["symbol"])} · {html(item["market"])}</span>
              </div>
              <span>{html(item["broker_name"])}</span>
              <span>미연동</span>
              <span>{rule_count}개 규칙</span>
              <form method="post" action="/wizard/symbols/remove" class="inline-form">
                <input type="hidden" name="itemId" value="{html(item['id'])}" />
                <button class="button button-ghost button-small" type="submit">삭제</button>
              </form>
            </div>
            """
        )
    return "".join(rows)


def render_pattern_list(draft: dict) -> str:
    if not draft["patterns"]:
        return """
        <div class="empty-card">
          <h3>자동매매 규칙이 없습니다.</h3>
          <p>종목을 추가한 뒤에 매수/매도 패턴과 주기를 지정하면 여기서 한눈에 볼 수 있습니다.</p>
        </div>
        """

    cards = []
    for item in draft["patterns"]:
        sides = []
        if item["buy_enabled"]:
            sides.append("자동 매수")
        if item["sell_enabled"]:
            sides.append("자동 매도")
        budget = item["budget"] or "예산 미정"
        note = item["note"] or "설명 없음"
        cards.append(
            f"""
            <div class="list-card">
              <div class="list-card-head">
                <div>
                  <strong>{html(item["symbol_name"])}</strong>
                  <span>{html(item["pattern_label"])} · {html(item["schedule_label"])}</span>
                </div>
                <span class="mini-status">{html(' / '.join(sides))}</span>
              </div>
              <p class="list-note">{html(budget)} · {html(note)}</p>
              <form method="post" action="/wizard/patterns/remove" class="inline-form">
                <input type="hidden" name="itemId" value="{html(item['id'])}" />
                <button class="button button-ghost button-small" type="submit">삭제</button>
              </form>
            </div>
            """
        )
    return "".join(cards)


def render_ai_summary(draft: dict) -> str:
    ai = draft["ai"]
    if not ai.get("provider"):
        return """
        <div class="empty-card">
          <h3>AI 설정이 아직 없습니다.</h3>
          <p>OpenAI나 Anthropic 같은 외부 모델을 연결하고, 텍스트 기반 규칙 프롬프트를 마지막 단계에서 추가합니다.</p>
        </div>
        """

    provider_label = next((item["label"] for item in AI_PROVIDERS if item["value"] == ai["provider"]), ai["provider"])
    prompt_preview = ai.get("prompt") or "프롬프트 없음"
    return f"""
    <div class="list-card">
      <div class="list-card-head">
        <div>
          <strong>{html(provider_label)}</strong>
          <span>{html(ai.get("model", "모델 미지정"))}</span>
        </div>
        <span class="mini-status">{'API 키 입력됨' if ai.get('has_api_key') else 'API 키 미입력'}</span>
      </div>
      <p class="list-note">{html(prompt_preview)}</p>
      <form method="post" action="/wizard/ai/clear" class="inline-form">
        <button class="button button-ghost button-small" type="submit">초기화</button>
      </form>
    </div>
    """


def render_overview_section(draft: dict) -> str:
    return f"""
    <section id="step-2" class="section-card">
      <div class="section-header">
        <div>
          <span class="section-step">2</span>
          <h2>주가 목록</h2>
          <p>처음에는 비어 있는 목록입니다. 증권을 연결하고 종목을 추가할수록 아래 보드가 채워집니다.</p>
        </div>
      </div>
      <div class="metric-grid">
        {render_metric_cards(draft)}
      </div>
      <div class="section-layout overview-layout">
        <div class="panel-group">
          <div class="panel-card">
            <div class="panel-card-head">
              <h3>연결된 증권 목록</h3>
              <span>{len(draft["brokers"])}개</span>
            </div>
            <div class="stack-list">
              {render_connected_brokers(draft)}
            </div>
          </div>
          <div class="panel-card">
            <div class="panel-card-head">
              <h3>자동매매 패턴</h3>
              <span>{len(draft["patterns"])}개</span>
            </div>
            <div class="stack-list">
              {render_pattern_list(draft)}
            </div>
          </div>
        </div>
        <div class="panel-card">
          <div class="panel-card-head">
            <h3>종목 목록</h3>
            <span>{len(draft["symbols"])}개</span>
          </div>
          <div class="table-head">
            <span>종목</span>
            <span>연결 증권</span>
            <span>현재가</span>
            <span>규칙</span>
            <span></span>
          </div>
          <div class="table-body">
            {render_symbol_rows(draft)}
          </div>
          <div class="panel-card-head panel-card-footer">
            <h3>AI 연동</h3>
            <span>{'완료' if draft['ai'].get('provider') else '대기'}</span>
          </div>
          {render_ai_summary(draft)}
        </div>
      </div>
    </section>
    """


def render_capabilities(broker: dict) -> str:
    items = []
    labels = {"quote": "주가 확인", "buy": "자동 매수", "sell": "자동 매도", "balance": "잔고 확인"}
    for key, label in labels.items():
        capability = CAPABILITY_META[broker["capability"][key]]
        items.append(f'<span class="capability-pill {html(capability["className"])}">{html(label)} · {html(capability["label"])}</span>')
    return "".join(items)


def render_broker_picker(selected_broker_id: str) -> str:
    chips = []
    for broker in BROKER_DETAILS:
        status = STATUS_META[broker["status"]]
        classes = "broker-chip is-active" if broker["id"] == selected_broker_id else "broker-chip"
        chips.append(
            f"""
            <a class="{classes}" href="/?broker={html(broker['id'])}#step-3">
              <strong>{html(broker['name'])}</strong>
              <span>{html(status['label'])}</span>
            </a>
            """
        )
    return "".join(chips)


def render_broker_form(broker: dict, values: dict[str, str], message: dict | None, validation: dict | None) -> str:
    status = STATUS_META[broker["status"]]
    guide_items = "".join(f"<li>{html(step)}</li>" for step in broker.get("steps", []))
    source_items = "".join(
        f'<li><a class="inline-link" href="{html(source["url"])}" target="_blank" rel="noreferrer">{html(source["label"])}</a></li>'
        for source in broker.get("sources", [])
    )

    if broker["status"] != "ready":
        return f"""
        <div class="panel-card">
          <div class="panel-card-head">
            <h3>{html(broker["name"])}</h3>
            <span class="status-pill {html(status["className"])}">{html(status["label"])}</span>
          </div>
          <p class="section-copy">{html(broker["summary"])}</p>
          <div class="capability-row">{render_capabilities(broker)}</div>
          <div class="empty-card">
            <h3>이 증권사는 지금 바로 연결하지 않습니다.</h3>
            <p>{html(status["description"])} 상태라서, 현재는 안내와 공식 링크만 제공합니다.</p>
          </div>
          <div class="guide-grid">
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
        state_text = "기본 필드 검증 통과" if not missing and validation.get("is_supported") else "입력 보완 필요"
        warning_items = "".join(f"<li>{html(item)}</li>" for item in warnings)
        missing_text = f"누락 필드: {html(', '.join(missing))}" if missing else "누락된 필수 필드는 없습니다."
        validation_html = f"""
        <div class="message message-{'success' if not missing else 'warning'}">
          <strong>{html(state_text)}</strong><br />
          {missing_text}
          {'<ul class="bullet-list compact-list">' + warning_items + '</ul>' if warnings else ''}
        </div>
        """

    return f"""
    <div class="panel-card">
      <div class="panel-card-head">
        <div>
          <h3>{html(broker["name"])}</h3>
          <span>{html(broker["summary"])}</span>
        </div>
        <span class="status-pill {html(status["className"])}">{html(status["label"])}</span>
      </div>
      <div class="capability-row">{render_capabilities(broker)}</div>
      {render_message(message)}
      {validation_html}
      <form method="post" action="/wizard/broker/add" class="form-grid">
        <input type="hidden" name="selectedBrokerId" value="{html(broker['id'])}" />
        {''.join(fields_html)}
        <div class="field field-full">
          <div class="button-row">
            <button class="button button-primary" type="submit">증권 추가</button>
          </div>
          <small>API 키 원문은 저장하지 않고, 연결된 증권 메타 정보만 이 브라우저에 임시 보관합니다.</small>
        </div>
      </form>
      <div class="guide-grid">
        <div>
          <h4>가이드</h4>
          <ol class="bullet-list ordered-list">{guide_items}</ol>
        </div>
        <div>
          <h4>공식 링크</h4>
          <ul class="bullet-list">{source_items}</ul>
        </div>
      </div>
    </div>
    """


def render_broker_section(draft: dict, selected_broker_id: str, values: dict[str, str], message: dict | None, validation: dict | None) -> str:
    broker = get_broker_or_none(selected_broker_id) or READY_BROKERS[0]
    return f"""
    <section id="step-3" class="section-card">
      <div class="section-header">
        <div>
          <span class="section-step">3</span>
          <h2>증권 추가</h2>
          <p>지원 상태를 먼저 보고, 바로 연결 가능한 증권사만 단계적으로 붙입니다. 여기서는 계좌 메타 정보만 연결하고 실제 키는 저장하지 않습니다.</p>
        </div>
      </div>
      <div class="broker-picker">{render_broker_picker(broker["id"])}</div>
      {render_broker_form(broker, values, message, validation)}
    </section>
    """


def render_symbol_section(draft: dict, values: dict[str, str], message: dict | None) -> str:
    broker_options = [{"value": item["broker_id"], "label": f'{item["broker_name"]} · {item["account_label"]}'} for item in draft["brokers"]]
    markets = [
        {"value": "KRX", "label": "국내주식"},
        {"value": "NASDAQ", "label": "미국주식"},
        {"value": "NYSE", "label": "뉴욕거래소"},
        {"value": "ETF", "label": "ETF"},
    ]
    empty = not broker_options
    content = """
      <div class="empty-card">
        <h3>먼저 증권을 추가해야 합니다.</h3>
        <p>3단계에서 하나 이상의 증권 계정을 등록해야 종목을 연결할 수 있습니다.</p>
      </div>
    """
    if not empty:
        content = f"""
        <form method="post" action="/wizard/symbols/add" class="form-grid">
          {render_select("brokerId", "연결 증권", broker_options, values.get("brokerId"), "어느 증권사 계좌로 이 종목을 관리할지 선택", required=True)}
          {render_input("symbol", "종목 코드", values.get("symbol"), "예: 005930, AAPL", required=True, placeholder="005930")}
          {render_input("symbolName", "종목명", values.get("symbolName"), "비워두면 종목 코드로 표시", placeholder="삼성전자")}
          {render_select("market", "시장", markets, values.get("market") or "KRX", "국내/해외 구분용", required=True)}
          <div class="field field-full">
            <div class="button-row">
              <button class="button button-primary" type="submit">종목 추가</button>
            </div>
          </div>
        </form>
        """

    return f"""
    <section id="step-4" class="section-card">
      <div class="section-header">
        <div>
          <span class="section-step">4</span>
          <h2>종목 추가</h2>
          <p>자동매매 대상으로 보고 싶은 종목을 하나씩 담습니다. 처음엔 비어 있고, 연결한 증권과 짝을 지어 등록합니다.</p>
        </div>
      </div>
      {render_message(message)}
      <div class="section-layout">
        <div class="form-panel">
          {content}
        </div>
        <div class="aside-panel">
          <h3>현재 종목 목록</h3>
          <div class="stack-list">
            {render_symbol_rows(draft)}
          </div>
        </div>
      </div>
    </section>
    """


def render_pattern_section(draft: dict, values: dict[str, str], message: dict | None) -> str:
    symbol_options = [{"value": item["id"], "label": f'{item["name"]} ({item["symbol"]})'} for item in draft["symbols"]]
    content = """
      <div class="empty-card">
        <h3>먼저 종목을 추가해야 합니다.</h3>
        <p>4단계에서 종목을 넣어야 어떤 종목에 어떤 패턴을 적용할지 고를 수 있습니다.</p>
      </div>
    """
    if symbol_options:
        content = f"""
        <form method="post" action="/wizard/patterns/add" class="form-grid">
          {render_select("symbolId", "대상 종목", symbol_options, values.get("symbolId"), "어떤 종목에 규칙을 붙일지 선택", required=True)}
          {render_select("patternType", "패턴", PATTERN_OPTIONS, values.get("patternType"), "매수/매도 조건 템플릿", required=True)}
          {render_select("schedule", "주기", SCHEDULE_OPTIONS, values.get("schedule"), "얼마나 자주 확인할지", required=True)}
          {render_input("budget", "예산/한도", values.get("budget"), "예: 회당 30만원, 보유분 20% 매도", placeholder="회당 30만원")}
          <div class="field">
            <label>매수/매도 활성화</label>
            <div class="toggle-group">
              <label class="toggle-item"><input type="checkbox" name="buyEnabled"{checked_attr(values.get("buyEnabled") == "on")} /> 자동 매수</label>
              <label class="toggle-item"><input type="checkbox" name="sellEnabled"{checked_attr(values.get("sellEnabled") == "on")} /> 자동 매도</label>
            </div>
            <small>둘 중 하나 이상 선택해야 규칙이 저장됩니다.</small>
          </div>
          {render_textarea("note", "설명", values.get("note"), "예: 5% 하락 시 분할매수, 8% 상승 시 절반 매도", placeholder="조건 설명을 자유롭게 적어도 됩니다.")}
          <div class="field field-full">
            <div class="button-row">
              <button class="button button-primary" type="submit">패턴 추가</button>
            </div>
          </div>
        </form>
        """

    return f"""
    <section id="step-5" class="section-card">
      <div class="section-header">
        <div>
          <span class="section-step">5</span>
          <h2>패턴 설정</h2>
          <p>종목별로 자동 매수와 자동 매도를 어떤 패턴으로 돌릴지, 그리고 얼마나 자주 체크할지 정합니다.</p>
        </div>
      </div>
      {render_message(message)}
      <div class="section-layout">
        <div class="form-panel">
          {content}
        </div>
        <div class="aside-panel">
          <h3>현재 자동매매 규칙</h3>
          <div class="stack-list">
            {render_pattern_list(draft)}
          </div>
        </div>
      </div>
    </section>
    """


def render_ai_section(draft: dict, values: dict[str, str], message: dict | None) -> str:
    ai = draft["ai"]
    provider_value = values.get("provider") or ai.get("provider")
    model_value = values.get("model") or ai.get("model")
    prompt_value = values.get("prompt") or ai.get("prompt")
    return f"""
    <section id="step-6" class="section-card">
      <div class="section-header">
        <div>
          <span class="section-step">6</span>
          <h2>AI API 추가</h2>
          <p>마지막 단계에서는 외부 AI 모델을 붙이고, 자연어 텍스트로 패턴을 설명합니다. 실제 주문 전에는 항상 별도 룰 엔진 검증이 필요합니다.</p>
        </div>
      </div>
      {render_message(message)}
      <div class="section-layout">
        <div class="form-panel">
          <form method="post" action="/wizard/ai/save" class="form-grid">
            {render_select("provider", "AI 제공사", AI_PROVIDERS, provider_value or "openai", "OpenAI, Anthropic, Google 등", required=True)}
            {render_input("model", "모델명", model_value, "예: gpt-5, claude-sonnet, gemini-pro", required=True, placeholder="gpt-5")}
            {render_input("apiKey", "API 키", "", "입력 즉시 사용하고 저장은 하지 않습니다.", required=True, input_type="password", placeholder="sk-...")}
            {render_textarea("prompt", "패턴 프롬프트", prompt_value, "예: 삼성전자는 장중 변동성이 2% 이상이면 분할매수, 5% 수익이면 절반 매도", required=True, placeholder="자연어로 패턴을 적어주세요.")}
            <div class="field field-full">
              <div class="button-row">
                <button class="button button-primary" type="submit">AI 설정 저장</button>
              </div>
            </div>
          </form>
        </div>
        <div class="aside-panel">
          <h3>현재 AI 설정</h3>
          {render_ai_summary(draft)}
          <div class="empty-card subtle-card">
            <h3>다음 단계</h3>
            <p>이 다음부터는 실제 브로커 어댑터, 시세 조회, 패턴 워커, 주문 승인/리스크 검증을 붙이면 됩니다.</p>
          </div>
        </div>
      </div>
    </section>
    """


def render_home_page(
    draft: dict,
    *,
    selected_broker_id: str | None = None,
    profile_message: dict | None = None,
    broker_message: dict | None = None,
    broker_validation: dict | None = None,
    broker_values: dict[str, str] | None = None,
    symbol_message: dict | None = None,
    symbol_values: dict[str, str] | None = None,
    pattern_message: dict | None = None,
    pattern_values: dict[str, str] | None = None,
    ai_message: dict | None = None,
    ai_values: dict[str, str] | None = None,
    page_message: dict | None = None,
) -> bytes:
    selected = selected_broker_id or READY_BROKERS[0]["id"]
    document = f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Auto Trading Setup Flow</title>
    <link rel="stylesheet" href="/styles.css" />
  </head>
  <body>
    <div class="app-shell">
      <header class="hero-card">
        <div class="hero-copy">
          <span class="hero-kicker">Auto Trading Setup</span>
          <h1>한 번에 다 보여주지 말고, 순서대로 설정하는 자동매매 온보딩</h1>
          <p>
            회원가입부터 증권 추가, 종목 선택, 자동 매수/매도 패턴, AI API 연결까지
            단계별로 쌓아가는 구조입니다. 모바일에서도 위에서 아래로 내려가며 입력할 수 있게
            구성했습니다.
          </p>
        </div>
        <div class="hero-side">
          <div class="hero-stat">
            <span>배포 버전</span>
            <strong>{BUILD_DATE}</strong>
          </div>
          <div class="hero-stat">
            <span>지원 증권</span>
            <strong>{len(BROKER_DETAILS)}개</strong>
          </div>
          <form method="post" action="/wizard/reset">
            <button class="button button-ghost" type="submit">임시 설정 초기화</button>
          </form>
        </div>
      </header>

      {render_message(page_message)}

      <section class="progress-card">
        <div class="progress-grid">
          {render_progress(draft)}
        </div>
      </section>

      <main class="flow-stack">
        {render_profile_section(draft, profile_message)}
        {render_overview_section(draft)}
        {render_broker_section(draft, selected, broker_values or {}, broker_message, broker_validation)}
        {render_symbol_section(draft, symbol_values or {}, symbol_message)}
        {render_pattern_section(draft, pattern_values or {}, pattern_message)}
        {render_ai_section(draft, ai_values or {}, ai_message)}
      </main>
    </div>
  </body>
</html>
"""
    return document.encode("utf-8")


class AppHandler(BaseHTTPRequestHandler):
    server_version = "StockBrokerOnboardingPython/0.3"

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
        self._send_bytes(
            HTTPStatus.OK,
            body,
            "text/html; charset=utf-8",
            include_body=include_body,
            extra_headers=extra_headers,
        )

    def _send_json(
        self,
        status: HTTPStatus,
        payload: dict | list,
        *,
        include_body: bool = True,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._send_bytes(
            status,
            body,
            "application/json; charset=utf-8",
            include_body=include_body,
            extra_headers=extra_headers,
        )

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

    def _render_with_cookie(self, draft: dict, html_body: bytes) -> None:
        self._send_html(html_body, extra_headers={"Set-Cookie": draft_cookie_header(draft)})

    def _route_get(self, *, include_body: bool) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)

        if path in {"/", "/index.html"}:
            draft = self._draft()
            selected_broker = query.get("broker", [READY_BROKERS[0]["id"]])[-1]
            body = render_home_page(draft, selected_broker_id=selected_broker)
            self._send_html(body, include_body=include_body)
            return

        if path == "/healthz":
            self._send_json(
                HTTPStatus.OK,
                {"status": "ok", "service": "stock-broker-onboarding-python", "brokers": len(BROKER_DETAILS)},
                include_body=include_body,
            )
            return

        if path == "/api/v1/brokers":
            self._send_json(HTTPStatus.OK, {"items": BROKER_CATALOG}, include_body=include_body)
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

        if path == "/wizard/reset":
            body = render_home_page(fresh_draft(), page_message={"kind": "success", "text": "임시 설정을 모두 초기화했습니다."})
            self._send_html(body, extra_headers={"Set-Cookie": clear_cookie_header()})
            return

        form = self._read_form()

        if path == "/wizard/profile":
            draft["profile"] = {
                "nickname": trim(form.get("nickname"), 32),
                "email": trim(form.get("email"), 120),
                "phone": trim(form.get("phone"), 32),
            }
            body = render_home_page(draft, profile_message={"kind": "success", "text": "프로필을 저장했습니다."})
            self._render_with_cookie(draft, body)
            return

        if path == "/wizard/broker/add":
            selected_broker = form.get("selectedBrokerId") or READY_BROKERS[0]["id"]
            broker = get_broker_or_none(selected_broker)
            if not broker:
                body = render_home_page(draft, page_message={"kind": "warning", "text": "선택한 증권사를 찾지 못했습니다."})
                self._send_html(body)
                return
            validation = validate_broker_values(broker, form)
            if validation["is_supported"] and not validation["missing_fields"]:
                upsert_broker_entry(draft, broker, form)
                body = render_home_page(
                    draft,
                    selected_broker_id=selected_broker,
                    broker_message={"kind": "success", "text": f"{broker['name']} 증권을 연결 목록에 추가했습니다."},
                    broker_validation=validation,
                    broker_values={},
                )
                self._render_with_cookie(draft, body)
                return

            body = render_home_page(
                draft,
                selected_broker_id=selected_broker,
                broker_message={"kind": "warning", "text": "필수 입력을 확인한 뒤 다시 추가해 주세요."},
                broker_validation=validation,
                broker_values=form,
            )
            self._send_html(body)
            return

        if path == "/wizard/brokers/remove":
            draft["brokers"] = remove_item(draft["brokers"], trim(form.get("itemId"), 40))
            body = render_home_page(draft, broker_message={"kind": "success", "text": "증권 연결을 삭제했습니다."})
            self._render_with_cookie(draft, body)
            return

        if path == "/wizard/symbols/add":
            success, text = add_symbol_entry(draft, form)
            body = render_home_page(
                draft,
                symbol_message={"kind": "success" if success else "warning", "text": text},
                symbol_values={} if success else form,
            )
            if success:
                self._render_with_cookie(draft, body)
            else:
                self._send_html(body)
            return

        if path == "/wizard/symbols/remove":
            removed_id = trim(form.get("itemId"), 40)
            draft["symbols"] = remove_item(draft["symbols"], removed_id)
            draft["patterns"] = [pattern for pattern in draft["patterns"] if pattern.get("symbol_id") != removed_id]
            body = render_home_page(draft, symbol_message={"kind": "success", "text": "종목과 연결된 규칙을 함께 삭제했습니다."})
            self._render_with_cookie(draft, body)
            return

        if path == "/wizard/patterns/add":
            success, text = add_pattern_entry(draft, form)
            body = render_home_page(
                draft,
                pattern_message={"kind": "success" if success else "warning", "text": text},
                pattern_values={} if success else form,
            )
            if success:
                self._render_with_cookie(draft, body)
            else:
                self._send_html(body)
            return

        if path == "/wizard/patterns/remove":
            draft["patterns"] = remove_item(draft["patterns"], trim(form.get("itemId"), 40))
            body = render_home_page(draft, pattern_message={"kind": "success", "text": "자동매매 규칙을 삭제했습니다."})
            self._render_with_cookie(draft, body)
            return

        if path == "/wizard/ai/save":
            success, text = save_ai_entry(draft, form)
            body = render_home_page(
                draft,
                ai_message={"kind": "success" if success else "warning", "text": text},
                ai_values={} if success else form,
            )
            if success:
                self._render_with_cookie(draft, body)
            else:
                self._send_html(body)
            return

        if path == "/wizard/ai/clear":
            draft["ai"] = {"provider": "", "model": "", "prompt": "", "has_api_key": False}
            body = render_home_page(draft, ai_message={"kind": "success", "text": "AI 설정을 초기화했습니다."})
            self._render_with_cookie(draft, body)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"detail": "not_found"})


def main() -> None:
    port = int(os.environ.get("PORT", "80"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
