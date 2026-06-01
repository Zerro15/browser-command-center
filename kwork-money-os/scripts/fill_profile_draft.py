#!/usr/bin/env python3
"""CLI wrapper for safe Kwork profile draft filling."""

from __future__ import annotations

import argparse
from argparse import Namespace

from browser_rpa_bridge import run_profile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="Profile JSON or Markdown from data/profile")
    parser.add_argument("--profile-url", default=None, help="Kwork profile/settings edit URL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--fill-profile", action="store_true")
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()

    modes = [args.dry_run, args.preview, args.fill_profile]
    if sum(bool(item) for item in modes) != 1:
        raise SystemExit("Choose exactly one mode: --dry-run, --preview, or --fill-profile")

    mode = "dry-run" if args.dry_run else "preview" if args.preview else "fill-profile"
    run_profile(
        Namespace(
            mode=mode,
            profile=args.profile,
            profile_url=args.profile_url,
            approve=args.approve,
        )
    )


if __name__ == "__main__":
    main()
