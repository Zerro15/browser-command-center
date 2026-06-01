#!/usr/bin/env python3
"""Create local Kwork profile draft files without editing the live profile."""

from __future__ import annotations

import argparse

from _common import DATA, SERVICES, ensure_dir, load_yaml, write_json


def build_profile(service_ids: list[str]) -> dict:
    services = [load_yaml(SERVICES / f"{service_id}.yaml") for service_id in service_ids]
    service_names = [service["name"] for service in services]
    skills = []
    for service in services:
        skills.extend(service.get("skills") or [])
    skills = list(dict.fromkeys(skills))

    return {
        "positioning": "Разрабатываю небольшие рабочие автоматизации, ботов и интеграции без лишних обещаний.",
        "about": (
            "Помогаю быстро собрать понятный технический результат: Telegram-бота, интеграцию с таблицами, "
            "AI-сценарий, Docker-запуск или небольшой внутренний инструмент. Сначала уточняю задачу и ограничения, "
            "потом фиксирую объем и сдаю результат с короткой инструкцией."
        ),
        "services": service_names,
        "trust": [
            "показываю результат на тестовом сценарии",
            "не прошу пароли в открытом виде",
            "честно отделяю базовый объем от доработок",
            "оставляю инструкцию запуска или использования",
        ],
        "tech_stack": skills,
        "style_notes": "Спокойный деловой тон, без понтов, гарантий продаж и вводящих в заблуждение обещаний.",
    }


def render_markdown(profile: dict) -> str:
    return f"""# Kwork Profile Draft

## Positioning
{profile['positioning']}

## About
{profile['about']}

## Services
{chr(10).join(f"- {item}" for item in profile['services'])}

## Why Trust
{chr(10).join(f"- {item}" for item in profile['trust'])}

## Tech Stack
{", ".join(profile['tech_stack'])}

## Style Notes
{profile['style_notes']}

## Safety
Этот файл только черновик. Скрипт не меняет профиль Kwork сам.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--services", nargs="*", default=["telegram_bot_leads", "ai_business_bot", "docker_project_launch", "n8n_automation"])
    args = parser.parse_args()
    profile = build_profile(args.services)
    output_dir = ensure_dir(DATA / "profile")
    md_path = output_dir / "profile_draft.md"
    json_path = output_dir / "profile_draft.json"
    md_path.write_text(render_markdown(profile), encoding="utf-8")
    write_json(json_path, profile)
    print(md_path)
    print(json_path)


if __name__ == "__main__":
    main()
