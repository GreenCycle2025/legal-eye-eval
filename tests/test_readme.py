"""Offline checks of the README's generated blocks (no network, standard library only)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import render_readme  # noqa: E402


class TestReadme(unittest.TestCase):
    def test_readme_is_up_to_date_with_the_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "render_readme.py"), "--check"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_badges_follow_latest(self) -> None:
        latest = json.loads((ROOT / "runs" / "latest.json").read_text(encoding="utf-8"))
        badges = render_readme.badges(latest)
        self.assertIn(f"({latest['pass']}%2F{latest['total']})", badges)
        self.assertIn(f"last_run-{latest['date'].replace('-', '--')}-", badges)

    def test_badge_escaping(self) -> None:
        self.assertEqual(render_readme._badge_text("out-of-scope rejection"),
                         "out--of--scope_rejection")
        self.assertEqual(render_readme._badge_text("28% (14/50)"), "28%25_(14%2F50)")

    def test_errors_are_counted_apart_from_verdicts(self) -> None:
        rows = [{"verdict": "PASS"}, {"verdict": "WEAK"}, {"ok": False, "error": "TimeoutError"}]
        self.assertEqual(render_readme.counts(rows),
                         {"total": 3, "PASS": 1, "WEAK": 1, "FAIL": 0, "ERR": 1})

    def test_render_replaces_only_its_blocks(self) -> None:
        text = "a\n<!-- generated:x -->\nold\n<!-- /generated:x -->\nb\n"
        self.assertEqual(render_readme.render(text, {"x": "new"}),
                         "a\n<!-- generated:x -->\nnew\n<!-- /generated:x -->\nb\n")
        empty = "<!-- generated:x -->\n<!-- /generated:x -->\n"
        self.assertEqual(render_readme.render(empty, {"x": "new"}),
                         "<!-- generated:x -->\nnew\n<!-- /generated:x -->\n")

    def test_the_gate_counts_the_strict_verdict_when_a_run_has_it(self) -> None:
        latest = {"date": "2026-10-25", "run_file": "runs/run_2026_10_25.json", "total": 50,
                  "pass": 44, "weak": 6, "fail": 0, "oos_total": 5, "oos_rejected": 5}
        self.assertIn("85% PASS (43/50): met", render_readme.latest_block(latest))
        latest.update(strict_pass=40, strict_weak=6, strict_fail=4)
        block = render_readme.latest_block(latest)
        self.assertIn("on the strict verdict (43/50): not met", block)
        self.assertIn("| 50 questions | 40 (80%) | 6 | 4 |", block)
        self.assertIn("strict_PASS-80%25_(40%2F50)", render_readme.badges(latest))

    def test_build_latest_adds_strict_counts_only_for_runs_that_have_them(self) -> None:
        rows = [{"question": "q1", "verdict": "PASS", "strict_verdict": "FAIL", "ok": True},
                {"question": "q2", "verdict": "PASS", "strict_verdict": "PASS", "ok": True}]
        with tempfile.TemporaryDirectory() as tmp:
            run, out = Path(tmp) / "run_2026_10_25.json", Path(tmp) / "latest.json"
            run.write_text(json.dumps(rows), encoding="utf-8")
            subprocess.run([sys.executable, str(ROOT / "build_latest.py"), str(run), "--out", str(out)],
                           cwd=ROOT, check=True, capture_output=True)
            latest = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual((latest["pass"], latest["strict_pass"], latest["strict_fail"]), (2, 1, 1))
            for r in rows:
                r.pop("strict_verdict")
            run.write_text(json.dumps(rows), encoding="utf-8")
            subprocess.run([sys.executable, str(ROOT / "build_latest.py"), str(run), "--out", str(out)],
                           cwd=ROOT, check=True, capture_output=True)
            self.assertNotIn("strict_pass", json.loads(out.read_text(encoding="utf-8")))

    def test_run_label(self) -> None:
        self.assertEqual(render_readme.run_label(Path("runs/run_2026_05_12_v2.json")),
                         "2026-05-12 (v2)")
        self.assertEqual(render_readme.run_label(Path("runs/run_2026_10_18.json")), "2026-10-18")


class TestHarnessCli(unittest.TestCase):
    def test_retries_never_repeat_an_answered_question(self) -> None:
        """--retries asks again only questions that got no answer."""
        import eval_graph_arguments as ev

        calls = []

        def fake_evaluate(base_url, q, timeout, *, via="lawyer"):
            calls.append(q["question"])
            first = calls.count(q["question"]) == 1
            if q is ev.QUESTIONS[0] and first:
                return {"question": q["question"], "ok": False, "error": "TimeoutError"}
            return {"question": q["question"], "ok": True, "verdict": "WEAK",
                    "anchor_label_match": True}

        original = ev.evaluate, ev.time.sleep, ev.print_table
        ev.evaluate, ev.time.sleep, ev.print_table = fake_evaluate, lambda s: None, lambda rows: None
        argv = sys.argv
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "run.json"
                sys.argv = ["eval", "--retries", "1", "--json", str(out)]
                ev.main()
                rows = json.loads(out.read_text(encoding="utf-8"))
        finally:
            ev.evaluate, ev.time.sleep, ev.print_table = original
            sys.argv = argv
        self.assertEqual(len(calls), len(ev.QUESTIONS) + 1)
        self.assertEqual(rows[0]["attempts"], 2)
        self.assertTrue(all(r["attempts"] == 1 for r in rows[1:]))


if __name__ == "__main__":
    unittest.main()
