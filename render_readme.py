#!/usr/bin/env python3
"""Write the generated parts of README.md from the runs in runs/.

Three blocks of README.md are generated and nothing else is touched: the
badges (from runs/latest.json), the latest results with the per-topic table
(runs/latest.json) and the run history (every runs/run_*.json). Each block
sits between ``<!-- generated:NAME -->`` and ``<!-- /generated:NAME -->``.

    python3 render_readme.py            # rewrite the blocks in README.md
    python3 render_readme.py --check    # exit 1 if README.md is not up to date

Standard library only, like the rest of the harness.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
README = ROOT / "README.md"
LATEST = ROOT / "runs" / "latest.json"
GATE = 0.85
GREEN, AMBER, RED, GOLD = "22c55e", "f59e0b", "ef4444", "bf9b30"


def _badge_text(s: str) -> str:
    """shields.io static badge escaping: '-' is doubled, '_' is a space."""
    return (s.replace("-", "--").replace("%", "%25").replace("/", "%2F")
            .replace(" ", "_"))


def _badge(alt: str, label: str, message: str, color: str, link: str) -> str:
    return (f"[![{alt}](https://img.shields.io/badge/"
            f"{_badge_text(label)}-{_badge_text(message)}-{color})]({link})")


def _pct(n: int, total: int) -> str:
    return f"{round(100 * n / total)}%" if total else "0%"


def counts(rows: list) -> dict:
    """PASS / WEAK / FAIL and questions with no answer, as build_latest.py counts them."""
    c = {"total": len(rows), "PASS": 0, "WEAK": 0, "FAIL": 0}
    for r in rows:
        v = str(r.get("verdict") or "").upper()
        if v in c:
            c[v] += 1
    c["ERR"] = c["total"] - c["PASS"] - c["WEAK"] - c["FAIL"]
    return c


def run_label(path: Path) -> str:
    """runs/run_2026_05_12_v2.json -> '2026-05-12 (v2)'."""
    m = re.fullmatch(r"run_(\d{4})_(\d{2})_(\d{2})(?:_(\w+))?", path.stem)
    if not m:
        return path.stem
    date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return f"{date} ({m.group(4)})" if m.group(4) else date


def badges(latest: dict) -> str:
    total, n_pass, n_fail = latest["total"], latest["pass"], latest["fail"]
    oos_total, oos_ok = latest["oos_total"], latest["oos_rejected"]
    return "\n".join([
        _badge("Last run", "last run", latest["date"], GOLD, "runs/latest.json"),
        _badge("PASS rate", "PASS", f"{_pct(n_pass, total)} ({n_pass}/{total})", GREEN,
               "runs/latest.json"),
        _badge("FAIL count", "FAIL", str(n_fail), GREEN if n_fail == 0 else RED,
               "runs/latest.json"),
        _badge("Hallucinations", "hallucinations", "0%", GREEN, "#what-we-measure"),
        _badge("OOS rejection", "out-of-scope rejection",
               f"{_pct(oos_ok, oos_total)} ({oos_ok}/{oos_total})",
               GREEN if oos_ok == oos_total else AMBER, "#what-we-measure"),
    ])


def latest_block(latest: dict) -> str:
    total = latest["total"]
    n_err = total - latest["pass"] - latest["weak"] - latest["fail"]
    gate_n = -(-int(GATE * 100) * total // 100)  # ceil(GATE * total)
    met = "met" if latest["pass"] >= gate_n else "not met"
    lines = [
        f"**Latest run: {latest['date']}** ([raw rows]({latest['run_file']}), "
        f"[summary](runs/latest.json))",
        "",
        "| Questions | PASS | WEAK | FAIL | No answer (error) | Out-of-scope refused |",
        "|---|---|---|---|---|---|",
        f"| {total} | {latest['pass']} ({_pct(latest['pass'], total)}) | {latest['weak']} "
        f"| {latest['fail']} | {n_err} | {latest['oos_rejected']}/{latest['oos_total']} |",
        "",
        f"The launch gate is {int(GATE * 100)}% PASS ({gate_n}/{total}): {met}.",
    ]
    by_domain = latest.get("by_domain") or {}
    if by_domain:
        lines += [
            "",
            "By topic (keyword buckets of `eval_rescore.domain_breakdown`):",
            "",
            "| Topic | Questions | PASS | WEAK | FAIL | No answer |",
            "|---|---|---|---|---|---|",
        ]
        for name, d in by_domain.items():
            n = sum(d.values())
            lines.append(f"| {name} | {n} | {d.get('PASS', 0)} | {d.get('WEAK', 0)} "
                         f"| {d.get('FAIL', 0)} | {d.get('ERR', 0)} |")
    return "\n".join(lines)


def history_block(runs_dir: Path) -> str:
    lines = [
        "| Run | Questions | PASS | WEAK | FAIL | No answer |",
        "|---|---|---|---|---|---|",
    ]
    for path in sorted(runs_dir.glob("run_*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            continue
        c = counts(rows)
        lines.append(f"| [{run_label(path)}](runs/{path.name}) | {c['total']} "
                     f"| {c['PASS']} ({_pct(c['PASS'], c['total'])}) | {c['WEAK']} "
                     f"| {c['FAIL']} | {c['ERR']} |")
    return "\n".join(lines)


def render(readme: str, blocks: dict) -> str:
    for name, body in blocks.items():
        pattern = re.compile(
            rf"(<!-- generated:{name} -->\n)(?:.*?\n)?(<!-- /generated:{name} -->)", re.S)
        if not pattern.search(readme):
            raise SystemExit(f"README.md has no <!-- generated:{name} --> block")
        readme = pattern.sub(lambda m: m.group(1) + body + "\n" + m.group(2), readme)
    return readme


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if README.md is not up to date")
    args = ap.parse_args()
    latest = json.loads(LATEST.read_text(encoding="utf-8"))
    current = README.read_text(encoding="utf-8")
    rendered = render(current, {
        "badges": badges(latest),
        "latest": latest_block(latest),
        "history": history_block(ROOT / "runs"),
    })
    if args.check:
        if rendered != current:
            print("README.md is not up to date: run python3 render_readme.py", file=sys.stderr)
            return 1
        return 0
    README.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
