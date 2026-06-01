#!/usr/bin/env python3
"""Generate a local Kwork offer draft from a service YAML file."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import DATA, SERVICES, ensure_dir, listify, load_yaml, markdown_list, slugify, write_json


def load_service(value: str) -> tuple[Path, dict]:
    path = Path(value)
    if not path.exists():
        path = SERVICES / f"{value}.yaml"
    return path, load_yaml(path)


def build_offer(service: dict) -> dict:
    name = service["name"]
    result = service.get("client_result", "")
    base = listify(service.get("base_scope"))
    not_included = listify(service.get("not_included"))
    extras = listify(service.get("extras"))
    packages = service.get("packages") or {}
    tags = list(dict.fromkeys([*listify(service.get("skills")), *listify(service.get("target_clients"))]))[:10]

    return {
        "service_id": service.get("id", slugify(name)),
        "title": f"Сделаю {name.lower()} с понятным результатом",
        "short_description": result or service.get("positioning", ""),
        "full_description": (
            f"{service.get('positioning', name)}\n\n"
            f"Результат: {result}\n\n"
            "Перед стартом уточняю задачу, фиксирую базовый объем и показываю, что именно будет готово. "
            "Если задача выходит за рамки базового кворка, заранее предложу отдельный этап."
        ),
        "what_included": base,
        "what_not_included": not_included,
        "packages": packages,
        "extras": extras,
        "FAQ": [
            {"q": "Что нужно от меня для старта?", "a": "Описание задачи, доступы без паролей в переписке, примеры и желаемый результат."},
            {"q": "Можно ли расширить задачу?", "a": "Да, после оценки объема предложу отдельный этап или доп."},
            {"q": "Что я получу в конце?", "a": service.get("proof", "Рабочий результат, короткое объяснение и инструкцию.")},
        ],
        "buyer_questions": [
            "Какой конкретный результат нужен?",
            "Какие сервисы или API нужно подключить?",
            "Где сейчас лежит код/материалы?",
            "Есть ли пример похожего решения?",
            "Какие ограничения по сроку и доступам?",
        ],
        "tags": tags,
        "delivery_requirements": [
            "Не присылайте пароли в открытом виде.",
            "Доступы лучше выдавать временно или через роли.",
            "Для API нужны тестовые ключи или инструкция получения.",
        ],
        "upsell_strategy": [
            "деплой и автозапуск",
            "интеграция с таблицами/API",
            "дополнительные сценарии",
            "документация и обучение",
        ],
        "risk_level": service.get("risk_level", "medium"),
        "proof": service.get("proof", ""),
    }


def render_markdown(offer: dict) -> str:
    package_lines = []
    for name, package in (offer.get("packages") or {}).items():
        package_lines.append(f"### {name}")
        package_lines.append(f"Цена от: {package.get('price_from', 'n/a')} руб.")
        package_lines.append(f"Срок: {package.get('days', 'n/a')} дн.")
        package_lines.append(markdown_list(listify(package.get("includes"))))
        package_lines.append("")

    faq_lines = []
    for item in offer.get("FAQ", []):
        faq_lines.append(f"**{item['q']}**\n\n{item['a']}\n")

    return f"""# {offer['title']}

## Short Description
{offer['short_description']}

## Full Description
{offer['full_description']}

## What Included
{markdown_list(offer['what_included'])}

## What Not Included
{markdown_list(offer['what_not_included'])}

## Packages
{chr(10).join(package_lines).rstrip()}

## Extras
{markdown_list(offer['extras'])}

## FAQ
{chr(10).join(faq_lines).rstrip()}

## Buyer Questions
{markdown_list(offer['buyer_questions'])}

## Tags
{", ".join(offer['tags'])}

## Delivery Requirements
{markdown_list(offer['delivery_requirements'])}

## Upsell Strategy
{markdown_list(offer['upsell_strategy'])}

## Proof
{offer['proof']}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("service", help="Service id or YAML path")
    args = parser.parse_args()

    _, service = load_service(args.service)
    offer = build_offer(service)
    slug = slugify(offer["service_id"])
    output_dir = ensure_dir(DATA / "offers")
    md_path = output_dir / f"{slug}.md"
    json_path = output_dir / f"{slug}.json"
    md_path.write_text(render_markdown(offer), encoding="utf-8")
    write_json(json_path, offer)
    print(md_path)
    print(json_path)


if __name__ == "__main__":
    main()
