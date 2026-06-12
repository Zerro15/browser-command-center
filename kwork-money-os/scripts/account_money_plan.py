#!/usr/bin/env python3
"""Build a practical Kwork account money plan from audits and services."""

from __future__ import annotations

import argparse
from pathlib import Path

from account_optimizer_common import add_mode_args, build_plan_report, load_services, parse_mode, read_text, require_run_approval, write_markdown
from _common import REPORTS


ACCOUNT_AUDIT_PATH = REPORTS / "account_audit.md"
OFFERS_AUDIT_PATH = REPORTS / "kwork_offers_audit.md"
OPPORTUNITIES_PATH = REPORTS / "opportunities.md"
PLAN_OUTPUT_PATH = REPORTS / "account_money_plan.md"
PLAN_DRY_RUN_PATH = REPORTS / "account_money_plan_dry_run.md"


def service_price(service: dict, package_name: str, fallback: int) -> int:
    return int(((service.get("packages") or {}).get(package_name) or {}).get("price_from", fallback))


def top_services(services: list[dict]) -> list[dict]:
    def score(service: dict) -> tuple[int, int]:
        risk = str(service.get("risk_level", "medium")).lower()
        risk_score = 3 if risk == "low" else 2 if risk == "medium" else 1
        economy = service_price(service, "economy", 2500)
        beginner_score = 3 if economy <= 4000 else 2 if economy <= 6000 else 1
        return (risk_score + beginner_score, -economy)

    return sorted(services, key=score, reverse=True)[:5]


def build_plan(args: argparse.Namespace, services: list[dict]) -> list[str]:
    top = top_services(services)
    account_audit = read_text(Path(args.account_audit), "account audit missing")
    offers_audit = read_text(Path(args.offers_audit), "offers audit missing")
    opportunities = read_text(Path(args.opportunities), "opportunities report missing")
    return [
        "# Kwork Account Money Plan",
        "",
        f"Current level: `{args.current_level}`",
        "",
        "## Топ-5 услуг, которые стоит продавать",
        *(
            f"- {item.get('name', item.get('id'))}: старт {service_price(item, 'economy', 2500)} руб., "
            f"стандарт {service_price(item, 'standard', 5000)} руб.; {item.get('positioning', '')}"
            for item in top
        ),
        "",
        "## Какие кворки создать первыми",
        "- Исправлю одну ошибку в Python, JS, боте или парсере: низкий риск, быстрый результат.",
        "- Сделаю простого Telegram-бота для заявок: понятный бизнес-результат.",
        "- Обработаю один Excel/CSV файл или таблицу: хорошо для маленьких заказов.",
        "- Сделаю мини-парсер одной страницы на Python: только публичные данные и один источник.",
        "- Запущу проект через Docker с инструкцией: полезно для владельцев кода и MVP.",
        "",
        "## Какие кворки улучшить",
        "- Все кворки, где заголовок обещает широкий результат, сузить до одного конкретного итога.",
        "- В первом пакете оставить маленький объём: 1 бот, 1 файл, 1 страница, 1 интеграция.",
        "- Добавить вопросы покупателю, чтобы не принимать мутную задачу вслепую.",
        "",
        "## Стартовые цены",
        "- Recovery-кворки: 1500-2500 руб. за маленький результат.",
        "- Telegram/Sheets/API простые задачи: 2500-5000 руб.",
        "- Docker/AI/API средние задачи: 4000-10000 руб. только после уточнения.",
        "- Всё сложное: сначала платный маленький диагностический этап.",
        "",
        "## Что написать в профиле",
        "- `Сделаю простую рабочую автоматизацию для бизнеса без лишней воды`.",
        "- Указать стек: Python, Telegram Bot API, Google Sheets, Docker, OpenAI API, парсеры.",
        "- Добавить честные ограничения: не делаю спам, взлом, обход капчи и сбор приватных данных.",
        "",
        "## Как отвечать клиентам",
        "- Коротко подтвердить, что задача похожа на понятный сценарий.",
        "- Задать 2-3 вопроса: результат, входные данные, пример, доступы.",
        "- Предложить маленький первый этап вместо большого обещания.",
        "- Не уводить клиента с Kwork и не просить токены до понятного этапа.",
        "",
        "## Что делать каждый день",
        "- Проверять сообщения и заявки 2-3 раза в день.",
        "- Отвечать только на подходящие маленькие задачи.",
        "- Отказываться от серых, мутных и слишком больших задач.",
        "- Обновлять один кворк или один шаблон ответа по результатам дня.",
        "",
        "## Что делать первую неделю",
        "- День 1: обновить профиль, проверить все recovery-кворки.",
        "- День 2: подготовить 5 коротких шаблонов ответов.",
        "- День 3: улучшить обложки и первые 2 строки описаний.",
        "- День 4: проверить цены и убрать широкие обещания.",
        "- День 5-7: быстро отвечать, брать только маленькие заказы, собирать отзывы.",
        "",
        "## Риски",
        "- Блокировка: не спамить, не делать массовые отклики, не обходить правила Kwork.",
        "- Плохой отзыв: не принимать заказ без ясного результата и входных данных.",
        "- Слабые обещания: не писать `любой бот`, `любая интеграция`, `быстро всё сделаю`.",
        "- Приватные данные: не хранить токены, cookies, пароли и личные сообщения в отчётах.",
        "",
        "## Как не слить аккаунт",
        "- Финальные действия делать руками после проверки текста и страницы.",
        "- Держать первые заказы маленькими и проверяемыми.",
        "- Не спорить с клиентом: если задача мутная, задавать вопросы или отказываться.",
        "- Не продавать то, что требует обхода защит, серого парсинга или массовой рассылки.",
        "",
        "## Source Notes",
        f"- account_audit.md loaded: `{bool(account_audit.strip())}`",
        f"- kwork_offers_audit.md loaded: `{bool(offers_audit.strip())}`",
        f"- opportunities.md loaded: `{bool(opportunities.strip())}`",
        "- This plan is local-only and does not change Kwork.",
    ]


def run_plan(args: argparse.Namespace) -> None:
    mode = parse_mode(args)
    if mode in {"dry-run", "preview"}:
        build_plan_report(
            PLAN_DRY_RUN_PATH,
            "Kwork Account Money Plan Dry Run",
            mode,
            [
                f"Read {args.account_audit}.",
                f"Read {args.offers_audit}.",
                f"Read {args.opportunities}.",
                "Read services/*.yaml.",
                f"Write {args.output} only in --run --approve.",
            ],
        )
        print(PLAN_DRY_RUN_PATH)
        return
    require_run_approval(mode, args.approve, "Account money plan generation")
    write_markdown(Path(args.output), build_plan(args, load_services()))
    print(args.output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-audit", default=str(ACCOUNT_AUDIT_PATH))
    parser.add_argument("--offers-audit", default=str(OFFERS_AUDIT_PATH))
    parser.add_argument("--opportunities", default=str(OPPORTUNITIES_PATH))
    parser.add_argument("--output", default=str(PLAN_OUTPUT_PATH))
    parser.add_argument("--current-level", default="low-reputation recovery mode")
    add_mode_args(parser)
    run_plan(parser.parse_args())


if __name__ == "__main__":
    main()
