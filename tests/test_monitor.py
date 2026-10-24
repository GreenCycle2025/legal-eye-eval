"""Offline checks of monitor.py (no network, standard library only)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import monitor  # noqa: E402


def fake_get(answers):
    """answers: path -> list of responses, one per call, the last repeated."""
    calls = {}

    def get(url, timeout):
        path = url.split("1bigfam.com", 1)[-1] if "1bigfam.com" in url else url
        n = calls.get(path, 0)
        calls[path] = n + 1
        seq = answers[path]
        return dict(seq[min(n, len(seq) - 1)], ms=5)
    return get


READY = {"status": 200, "body": '{"ok": true}', "replica": True}
READY_STANDBY = {"status": 200, "body": '{"ok": true}', "replica": False}
SELFTEST = {"status": 200, "body": "{}", "replica": True}
SELFTEST_STANDBY = {"status": 200, "body": "{}", "replica": False}
FAILED = {"status": None, "error": "TimeoutError", "body": "", "replica": False}


class TestAssess(unittest.TestCase):
    def run_checks(self, answers, attempts=3):
        return monitor.run_checks(monitor.DEFAULT_BASE, attempts, 0,
                                  get=fake_get(answers), sleep=lambda s: None)

    def test_ok_stops_after_one_probe(self):
        probes = self.run_checks({"/readyz": [READY], "/v1/corpus/selftest": [SELFTEST]})
        self.assertEqual(len(probes), 1)
        self.assertEqual(monitor.assess(probes), "ok")

    def test_one_failure_is_retried_and_does_not_count(self):
        probes = self.run_checks({"/readyz": [FAILED, READY], "/v1/corpus/selftest": [SELFTEST]})
        self.assertEqual(len(probes), 2)
        self.assertEqual(monitor.assess(probes), "ok")

    def test_down_when_every_attempt_fails(self):
        probes = self.run_checks({"/readyz": [FAILED], "/v1/corpus/selftest": [FAILED]})
        self.assertEqual(len(probes), 3)
        self.assertEqual(monitor.assess(probes), "down")

    def test_readyz_not_ok_is_down(self):
        not_ok = {"status": 200, "body": '{"ok": false}', "replica": True}
        probes = self.run_checks({"/readyz": [not_ok], "/v1/corpus/selftest": [SELFTEST]})
        self.assertEqual(monitor.assess(probes), "down")

    def test_selftest_503_is_down(self):
        bad = {"status": 503, "body": "{}", "replica": True}
        probes = self.run_checks({"/readyz": [READY], "/v1/corpus/selftest": [bad]})
        self.assertEqual(monitor.assess(probes), "down")

    def test_standby_when_no_answer_carries_the_replica_header(self):
        probes = self.run_checks({"/readyz": [READY_STANDBY],
                                  "/v1/corpus/selftest": [SELFTEST_STANDBY]})
        self.assertEqual(len(probes), 3)
        self.assertEqual(monitor.assess(probes), "standby")


class FakeGitHub:
    def __init__(self, open_issues=()):
        self.issues = [dict(i) for i in open_issues]
        self.log = []

    def open_issues(self):
        return [i for i in self.issues if i.get("state", "open") == "open"]

    def create(self, title, body, assignee):
        self.log.append(("create", title, assignee))
        self.issues.append({"number": len(self.issues) + 1, "title": title, "state": "open"})

    def comment(self, number, body):
        self.log.append(("comment", number))

    def close(self, number):
        self.log.append(("close", number))
        for i in self.issues:
            if i["number"] == number:
                i["state"] = "closed"


PROBE = {"at": "2026-10-24T12:00:00Z", "readyz": 200, "readyz_ms": 5,
         "selftest": 200, "selftest_ms": 5, "space": True, "up": True}


class TestReconcile(unittest.TestCase):
    def test_down_opens_one_issue_assigned_to_the_owner(self):
        gh = FakeGitHub()
        monitor.reconcile("down", [PROBE], gh, monitor.DEFAULT_BASE, "owner")
        monitor.reconcile("down", [PROBE], gh, monitor.DEFAULT_BASE, "owner")
        self.assertEqual(gh.log, [("create", monitor.TITLES["down"], "owner")])

    def test_recovery_comments_and_closes(self):
        gh = FakeGitHub([{"number": 7, "title": monitor.TITLES["down"]}])
        actions = monitor.reconcile("ok", [PROBE], gh, monitor.DEFAULT_BASE)
        self.assertEqual(gh.log, [("comment", 7), ("close", 7)])
        self.assertEqual(actions, [f"closed: {monitor.TITLES['down']}"])

    def test_down_to_standby_swaps_the_issues(self):
        gh = FakeGitHub([{"number": 3, "title": monitor.TITLES["down"]}])
        monitor.reconcile("standby", [PROBE], gh, monitor.DEFAULT_BASE)
        self.assertEqual(sorted(gh.log, key=str), sorted(
            [("create", monitor.TITLES["standby"], ""), ("comment", 3), ("close", 3)], key=str))

    def test_other_issues_are_left_alone(self):
        gh = FakeGitHub([{"number": 1, "title": "something else"}])
        monitor.reconcile("ok", [PROBE], gh, monitor.DEFAULT_BASE)
        self.assertEqual(gh.log, [])


if __name__ == "__main__":
    unittest.main()
