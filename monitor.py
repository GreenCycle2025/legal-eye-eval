#!/usr/bin/env python3
"""Is the public API answering, and from which upstream?

Checks https://legal-eye-api.1bigfam.com the way a visitor reaches it:

- ``GET /readyz`` must answer 200 with ``"ok": true`` (service up, corpus
  index open);
- ``GET /v1/corpus/selftest`` must answer 200 (a fixed search still returns
  rulings);
- the Hugging Face Space's responses carry ``x-proxied-replica``; the standby
  container's do not, so a response without it means the standby is serving.

A check that fails is repeated (``--attempts``, ``--interval``) before it
counts, so one slow request is not an outage. The result is one of ``ok``,
``standby`` (up, but the Space is not answering) and ``down``.

    python3 monitor.py                    # print the result as JSON
    python3 monitor.py --github-issues    # and open or close the alert issues

With ``--github-issues`` (in GitHub Actions: GITHUB_TOKEN, GITHUB_REPOSITORY)
the state lives in two issues of this repository, one per problem: an issue
is opened when its problem starts, assigned to MONITOR_ASSIGNEE when set (so
GitHub notifies that person), and commented on and closed when it ends.
Standard library only, like the rest of the harness.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

DEFAULT_BASE = "https://legal-eye-api.1bigfam.com"
TITLES = {
    "down": "[monitor] the legal-eye API is not answering",
    "standby": "[monitor] the standby is answering instead of the Space",
}
USER_AGENT = "legal-eye-eval-monitor"


def _get(url: str, timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536).decode("utf-8", "replace")
            return {"status": resp.status, "body": body,
                    "replica": resp.headers.get("x-proxied-replica") is not None,
                    "ms": int((time.monotonic() - started) * 1000)}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": "", "replica": e.headers.get("x-proxied-replica") is not None,
                "ms": int((time.monotonic() - started) * 1000)}
    except Exception as e:
        return {"status": None, "error": type(e).__name__, "body": "", "replica": False,
                "ms": int((time.monotonic() - started) * 1000)}


def probe(base_url: str, get: Callable[[str, float], Dict[str, Any]] = _get) -> Dict[str, Any]:
    """One look at the service: readyz, selftest, and which upstream answered."""
    ready = get(f"{base_url}/readyz", 20)
    try:
        ready_ok = ready["status"] == 200 and bool(json.loads(ready["body"] or "{}").get("ok"))
    except ValueError:
        ready_ok = False
    selftest = get(f"{base_url}/v1/corpus/selftest", 30)
    up = ready_ok and selftest["status"] == 200
    return {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "readyz": ready["status"] if ready["status"] is not None else ready.get("error"),
        "readyz_ms": ready["ms"],
        "selftest": selftest["status"] if selftest["status"] is not None else selftest.get("error"),
        "selftest_ms": selftest["ms"],
        "space": bool(ready["replica"] or selftest["replica"]),
        "up": up,
    }


def assess(probes: List[Dict[str, Any]]) -> str:
    """The state the last probe shows; earlier probes are the failed ones repeated."""
    last = probes[-1]
    if not last["up"]:
        return "down"
    return "ok" if last["space"] else "standby"


def run_checks(base_url: str, attempts: int, interval: float,
               get: Callable[[str, float], Dict[str, Any]] = _get,
               sleep: Callable[[float], None] = time.sleep) -> List[Dict[str, Any]]:
    """Probe until one is fully fine (up, from the Space), at most `attempts` times."""
    probes: List[Dict[str, Any]] = []
    for i in range(max(1, attempts)):
        if i:
            sleep(interval)
        p = probe(base_url, get)
        probes.append(p)
        if p["up"] and p["space"]:
            break
    return probes


# ──────────────────────────────────────────────────────────────────────
# Alert issues
# ──────────────────────────────────────────────────────────────────────

class GitHub:
    """The few REST calls the alert issues need."""

    def __init__(self, repo: str, token: str, api: str = "https://api.github.com"):
        self.repo, self.token, self.api = repo, token, api.rstrip("/")

    def call(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        req = urllib.request.Request(
            f"{self.api}/repos/{self.repo}{path}", method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"Authorization": f"Bearer {self.token}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": USER_AGENT,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None

    def open_issues(self) -> List[dict]:
        return [i for i in self.call("GET", "/issues?state=open&per_page=100") or []
                if "pull_request" not in i]

    def create(self, title: str, body: str, assignee: str) -> None:
        payload = {"title": title, "body": body}
        if assignee:
            try:
                self.call("POST", "/issues", dict(payload, assignees=[assignee]))
                return
            except urllib.error.HTTPError as e:
                if e.code != 422:          # someone who cannot be assigned
                    raise
        self.call("POST", "/issues", payload)

    def comment(self, number: int, body: str) -> None:
        self.call("POST", f"/issues/{number}/comments", {"body": body})

    def close(self, number: int) -> None:
        self.call("PATCH", f"/issues/{number}", {"state": "closed", "state_reason": "completed"})


def _table(probes: List[Dict[str, Any]]) -> str:
    lines = ["| at (UTC) | /readyz | ms | /v1/corpus/selftest | ms | Space answered |",
             "|---|---|---|---|---|---|"]
    for p in probes:
        lines.append(f"| {p['at']} | {p['readyz']} | {p['readyz_ms']} | {p['selftest']} "
                     f"| {p['selftest_ms']} | {'yes' if p['space'] else 'no'} |")
    return "\n".join(lines)


def reconcile(state: str, probes: List[Dict[str, Any]], gh: GitHub, base_url: str,
              assignee: str = "", run_url: str = "") -> List[str]:
    """Open the issue of the current problem, close the issues of problems that ended."""
    actions: List[str] = []
    open_by_title = {i["title"]: i for i in gh.open_issues() if i["title"] in TITLES.values()}
    for problem, title in TITLES.items():
        issue = open_by_title.get(title)
        if problem == state and issue is None:
            what = ("`/readyz` or `/v1/corpus/selftest` failed on every attempt."
                    if problem == "down" else
                    "Requests are answered without `x-proxied-replica`: the Hugging Face "
                    "Space is failing `/readyz` and Caddy sends traffic to the standby "
                    "container (legal-eye `docs/SELF_HOSTING.md`).")
            gh.create(title, f"{base_url}\n\n{what}\n\n{_table(probes)}\n\n{run_url}".rstrip(),
                      assignee)
            actions.append(f"opened: {title}")
        elif problem != state and issue is not None:
            gh.comment(issue["number"], f"Ended: the check at {probes[-1]['at']} found `{state}`."
                                        f"\n\n{_table(probes[-1:])}\n\n{run_url}".rstrip())
            gh.close(issue["number"])
            actions.append(f"closed: {title}")
    return actions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--interval", type=float, default=60.0,
                    help="seconds between attempts when a check fails")
    ap.add_argument("--github-issues", action="store_true",
                    help="open or close the alert issues (GITHUB_TOKEN, GITHUB_REPOSITORY)")
    args = ap.parse_args()

    probes = run_checks(args.base_url, args.attempts, args.interval)
    state = assess(probes)
    result = {"state": state, "probes": probes}
    if args.github_issues:
        repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
        if not repo or not token:
            print("--github-issues needs GITHUB_REPOSITORY and GITHUB_TOKEN", file=sys.stderr)
            return 2
        run_url = ""
        if os.environ.get("GITHUB_RUN_ID"):
            run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}"
                       f"/actions/runs/{os.environ['GITHUB_RUN_ID']}")
        result["issues"] = reconcile(state, probes, GitHub(repo, token), args.base_url,
                                     os.environ.get("MONITOR_ASSIGNEE", ""), run_url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
