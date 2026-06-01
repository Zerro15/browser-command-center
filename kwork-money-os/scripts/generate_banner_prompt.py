#!/usr/bin/env python3
"""Generate 660x440 Kwork banner prompts from an offer or service."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import DATA, SERVICES, ensure_dir, load_json, load_yaml, slugify, write_json


STYLES = {
    "dark tech": "dark technical interface, crisp contrast, subtle code panels, professional SaaS feeling",
    "clean business": "clean white business layout, structured blocks, calm accent colors, high readability",
    "bright marketplace": "bright marketplace cover, energetic but clean, clear service value, modern UI shapes",
}


def load_source(value: str) -> dict:
    path = Path(value)
    if not path.exists():
        offer_path = DATA / "offers" / f"{value}.json"
        service_path = SERVICES / f"{value}.yaml"
        path = offer_path if offer_path.exists() else service_path
    if path.suffix == ".json":
        return load_json(path)
    return load_yaml(path)


def build_prompts(source: dict) -> dict:
    title = source.get("title") or source.get("name")
    result = source.get("short_description") or source.get("client_result") or source.get("positioning", "")
    banner_text = title.replace("Сделаю ", "").replace(" с понятным результатом", "")[:42]
    variants = []
    for style, description in STYLES.items():
        variants.append(
            {
                "style": style,
                "size": "660x440",
                "banner_text": banner_text,
                "prompt": (
                    f"Create a Kwork service banner, 660x440 px, {description}. "
                    f"Main readable Russian text: \"{banner_text}\". "
                    f"Secondary idea: {result}. "
                    "Composition: large readable headline, one focused central visual metaphor, "
                    "small checklist or UI card shapes, plenty of spacing, no clutter. "
                    "Use original abstract UI, no real brand logos."
                ),
                "negative_prompt": "no watermark, no tiny text, no broken UI, no fake logos, no unreadable letters, no distorted hands, no misleading badges",
            }
        )
    return {"source_title": title, "variants": variants}


def render_markdown(result: dict) -> str:
    lines = [f"# Banner prompts: {result['source_title']}", ""]
    for item in result["variants"]:
        lines.extend(
            [
                f"## {item['style']}",
                "",
                f"Size: `{item['size']}`",
                "",
                f"Text: `{item['banner_text']}`",
                "",
                item["prompt"],
                "",
                f"Negative: {item['negative_prompt']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Offer JSON, service YAML, or id")
    args = parser.parse_args()

    source = load_source(args.source)
    result = build_prompts(source)
    slug = slugify(source.get("service_id") or source.get("id") or result["source_title"])
    output_dir = ensure_dir(DATA / "banners")
    md_path = output_dir / f"{slug}.md"
    json_path = output_dir / f"{slug}.json"
    md_path.write_text(render_markdown(result), encoding="utf-8")
    write_json(json_path, result)
    print(md_path)
    print(json_path)


if __name__ == "__main__":
    main()
