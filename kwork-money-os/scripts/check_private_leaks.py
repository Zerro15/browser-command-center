#!/usr/bin/env python3
"""Fail if private Kwork Money OS runtime/generated files are tracked or staged."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ALLOWLIST = {
    "kwork-money-os/reports/account_audit.example.md",
    "kwork-money-os/reports/account_money_plan.example.md",
    "kwork-money-os/reports/reply_drafts.example.md",
    "kwork-money-os/data/profile/profile_optimized.example.json",
    "kwork-money-os/data/offers/optimized/example_offer.json",
    "kwork-money-os/templates/yandex_direct_sheets_exporter/.env.example",
}


@dataclass(frozen=True)
class Rule:
    label: str
    needle: str

    def matches(self, path: str) -> bool:
        return self.needle in path


FORBIDDEN_RULES = [
    Rule("ZerroOne browser profile", "kwork-money-os/.browser-profile-zerroone/"),
    Rule("wrong ZerroOne browser profile backup", "kwork-money-os/.browser-profile-zerroone-wrong-"),
    Rule("browser profile", "kwork-money-os/.browser-profile/"),
    Rule("virtualenv", "kwork-money-os/.venv/"),
    Rule("auth data", "kwork-money-os/.auth/"),
    Rule("cookie file", "cookies"),
    Rule("state file", "state"),
    Rule("env file", ".env"),
    Rule("screenshots", "kwork-money-os/reports/screenshots/"),
    Rule("account audit report", "kwork-money-os/reports/account_audit.md"),
    Rule("offers audit report", "kwork-money-os/reports/kwork_offers_audit.md"),
    Rule("account money plan", "kwork-money-os/reports/account_money_plan.md"),
    Rule("reply drafts", "kwork-money-os/reports/reply_drafts.md"),
    Rule("lead radar report", "kwork-money-os/reports/lead_radar_report.md"),
    Rule("lead shortlist report", "kwork-money-os/reports/lead_shortlist.md"),
    Rule("top proposals report", "kwork-money-os/reports/top_5_proposals.md"),
    Rule("daily lead pipeline report", "kwork-money-os/reports/daily_lead_pipeline_report.md"),
    Rule("best lead report", "kwork-money-os/reports/best_lead_of_day.md"),
    Rule("operator dashboard report", "kwork-money-os/reports/operator_dashboard.md"),
    Rule("operator dashboard html", "kwork-money-os/reports/operator_dashboard.html"),
    Rule("offer factory report", "kwork-money-os/reports/offer_factory_report.md"),
    Rule("order executor report", "kwork-money-os/reports/order_executor_report.md"),
    Rule("post phone readiness report", "kwork-money-os/reports/post_phone_readiness_report.md"),
    Rule("post phone readiness bridge report", "kwork-money-os/reports/post_phone_readiness_bridge_report.md"),
    Rule("Kwork login diagnostics report", "kwork-money-os/reports/kwork_login_diagnostics_report.md"),
    Rule("Kwork login diagnostics bridge report", "kwork-money-os/reports/kwork_login_diagnostics_bridge_report.md"),
    Rule("Playwright GUI diagnostics report", "kwork-money-os/reports/playwright_gui_diagnostics_report.md"),
    Rule("Windows visible browser CDP report", "kwork-money-os/reports/windows_visible_browser_cdp_report.md"),
    Rule("optimized profile fill report", "kwork-money-os/reports/profile_optimized_fill_report.md"),
    Rule("optimized profile fill plan", "kwork-money-os/reports/profile_optimized_fill_plan.md"),
    Rule("pre-phone setup report", "kwork-money-os/reports/pre_phone_setup_report.md"),
    Rule("autopilot report", "kwork-money-os/reports/autopilot_report.md"),
    Rule("browser fill report", "kwork-money-os/reports/browser_fill_report.md"),
    Rule("optimized profile", "kwork-money-os/data/profile/profile_optimized.json"),
    Rule("optimized offers", "kwork-money-os/data/offers/optimized/"),
    Rule("best lead proposal", "kwork-money-os/data/leads/best_lead_of_day_proposal.md"),
    Rule("lead radar data", "kwork-money-os/data/leads/"),
    Rule("kwork studio runtime data", "kwork-money-os/data/kwork_studio/"),
    Rule("best lead delivery kit", "kwork-money-os/data/delivery/best_lead_yandex_direct_sheets/"),
    Rule("prepared order workspaces", "kwork-money-os/data/orders/prepared/"),
    Rule("reply data", "kwork-money-os/data/replies/"),
    Rule("private data", "kwork-money-os/data/private/"),
]


def run_git(args: list[str], repo_root: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.decode("utf-8", errors="replace")


def repo_root() -> Path:
    here = Path(__file__).resolve()
    try:
        output = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=here.parents[2],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        return Path(output)
    except Exception as error:
        raise SystemExit(f"Unable to locate git repository root: {error}") from error


def split_z(output: bytes) -> list[str]:
    return [item.decode("utf-8", errors="replace") for item in output.split(b"\0") if item]


def git_paths(args: list[str], repo_root_path: Path) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root_path,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return split_z(result.stdout)


def staged_paths(repo_root_path: Path) -> list[str]:
    # Deletions are safe here: they remove private files from the repository.
    return git_paths(
        ["diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRT"],
        repo_root_path,
    )


def tracked_paths(repo_root_path: Path) -> list[str]:
    return git_paths(["ls-files", "-z"], repo_root_path)


def is_forbidden(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if normalized in ALLOWLIST:
        return None
    for rule in FORBIDDEN_RULES:
        if rule.matches(normalized):
            return rule.label
    return None


def collect_violations(paths: list[str], source: str) -> list[tuple[str, str, str]]:
    violations = []
    for path in sorted(set(paths)):
        reason = is_forbidden(path)
        if reason:
            violations.append((source, reason, path))
    return violations


def main() -> None:
    root = repo_root()
    violations = []
    violations.extend(collect_violations(tracked_paths(root), "tracked",))
    violations.extend(collect_violations(staged_paths(root), "staged",))

    if not violations:
        print("No private Kwork Money OS files are tracked or staged.")
        return

    print("Private Kwork Money OS files detected in git index:")
    for source, reason, path in violations:
        print(f"- [{source}] {path} ({reason})")
    print("")
    print("Fix: keep the file on disk but remove it from git with:")
    print("  git rm --cached -- <path>")
    sys.exit(1)


if __name__ == "__main__":
    main()
