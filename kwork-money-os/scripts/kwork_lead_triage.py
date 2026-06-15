#!/usr/bin/env python3
"""Offline triage for Kwork Lead Radar results.

This script never opens a browser and never sends proposals. It reads the
locally saved Lead Radar JSONL, removes duplicates and unsafe projects, then
writes local shortlist cards and copy-paste proposal drafts.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from _common import DATA, REPORTS, ROOT, ensure_dir
from account_optimizer_common import redact_text


EXPECTED_REPO_ROOT = Path("/home/zerro/projects/browser-command-center")
REPO_ROOT = ROOT.parent
DEFAULT_INPUT = DATA / "leads" / "kwork_leads.jsonl"
SHORTLIST_DIR = DATA / "leads" / "shortlist"
SHORTLIST_REPORT = REPORTS / "lead_shortlist.md"
TOP5_REPORT = REPORTS / "top_5_proposals.md"

GENERIC_TITLES = {
    "",
    "Биржа проектов",
    "Рубрики",
    "Kwork",
    "Кворк",
    "Проект",
}

HIGH_RISK_PATTERNS = [
    (re.compile(r"captcha|капч", re.I), "captcha"),
    (re.compile(r"bypass|обход\s+защит|обойти\s+защит|антибот|анти-бот", re.I), "bypass/anti-bot"),
    (re.compile(r"\bспам\b|рассылк|массов(ая|ые|о)\s+регистрац", re.I), "spam/mass registration"),
    (re.compile(r"накрут", re.I), "manipulation/boosting"),
    (re.compile(r"чуж(ой|ие|их)\s+аккаунт|доступ\s+к\s+аккаунт|личн(ый|ые)\s+кабинет", re.I), "third-party accounts"),
    (re.compile(r"плат[её]ж|вывод(ы| средств)?|банк(овск|инг)|кошел[её]к", re.I), "payments/withdrawals"),
    (re.compile(r"парсинг[^\n.]{0,90}(обход|капч|блокиров|антибот)", re.I), "unsafe parsing"),
]

BOT_PATTERN = re.compile(r"telegram|телеграм|(?<![а-яёa-z])бот(?:а|ов|ы)?(?![а-яёa-z])", re.I)

GOOD_PATTERNS = [
    (BOT_PATTERN, 14, "Telegram bot scope"),
    (re.compile(r"google\s*sheets|google таблиц|гугл таблиц|таблиц", re.I), 12, "Google Sheets fit"),
    (re.compile(r"api|webhook|интеграц|яндекс директ|direct", re.I), 10, "API/integration fit"),
    (re.compile(r"python|скрипт|автоматизац|отч[её]т|crm|парсер|docker", re.I), 9, "Python automation fit"),
    (re.compile(r"заявк|форма|уведомлен|лид", re.I), 7, "request workflow"),
]

CLARITY_PATTERNS = [
    re.compile(r"нужно|требуется|необходимо|сделать|добавить|настроить|цель проекта", re.I),
    re.compile(r"\b\d+\.\s+\S+", re.I),
    re.compile(r"метрик|пол[ея]|вкладк|инструкц|пример|формат", re.I),
]


@dataclass
class Lead:
    raw: dict[str, Any]
    source_index: int
    lead_id: str
    project_id: str
    key: str
    title: str
    url: str
    buyer_username: str
    budget: str
    deadline: str
    category: str
    project_text: str
    proposals_count: str
    posted_time: str
    match_score: int
    risk_score: int
    recommended_price: int
    recommended_deadline: str
    why_match: list[str] = field(default_factory=list)
    why_risky: list[str] = field(default_factory=list)

    @property
    def is_project_url(self) -> bool:
        return bool(self.project_id)


@dataclass
class TriagedLead:
    lead: Lead
    competition_penalty: int
    budget_fit_bonus: int
    clarity_bonus: int
    final_score: int
    high_risk: bool
    high_risk_reasons: list[str]
    verdict: str
    execution_plan: list[str]
    questions: list[str]
    proposal: str


@dataclass
class TriageStats:
    input_count: int = 0
    deduplicated_count: int = 0
    skipped_invalid_url: int = 0
    removed_high_risk: int = 0
    shortlist_count: int = 0
    top5_count: int = 0
    git_commit: str = ""


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def validate_root() -> str:
    git_root = Path(run_git(["rev-parse", "--show-toplevel"]))
    if git_root != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong git root: {git_root}. Expected: {EXPECTED_REPO_ROOT}")
    if REPO_ROOT != EXPECTED_REPO_ROOT:
        raise SystemExit(f"Wrong script root: {REPO_ROOT}. Expected: {EXPECTED_REPO_ROOT}")
    return run_git(["rev-parse", "HEAD"])


def resolve_input(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path.resolve()
    root_path = ROOT / path
    if root_path.exists():
        return root_path.resolve()
    return cwd_path.resolve()


def clean(value: Any, limit: int = 1200) -> str:
    return redact_text(value, limit)


def project_id_from_url(url: str) -> str:
    match = re.search(r"/projects/(\d+)", url or "")
    return match.group(1) if match else ""


def normalized_key(url: str, title: str, text: str) -> tuple[str, str]:
    project_id = project_id_from_url(url)
    if project_id:
        return project_id, f"project:{project_id}"
    normalized_url = (url or "").split("#", 1)[0].rstrip("/")
    if normalized_url:
        return "", f"url:{normalized_url}"
    fallback = re.sub(r"\W+", "-", f"{title} {text[:120]}".lower(), flags=re.I).strip("-")
    return "", f"text:{fallback[:120]}"


def noisy_title(value: str) -> bool:
    return (
        value in GENERIC_TITLES
        or "Открыть урок" in value
        or "Показать:" in value
        or "Все предложения Новые Просмотренные" in value
    )


def derive_title(title: str, text: str) -> str:
    candidate = clean(title, 180)
    if not noisy_title(candidate) and len(candidate) > 6:
        return candidate

    normalized = re.sub(r"\s+", " ", text).strip()
    patterns = [
        r"К списку проектов\s+(.+?)(?:\s+(?:Нужно|Требуется|Необходимо|Цель проекта|Описание|Есть)\b)",
        r"К списку проектов\s+(.{12,160}?)(?:\s+Желаемый бюджет|\s+Допустимый|\s+K\s+Покупатель)",
        r"Новые\s+Просмотренные\s+(?:ПРОСМОТРЕНО\s+)?(.{8,150}?)(?:\s+(?:Нужно|Требуется|Необходимо|Есть|Я занимаюсь|Планируется|Добрый день|Привет|Ищу|Цель проекта)\b)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.I | re.S)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" -–—:;")
            value = re.sub(r"\bдля(?=[а-яё])", "для ", value, flags=re.I)
            if value and not noisy_title(value):
                return clean(value, 180)

    for sentence in re.split(r"(?<=[.!?])\s+|\s{2,}", normalized):
        sentence = sentence.strip(" -–—:;")
        if 18 <= len(sentence) <= 180 and not sentence.startswith("ФРИЛАНС МАРКЕТПЛЕЙС") and not noisy_title(sentence):
            return clean(sentence, 180)
    return candidate or "Kwork project"


def focus_project_text(title: str, text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""

    search_titles = [title, title.replace("для ", "для")]
    start = -1
    for search_title in search_titles:
        if not search_title:
            continue
        match = re.search(re.escape(search_title), normalized, re.I)
        if match:
            start = match.start()
            break
    if start < 0:
        return clean(normalized, 5000)

    segment = normalized[start:]
    end_match = re.search(r"Предложений:\s*\d+", segment, re.I)
    if end_match:
        segment = segment[: end_match.end()]
    return clean(segment, 3000)


def match_reasons(lead: Lead) -> list[str]:
    combined = f"{lead.title}\n{lead.category}\n{lead.project_text}"
    reasons = [reason for pattern, _points, reason in GOOD_PATTERNS if pattern.search(combined)]
    return reasons or ["general automation fit"]


def has_bot_scope(text: str) -> bool:
    return bool(BOT_PATTERN.search(text))


def parse_money_values(*texts: str) -> list[int]:
    combined = "\n".join(texts)
    values: list[int] = []
    pattern = re.compile(
        r"(?<!\d)(\d{1,3}(?:[\s.]\d{3})+|\d{4,6})\s*(?:₽|руб\.?|р\.|RUB)?",
        re.I,
    )
    for match in pattern.finditer(combined):
        value = int(re.sub(r"\D", "", match.group(1)))
        if 1000 <= value <= 500000:
            values.append(value)
    return values


def parse_count(value: str) -> int | None:
    text = value or ""
    match = re.search(r"(\d{1,3})\s*(?:предлож|отклик|заяв)", text, re.I)
    if match:
        return int(match.group(1))
    if text.strip().isdigit():
        return int(text.strip())
    return None


def parse_deadline_days(value: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*(?:дн|день|дня|дней)", value or "", re.I)
    return int(match.group(1)) if match else None


def listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean(item, 220) for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [clean(text, 220)] if text else []


def load_leads(path: Path) -> list[Lead]:
    if not path.exists():
        raise SystemExit(f"Lead Radar JSONL not found: {path}")

    leads: list[Lead] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit(f"Invalid JSONL at line {index}: {error}") from error

        raw_title = clean(item.get("title") or "", 180)
        project_text = clean(item.get("project_text") or "", 5000)
        title = derive_title(raw_title, project_text)
        project_text = focus_project_text(title, project_text)
        url = clean(item.get("url") or "", 300)
        project_id, key = normalized_key(url, title, project_text)
        lead_id = clean(item.get("lead_id") or key, 120)
        budget = clean(item.get("budget") or "", 160)
        deadline = clean(item.get("deadline") or "", 120)
        proposals_count = clean(item.get("proposals_count") or "", 120)
        leads.append(
            Lead(
                raw=item,
                source_index=index,
                lead_id=lead_id,
                project_id=project_id,
                key=key,
                title=title,
                url=url,
                buyer_username=clean(item.get("buyer_username") or "", 80),
                budget=budget,
                deadline=deadline,
                category=clean(item.get("category") or "", 120),
                project_text=project_text,
                proposals_count=proposals_count,
                posted_time=clean(item.get("posted_time") or "", 120),
                match_score=int(item.get("match_score") or 0),
                risk_score=int(item.get("risk_score") or 0),
                recommended_price=int(item.get("recommended_price") or 0),
                recommended_deadline=clean(item.get("recommended_deadline") or "", 80),
                why_match=listify(item.get("why_match")),
                why_risky=listify(item.get("why_risky")),
            )
        )
    return leads


def deduplicate(leads: list[Lead]) -> list[Lead]:
    selected: dict[str, Lead] = {}
    for lead in leads:
        current = selected.get(lead.key)
        if current is None or dedupe_quality(lead) > dedupe_quality(current):
            selected[lead.key] = lead
    return list(selected.values())


def dedupe_quality(lead: Lead) -> float:
    generic_penalty = -20 if lead.title in GENERIC_TITLES else 0
    detail_bonus = 35 if lead.is_project_url else -25
    text_bonus = min(len(lead.project_text) / 100, 35)
    return detail_bonus + generic_penalty + text_bonus + lead.match_score - lead.risk_score


def high_risk_reasons(lead: Lead) -> list[str]:
    combined = "\n".join(
        [
            lead.title,
            lead.category,
            lead.project_text,
            " ".join(lead.why_risky),
        ]
    )
    reasons: list[str] = []
    for pattern, reason in HIGH_RISK_PATTERNS:
        if pattern.search(combined):
            reasons.append(reason)
    return sorted(set(reasons))


def competition_penalty(lead: Lead) -> int:
    count = parse_count(f"{lead.proposals_count}\n{lead.project_text}")
    if count is None:
        return 0
    if count > 30:
        return 14
    if count > 20:
        return 10
    if count > 10:
        return 6
    if count > 5:
        return 3
    return 0


def budget_fit_bonus(lead: Lead) -> int:
    values = parse_money_values(lead.budget, lead.project_text)
    if not values:
        return 0
    visible_budget = max(values)
    if 3000 <= visible_budget <= 9000:
        return 12
    if 9000 < visible_budget <= 20000:
        return 7
    if visible_budget < 2500:
        return -12
    return 3


def clarity_bonus(lead: Lead) -> int:
    text = lead.project_text
    bonus = 0
    if len(text) >= 700:
        bonus += 10
    elif len(text) >= 250:
        bonus += 6
    elif len(text) < 120:
        bonus -= 10
    for pattern in CLARITY_PATTERNS:
        if pattern.search(text):
            bonus += 3
    if lead.title in GENERIC_TITLES:
        bonus -= 5
    return max(-15, min(bonus, 18))


def complexity(lead: Lead) -> str:
    text = f"{lead.title}\n{lead.project_text}".lower()
    complex_hits = [
        "crm",
        "1с",
        "bitrix",
        "битрикс",
        "postgres",
        "postgresql",
        "docker",
        "linux",
        "сервер",
        "парсер",
        "аналитика",
        "openai",
        "n8n",
        "синхронизац",
        "несколько систем",
    ]
    medium_hits = [
        "google",
        "таблиц",
        "api",
        "webhook",
        "яндекс директ",
        "интеграц",
    ]
    if any(item in text for item in complex_hits):
        return "complex"
    if has_bot_scope(text) or any(item in text for item in medium_hits):
        return "medium"
    return "simple"


def recommended_price(lead: Lead) -> int:
    level = complexity(lead)
    if level == "simple":
        base = 3500
    elif level == "medium":
        base = 6000
    else:
        base = 8500

    values = parse_money_values(lead.budget, lead.project_text)
    if values:
        visible_budget = max(values)
        if visible_budget < 2500:
            base = 2500
        elif visible_budget < base:
            base = max(2500, int(round(visible_budget / 500) * 500))

    return max(2500, min(base, 9000))


def recommended_deadline(lead: Lead) -> str:
    explicit_days = parse_deadline_days(f"{lead.deadline}\n{lead.project_text}")
    if explicit_days:
        safe_days = max(2, min(explicit_days, 7))
        return f"{safe_days} дн."
    level = complexity(lead)
    if level == "simple":
        return "2-3 дн."
    if level == "medium":
        return "3-5 дн."
    return "5-7 дн."


def execution_plan(lead: Lead) -> list[str]:
    text = f"{lead.title}\n{lead.project_text}".lower()
    if has_bot_scope(text):
        return [
            "зафиксировать сценарии бота, роли и поля заявки",
            "собрать рабочий aiogram-бот с командами, состояниями и проверкой входных данных",
            "добавить хранение в SQLite/PostgreSQL или выгрузку в Google Sheets, если это нужно",
            "передать README с запуском, настройкой токена и тестовым чек-листом",
        ]
    if "google" in text or "таблиц" in text or "яндекс директ" in text:
        return [
            "уточнить источники данных, доступные API и структуру итоговых вкладок",
            "сделать Python-интеграцию/API-выгрузку и запись в Google Sheets",
            "добавить пересчёт периода, форматирование колонок и контроль ошибок",
            "передать инструкцию по запуску и список ограничений по API/лимитам",
        ]
    if "парсер" in text or "парсинг" in text:
        return [
            "разобрать текущую логику парсера и место, где нужен реверс/доработка",
            "исправить основной сценарий на Python с логированием и понятной обработкой ошибок",
            "проверить на небольшом наборе тестовых данных без обхода защит и капчи",
            "передать код, README по запуску и список ограничений по источнику данных",
        ]
    if "linux" in text or "сервер" in text or "vps" in text or "claude code" in text:
        return [
            "уточнить ОС, текущие зависимости и целевой сценарий запуска Claude Code API",
            "настроить рабочее окружение, переменные и минимальную структуру проекта",
            "проверить запуск тестовой команды и базовую диагностику ошибок",
            "передать README с командами запуска, перезапуска и проверкой статуса",
        ]
    if "docker" in text:
        return [
            "разобрать текущий запуск и переменные окружения",
            "подготовить Dockerfile или docker-compose под повторяемый старт",
            "проверить запуск на тестовой команде",
            "передать короткую инструкцию по сборке, запуску и диагностике",
        ]
    if "crm" in text or "api" in text or "интеграц" in text:
        return [
            "описать схему обмена данными и обязательные поля",
            "собрать Python-интеграцию с API, обработкой ошибок и логированием",
            "проверить на тестовых данных без доступа к лишним аккаунтам",
            "передать инструкцию, конфиг-пример и границы поддержки",
        ]
    return [
        "уточнить входные данные и критерий готовности",
        "собрать небольшой Python-скрипт под первый рабочий сценарий",
        "проверить результат на тестовом примере",
        "передать код, инструкцию по запуску и понятные ограничения",
    ]


def client_questions(lead: Lead) -> list[str]:
    text = f"{lead.title}\n{lead.project_text}".lower()
    questions = [
        "Какие входные данные и пример результата можно использовать для проверки?",
        "Где должен запускаться результат: локально, на VPS или в уже существующем проекте?",
        "Какие критерии считать готовностью первого этапа?",
    ]
    if "google" in text or "таблиц" in text:
        questions[0] = "Есть ли пример Google-таблицы и список обязательных колонок/метрик?"
    if has_bot_scope(text):
        questions[0] = "Какие роли, команды и поля заявки должны быть в первом сценарии бота?"
    if "парсер" in text or "парсинг" in text:
        questions[0] = "Что именно сейчас не работает в парсере и есть ли пример входных/выходных данных?"
    if "linux" in text or "сервер" in text or "vps" in text:
        questions[0] = "Какая ОС на сервере и какой сценарий запуска должен работать в конце?"
    if "api" in text or "интеграц" in text or "яндекс директ" in text:
        questions[1] = "Доступен ли API/тестовый ключ или пока нужно подготовить код под ваши доступы?"
    return questions


def proposal_text(lead: Lead, price: int, deadline: str, plan: list[str], questions: list[str]) -> str:
    greeting = f"Здравствуйте, {lead.buyer_username}!" if lead.buyer_username else "Здравствуйте!"
    deadline_label = deadline.rstrip(".")
    body = [
        greeting,
        "",
        "Могу взять задачу как аккуратный первый этап: без лишних обещаний, с понятным результатом и инструкцией для проверки.",
        "",
        "План работы:",
        *(f"- {item};" for item in plan[:4]),
        "",
        f"Ориентир по цене: {price} ₽.",
        f"Ориентир по сроку: {deadline_label}.",
        "",
        "Перед стартом уточню 3 момента:",
        *(f"- {item}" for item in questions[:3]),
        "",
        "Если в задаче появятся спам, обход капчи/защит, чужие аккаунты или платёжные данные, такую часть не беру, но безопасный технический контур могу отделить.",
    ]
    text = "\n".join(body).strip()
    if len(text) <= 2000:
        return text
    return text[:1990].rstrip() + "\n..."


def verdict(final_score: int, risk_score: int, high_risk: bool) -> str:
    if high_risk or final_score < 20:
        return "SKIP"
    if final_score >= 45 and risk_score <= 30:
        return "SEND_AFTER_PHONE"
    return "REVIEW_MANUALLY"


def triage_lead(lead: Lead) -> TriagedLead:
    comp = competition_penalty(lead)
    budget_bonus = budget_fit_bonus(lead)
    clarity = clarity_bonus(lead)
    high_risk = high_risk_reasons(lead)
    price = recommended_price(lead)
    deadline = recommended_deadline(lead)
    lead.recommended_price = price
    lead.recommended_deadline = deadline
    lead.why_match = match_reasons(lead)
    final = int(lead.match_score - lead.risk_score - comp + budget_bonus + clarity)
    final = max(-100, min(final, 140))
    risk_blocked = bool(high_risk)
    plan = execution_plan(lead)
    questions = client_questions(lead)
    return TriagedLead(
        lead=lead,
        competition_penalty=comp,
        budget_fit_bonus=budget_bonus,
        clarity_bonus=clarity,
        final_score=final,
        high_risk=risk_blocked,
        high_risk_reasons=high_risk,
        verdict=verdict(final, lead.risk_score, risk_blocked),
        execution_plan=plan,
        questions=questions,
        proposal=proposal_text(lead, price, deadline, plan, questions),
    )


def write_card(item: TriagedLead) -> Path:
    lead = item.lead
    file_id = lead.project_id or re.sub(r"\W+", "-", lead.key, flags=re.I).strip("-")[:40]
    path = SHORTLIST_DIR / f"project_{file_id}.md"
    lines = [
        f"# {lead.title}",
        "",
        f"- title: {lead.title}",
        f"- url: {lead.url}",
        f"- buyer: {lead.buyer_username or 'not visible'}",
        f"- budget: {lead.budget or 'not visible'}",
        f"- deadline: {lead.deadline or lead.recommended_deadline}",
        f"- proposals_count: {lead.proposals_count or 'not visible'}",
        f"- match_score: {lead.match_score}",
        f"- risk_score: {lead.risk_score}",
        f"- final_score: {item.final_score}",
        f"- recommended_price: {lead.recommended_price} ₽",
        f"- recommended_deadline: {lead.recommended_deadline}",
        f"- verdict: {item.verdict}",
        "",
        "## Почему подходит",
        *(f"- {reason}" for reason in lead.why_match),
        "",
        "## Риски",
        *(f"- {reason}" for reason in (item.high_risk_reasons or lead.why_risky or ["no major risk keywords detected"])),
        "",
        "## Короткий план выполнения",
        *(f"- {step}" for step in item.execution_plan),
        "",
        "## Готовый отклик",
        "",
        item.proposal,
        "",
        "## 3 вопроса клиенту",
        *(f"- {question}" for question in item.questions[:3]),
        "",
        "## Safety",
        "- Offline triage only.",
        "- Nothing was sent to Kwork.",
        "- Phone/SMS/withdrawal/publish/send actions remain manual-only.",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def write_reports(items: list[TriagedLead], top5: list[TriagedLead], stats: TriageStats) -> None:
    ensure_dir(REPORTS)
    shortlist_lines = [
        "# Kwork Lead Shortlist",
        "",
        f"Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"project_root: `{REPO_ROOT}`",
        f"git_commit: `{stats.git_commit}`",
        "",
        "## Summary",
        f"- input_leads: `{stats.input_count}`",
        f"- deduplicated_projects: `{stats.deduplicated_count}`",
        f"- skipped_invalid_project_urls: `{stats.skipped_invalid_url}`",
        f"- removed_high_risk: `{stats.removed_high_risk}`",
        f"- shortlist_count: `{stats.shortlist_count}`",
        f"- top5_send_after_phone_count: `{stats.top5_count}`",
        "",
        "## Top Shortlist",
    ]
    for index, item in enumerate(items, start=1):
        lead = item.lead
        shortlist_lines.extend(
            [
                f"{index}. [{lead.title}]({lead.url})",
                f"   Score: `{item.final_score}` | match/risk: `{lead.match_score}/{lead.risk_score}` | price: `{lead.recommended_price} ₽` | deadline: `{lead.recommended_deadline}` | verdict: `{item.verdict}`",
                f"   Why: {', '.join(lead.why_match[:3])}",
                f"   Risks: {', '.join((item.high_risk_reasons or lead.why_risky)[:3])}",
            ]
        )
    shortlist_lines.extend(
        [
            "",
            "## Safety",
            "- Lead Triage is offline: it reads saved JSONL only and does not open Kwork.",
            "- Proposal drafts are local copy-paste helpers only.",
            "- Nothing was sent, no proposal/message buttons were clicked.",
            "- Phone/SMS/withdrawal/publish/moderation/final send actions remain manual-only.",
        ]
    )
    SHORTLIST_REPORT.write_text("\n".join(shortlist_lines).rstrip() + "\n", encoding="utf-8")

    top5_lines = [
        "# Top 5 Kwork Proposals",
        "",
        "Copy-paste only after phone verification is completed manually. Do not send before that.",
        "",
    ]
    for index, item in enumerate(top5, start=1):
        lead = item.lead
        top5_lines.extend(
            [
                f"## {index}. {lead.title}",
                "",
                f"- Проект: {lead.title}",
                f"- Ссылка: {lead.url}",
                f"- Цена: {lead.recommended_price} ₽",
                f"- Срок: {lead.recommended_deadline}",
                "",
                "```text",
                item.proposal,
                "```",
                "",
            ]
        )
    top5_lines.extend(
        [
            "## Safety",
            "- These are local drafts only.",
            "- They were not sent to Kwork.",
            "- `Предложить услугу`, `Отправить`, messages, phone/SMS, withdrawal and publish flows remain manual-only.",
        ]
    )
    TOP5_REPORT.write_text("\n".join(top5_lines).rstrip() + "\n", encoding="utf-8")


def write_outputs(items: list[TriagedLead], top5: list[TriagedLead], stats: TriageStats) -> None:
    ensure_dir(SHORTLIST_DIR)
    for old_file in SHORTLIST_DIR.glob("project_*.md"):
        old_file.unlink()
    for item in items:
        write_card(item)
    write_reports(items, top5, stats)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Kwork Lead Radar triage")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to data/leads/kwork_leads.jsonl")
    parser.add_argument("--top", type=int, default=10, help="Shortlist size")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    git_commit = validate_root()
    input_path = resolve_input(args.input)
    raw_leads = load_leads(input_path)
    deduped = deduplicate(raw_leads)
    triaged = [triage_lead(lead) for lead in deduped]

    invalid = [item for item in triaged if not item.lead.is_project_url]
    valid = [item for item in triaged if item.lead.is_project_url]
    high_risk = [item for item in valid if item.high_risk]
    safe = [item for item in valid if not item.high_risk]
    sorted_safe = sorted(safe, key=lambda item: (-item.final_score, item.lead.risk_score, item.lead.title))
    top_items = sorted_safe[: max(args.top, 0)]
    top5 = [item for item in top_items if item.verdict == "SEND_AFTER_PHONE"][:5]
    if len(top5) < 5:
        top5 = (top5 + [item for item in top_items if item not in top5])[:5]

    stats = TriageStats(
        input_count=len(raw_leads),
        deduplicated_count=len(deduped),
        skipped_invalid_url=len(invalid),
        removed_high_risk=len(high_risk),
        shortlist_count=len(top_items),
        top5_count=len(top5),
        git_commit=git_commit,
    )
    write_outputs(top_items, top5, stats)

    print(f"input_leads={stats.input_count}")
    print(f"deduplicated_projects={stats.deduplicated_count}")
    print(f"skipped_invalid_project_urls={stats.skipped_invalid_url}")
    print(f"removed_high_risk={stats.removed_high_risk}")
    print(f"shortlist_count={stats.shortlist_count}")
    print(f"top5_count={stats.top5_count}")
    print(f"shortlist_dir={SHORTLIST_DIR}")
    print(f"shortlist_report={SHORTLIST_REPORT}")
    print(f"top5_report={TOP5_REPORT}")
    for index, item in enumerate(top5, start=1):
        lead = item.lead
        print(f"top{index}={item.final_score} | {lead.recommended_price} ₽ | {lead.recommended_deadline} | {lead.title} | {lead.url}")


if __name__ == "__main__":
    main()
