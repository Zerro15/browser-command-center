#!/usr/bin/env python3
"""CLI wrapper for safe Kwork draft filling."""

from __future__ import annotations

import argparse
from argparse import Namespace

from browser_rpa_bridge import run_draft


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offer", required=True, help="Offer JSON or Markdown from data/offers")
    parser.add_argument("--banner", default=None, help="Optional ready banner image")
    parser.add_argument("--draft-url", default=None, help="Existing Kwork draft/edit URL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--fill-draft", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--hold", action="store_true")
    args = parser.parse_args()

    modes = [args.dry_run, args.preview, args.fill_draft]
    if sum(bool(item) for item in modes) != 1:
        raise SystemExit("Choose exactly one mode: --dry-run, --preview, or --fill-draft")

    mode = "dry-run" if args.dry_run else "preview" if args.preview else "fill-draft"
    run_draft(
        Namespace(
            mode=mode,
            offer=args.offer,
            banner=args.banner,
            draft_url=args.draft_url,
            approve=args.approve,
            hold=args.hold,
        )
    )


if __name__ == "__main__":
    main()
