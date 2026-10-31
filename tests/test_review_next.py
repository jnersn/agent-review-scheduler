import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("review_next", str(HERE / "review-next"))
spec = importlib.util.spec_from_loader("review_next", loader)
rn = importlib.util.module_from_spec(spec)
loader.exec_module(rn)

NOW = dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.timezone.utc)


def ago(days):
    return (NOW - dt.timedelta(days=days)).isoformat()


def ts(days):
    return (NOW - dt.timedelta(days=days)).timestamp()


CFG = {
    "app_paths": ["src/", "tests/"],
    "doc_paths": ["AGENTS.md", "docs/"],
    "layers": {
        "services": {"title": "Services", "paths": ["src/services/", "!src/services/legacy/"]},
        "ui": {"title": "UI", "paths": ["src/ui/"]},
    },
    "types": {
        "regression": {"scope": "diff"},
        "area-bug-hunt": {"scope": "area", "cadence_days": 1},
        "maintainability": {"scope": "layer", "cadence_days": 7, "churn_boost": True},
        "performance": {"scope": "layer", "cadence_days": 30, "issue_keywords": ["slow", "main thread"]},
        "docs-hygiene": {"scope": "app", "cadence_days": 30, "docs_boost": True},
        "release-readiness": {"scope": "app", "cadence_days": 90, "release_boost": True},
    },
}
AREAS = [("Sidebar", "ui/sidebar/, SidebarTree: counts"), ("Video", "media playback paths, PlayerController lifecycle")]


def signals(**kw):
    base = {"head": "b" * 40, "history": [], "regression_base": "a" * 40, "regression_commits": 0, "issues": [], "release": None}
    base.update(kw)
    return base


def script(directory, name, body):
    """An executable shell script, used as a fake reviewer or issue command."""
    path = Path(directory) / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return str(path)


class PureHelpers(unittest.TestCase):
    def test_parse_areas_skips_comments_and_blanks(self):
        text = "# comment\n\nSidebar | ui/sidebar/: counts\nVideo | PlayerController\n"
        self.assertEqual(rn.parse_areas(text), [("Sidebar", "ui/sidebar/: counts"), ("Video", "PlayerController")])

    def test_in_paths_with_excludes(self):
        pats = CFG["layers"]["services"]["paths"]
        self.assertTrue(rn.in_paths("src/services/billing.py", pats))
        self.assertFalse(rn.in_paths("src/services/legacy/old.py", pats))
        self.assertFalse(rn.in_paths("src/ui/x.py", pats))

    def test_area_tokens_keep_paths_and_type_names(self):
        toks = rn.area_tokens("ui/sidebar/ (NavMenu, SidebarTree): counts after scans, IndexService(+FileIO)")
        self.assertIn("ui/sidebar", toks)
        self.assertIn("SidebarTree", toks)
        self.assertIn("IndexService", toks)
        self.assertNotIn("counts", toks)

    def test_parse_history(self):
        log = "\x011700000000\n\n10\t2\tsrc/a.py\n-\t-\tsrc/img.png\n\x011700000100\n\n1\t1\tAGENTS.md\n"
        self.assertEqual(rn.parse_history(log), [(1700000000, [("src/a.py", 12), ("src/img.png", 0)]),
                                                 (1700000100, [("AGENTS.md", 2)])])

    def test_parse_counts_prefers_the_summary_line(self):
        report = "1. **X**\n- severity: high\n2. **Y**\n- severity: low\n\n0 critical, 1 high, 0 medium, 1 low"
        self.assertEqual(rn.parse_counts(report), {"critical": 0, "high": 1, "medium": 0, "low": 1})
        self.assertEqual(rn.parse_counts("- Severity: medium\n- Severity: medium"), {"critical": 0, "high": 0, "medium": 2, "low": 0})

    def test_release_signal_only_for_open_milestones_due_soon(self):
        soon = {"state": "open", "milestone": {"title": "1.7.0", "due_on": "2026-10-30T00:00:00Z"}}
        late = {"state": "open", "milestone": {"title": "2.0.0", "due_on": "2027-03-01T00:00:00Z"}}
        closed = {"state": "closed", "milestone": {"title": "1.6.0", "due_on": "2026-10-25T00:00:00Z"}}
        undated = {"state": "open", "milestone": {"title": "1.8.0", "due_on": None}}
        self.assertIn("1.7.0", rn.release_signal([late, closed, undated, soon], NOW))
        self.assertIsNone(rn.release_signal([late, closed, undated], NOW))

    def test_gh_issue_fields(self):
        raw = {"number": 7, "title": "Slow", "state": "OPEN", "createdAt": "2026-10-20T10:00:00Z",
               "milestone": {"number": 1, "title": "1.0", "description": "", "dueOn": "2026-11-01T00:00:00Z"}}
        self.assertEqual(rn.gh_issue(raw), {"number": 7, "title": "Slow", "state": "open", "created_at": "2026-10-20T10:00:00Z",
                                            "milestone": {"title": "1.0", "due_on": "2026-11-01T00:00:00Z"}})
        self.assertIsNone(rn.gh_issue({**raw, "milestone": None})["milestone"])


class Scoring(unittest.TestCase):
    def test_regression_only_when_commits_are_unreviewed(self):
        t = CFG["types"]["regression"]
        self.assertEqual(rn.score_type("regression", t, CFG, [], signals(regression_commits=0), NOW)[0], 0)
        self.assertEqual(rn.score_type("regression", t, CFG, [], signals(regression_commits=None), NOW)[0], 0)
        self.assertGreater(rn.score_type("regression", t, CFG, [], signals(regression_commits=10), NOW)[0], 1)

    def test_overdue_grows_with_time_and_is_capped(self):
        t = CFG["types"]["docs-hygiene"]
        fresh = [{"type": "docs-hygiene", "scope": "app", "at": ago(3)}]
        old = [{"type": "docs-hygiene", "scope": "app", "at": ago(400)}]
        self.assertLess(rn.score_type("docs-hygiene", t, CFG, fresh, signals(), NOW)[0], 0.2)
        self.assertEqual(rn.score_type("docs-hygiene", t, CFG, old, signals(), NOW)[0], rn.MAX_OVERDUE)

    def test_boosts(self):
        ledger = [{"type": "maintainability", "scope": "services", "at": ago(7)}]
        churn = signals(history=[(ts(1), [("src/services/a.py", 5000)])])
        self.assertGreater(rn.score_type("maintainability", CFG["types"]["maintainability"], CFG, ledger, churn, NOW)[0],
                           rn.score_type("maintainability", CFG["types"]["maintainability"], CFG, ledger, signals(), NOW)[0])
        issues = signals(issues=[{"number": 1, "title": "Grid is slow with 10k items", "created_at": ago(2)},
                                 {"number": 2, "title": "Nightly review 2026-10-20: slow paths", "created_at": ago(1)}])
        score, why = rn.score_type("performance", CFG["types"]["performance"], CFG, [], issues, NOW)
        self.assertAlmostEqual(score, rn.NEVER_RUN_SCORE + 0.4)  # the review report itself is not a signal
        self.assertIn("#1", " ".join(why))
        rel = rn.score_type("release-readiness", CFG["types"]["release-readiness"], CFG, [], signals(release="milestone due"), NOW)[0]
        self.assertAlmostEqual(rel, rn.NEVER_RUN_SCORE + 1.5)

    def test_yield_and_cooldown(self):
        t = CFG["types"]["docs-hygiene"]
        found = [{"type": "docs-hygiene", "scope": "app", "at": ago(30), "counts": {"critical": 0, "high": 1, "medium": 0, "low": 0}}]
        empty = [{"type": "docs-hygiene", "scope": "app", "at": ago(30), "counts": {s: 0 for s in rn.SEVERITIES}}]
        self.assertGreater(rn.score_type("docs-hygiene", t, CFG, found, signals(), NOW)[0],
                           rn.score_type("docs-hygiene", t, CFG, empty, signals(), NOW)[0])
        just_now = [{"type": "docs-hygiene", "scope": "app", "at": ago(0.1)}]
        self.assertIn("ran 2 h ago", rn.score_type("docs-hygiene", t, CFG, just_now, signals(), NOW)[1])


class ScopeAndPlan(unittest.TestCase):
    def test_layer_scope_prefers_churn_then_age(self):
        ledger = [{"type": "maintainability", "scope": "services", "at": ago(2)}, {"type": "maintainability", "scope": "ui", "at": ago(2)}]
        sig = signals(history=[(ts(1), [("src/ui/a.py", 10), ("src/ui/b.py", 10)])])
        self.assertEqual(rn.choose_scope("maintainability", CFG["types"]["maintainability"], CFG, ledger, sig, NOW, AREAS)["key"], "ui")
        ledger = [{"type": "maintainability", "scope": "ui", "at": ago(1)}]  # services never reviewed
        self.assertEqual(rn.choose_scope("maintainability", CFG["types"]["maintainability"], CFG, ledger, signals(), NOW, AREAS)["key"], "services")

    def test_area_scope_matches_changed_files_and_rotates(self):
        ledger = [{"type": "area-bug-hunt", "scope": "Sidebar", "at": ago(1)}]
        sig = signals(history=[(ts(0.5), [("src/ui/sidebar/x.py", 3)])])
        self.assertEqual(rn.choose_scope("area-bug-hunt", CFG["types"]["area-bug-hunt"], CFG, ledger, sig, NOW, AREAS)["key"], "Video")
        self.assertEqual(rn.choose_scope("area-bug-hunt", CFG["types"]["area-bug-hunt"], CFG, [], sig, NOW, AREAS)["key"], "Sidebar")

    def test_plan_picks_top_two_and_sets_delivery(self):
        sig = signals(regression_commits=12)
        picks, scores = rn.plan(CFG, [], sig, NOW, AREAS, 2)
        self.assertEqual(len(picks), 2)
        self.assertEqual(picks[0]["type"], "regression")
        self.assertEqual(picks[0]["deliver"], "print")
        self.assertEqual(picks[1]["deliver"], "print" if picks[1]["kind"] in rn.NARROW_SCOPES else "issue")
        self.assertEqual([s for s, _, _ in scores], sorted([s for s, _, _ in scores], reverse=True))

    def test_repeated_runs_move_on(self):
        sig = signals()
        first, _ = rn.plan(CFG, [], sig, NOW, AREAS, 2)
        ledger = [{"type": p["type"], "scope": p["scope"]["key"], "at": NOW.isoformat()} for p in first]
        second, _ = rn.plan(CFG, ledger, sig, NOW, AREAS, 2)
        self.assertFalse({p["type"] for p in first} & {p["type"] for p in second})

    def test_forced_types_and_scopes(self):
        picks, _ = rn.plan(CFG, [], signals(), NOW, AREAS, 2, ["maintainability:ui", "docs-hygiene"])
        self.assertEqual([(p["type"], p["scope"]["key"]) for p in picks], [("maintainability", "ui"), ("docs-hygiene", "app")])
        self.assertEqual(picks[0]["reasons"][0], "requested")
        with self.assertRaises(SystemExit):
            rn.plan(CFG, [], signals(), NOW, AREAS, 2, ["regression"])  # nothing to review
        with self.assertRaises(SystemExit):
            rn.plan(CFG, [], signals(), NOW, AREAS, 2, ["nope"])


class Reports(unittest.TestCase):
    def test_brief_names_only_the_needed_files(self):
        p = {"type": "maintainability", "kind": "layer", "scope": {"title": "Services", "detail": "src/services/"}, "reasons": []}
        text = rn.brief(p, {"app": "Example"}, "c" * 40, {})
        self.assertIn(".review/types/maintainability.md", text)
        self.assertIn("Scope details: src/services/", text)
        self.assertNotIn("changes.diff", text)

    def test_findings_come_from_the_last_json_block_sorted_by_severity(self):
        reply = ('Review type: x\n\nSummary.\n\n```json\n{"findings": ['
                 '{"title": "**Small thing.**", "severity": "LOW", "confidence": "confirmed", "body": "B1"},'
                 '{"title": "Big thing", "severity": "high", "confidence": "plausible", "body": "B2"},'
                 '{"severity": "low"}]}\n```\n')
        prose, findings = rn.parse_findings(reply)
        self.assertEqual(prose, "Review type: x\n\nSummary.")
        self.assertEqual([(f["title"], f["severity"], f["confidence"]) for f in findings],
                         [("Big thing", "high", "PLAUSIBLE"), ("Small thing", "low", "CONFIRMED")])
        self.assertEqual(rn.count_findings(findings), {"critical": 0, "high": 1, "medium": 0, "low": 1})
        self.assertEqual(rn.parse_findings("no block"), ("no block", None))
        self.assertIsNone(rn.parse_findings("```json\nnot json\n```")[1])

    def test_trailing_commas_outside_strings_are_tolerated(self):
        reply = ('```json\n{"findings": [\n  {"title": "A", "severity": "low", "body": "x, ] \\" ,}",\n  },\n]}\n```')
        _, findings = rn.parse_findings(reply)
        self.assertEqual([(f["title"], f["body"]) for f in findings], [("A", 'x, ] " ,}')])
        self.assertEqual(rn.drop_trailing_commas('{"a": [1, 2,], "b": ",]"}'), '{"a": [1, 2], "b": ",]"}')

    def test_section_renders_findings_with_ids(self):
        p = {"type": "regression", "kind": "diff", "scope": {"title": "a..b"}, "reasons": ["r"]}
        sec = rn.section(2, p, 'Summary.\n```json\n{"findings": [{"title": "T", "severity": "medium", "confidence": "CONFIRMED", "body": "B"}]}\n```')
        self.assertIn("### 2.1. T\n\nSeverity: medium. Confidence: CONFIRMED.\n\nB", sec)
        self.assertTrue(sec.endswith("0 critical, 0 high, 1 medium, 0 low."))
        self.assertIn("No findings.", rn.section(1, p, 'S\n```json\n{"findings": []}\n```'))

    def test_decide_applies_rules_triage_and_the_cap(self):
        f = lambda i, sev, conf: {"id": i, "title": i, "severity": sev, "confidence": conf, "body": ""}
        findings = [f("1.1", "high", "PLAUSIBLE"), f("1.2", "medium", "PLAUSIBLE"), f("1.3", "low", "CONFIRMED"),
                    f("2.1", "medium", "CONFIRMED"), f("2.2", "low", "CONFIRMED")]
        decisions = {"1.1": {"decision": "file", "reason": "a"}, "1.3": {"decision": "file", "reason": "b"},
                     "2.1": {"decision": "duplicate", "issue": 7, "reason": "c"}}
        rn.decide(findings, decisions, cap=1)
        self.assertEqual([x["outcome"] for x in findings], ["file", "skip", "skip", "duplicate", "skip"])
        self.assertIn("not confirmed", findings[1]["reason"])
        self.assertIn("nightly limit of 1", findings[2]["reason"])
        self.assertEqual(findings[4]["reason"], "triage gave no decision")
        rn.decide(findings, None, cap=3)
        self.assertEqual(findings[0]["reason"], "triage failed; not filed")

    def test_issues_filed_for_findings_are_not_keyword_signals(self):
        ledger = [{"type": "regression", "delivered": ["o/r#12", "#13"]}, {"type": "x", "delivered": "report"}]
        self.assertEqual(rn.filed_numbers(ledger), {12, 13})

    def test_a_single_review_over_the_limit_is_cut_and_points_at_the_report(self):
        body = rn.fit_body("intro", ["x" * 500], "footer", Path("/state/r.md"), limit=200)
        self.assertLessEqual(len(body), 200)
        self.assertTrue(body.startswith("intro\n\nxxx"))
        self.assertIn("`/state/r.md`", body)
        self.assertTrue(body.endswith("\n\nfooter"))


class Plans(unittest.TestCase):
    def test_plan_found_by_file_directory_or_name(self):
        with tempfile.TemporaryDirectory() as d:
            config = Path(d) / "config"
            plan_dir = config / "web"
            plan_dir.mkdir(parents=True)
            (plan_dir / "review-plan.json").write_text(json.dumps({"repo": "~/src/web"}))
            with mock.patch.object(rn, "CONFIG_HOME", config):
                for arg in (str(plan_dir / "review-plan.json"), str(plan_dir), "web"):
                    cfg = rn.load_plan(arg)
                    self.assertEqual((cfg["name"], cfg["app"], cfg["ref"]), ("web", "web", "origin/main"))
                with self.assertRaises(SystemExit):
                    rn.load_plan("missing")

    def test_plan_paths_are_relative_to_the_plan(self):
        cfg = {"dir": Path("/plans/web")}
        self.assertEqual(rn.plan_path(cfg, "areas.txt"), Path("/plans/web/areas.txt"))
        self.assertEqual(rn.plan_path(cfg, "/abs/types"), Path("/abs/types"))
        self.assertEqual(rn.plan_path(cfg, "~/types"), Path.home() / "types")

    def test_plan_commands_resolve_relative_to_the_plan(self):
        with tempfile.TemporaryDirectory() as d:
            plan = Path(d).resolve() / "review-plan.json"
            plan.write_text(json.dumps({"repo": ".", "issues": {"repo": "o/r", "command": {"list": ["./tracker", "list"], "create": ["tracker"]}},
                                        "reviewers": [{"command": ["~/bin/agent", "{prompt}"], "api_key_command": ["../key"]}]}))
            cfg = rn.load_plan(str(plan))
            self.assertEqual(cfg["issues"]["command"]["list"], [str(plan.parent / "tracker"), "list"])
            self.assertEqual(cfg["issues"]["command"]["create"], ["tracker"])
            self.assertEqual(cfg["reviewers"][0]["command"][0], str(Path.home() / "bin/agent"))
            self.assertEqual(cfg["reviewers"][0]["api_key_command"], [str(plan.parent / "../key")])


class Reviewers(unittest.TestCase):
    def test_falls_through_to_the_next_reviewer_and_fills_placeholders(self):
        with tempfile.TemporaryDirectory() as d:
            failing = script(d, "failing", "echo 'You have hit your limit'\n")
            json_out = script(d, "json", 'printf \'{"result": "Report for %s at %s", "total_cost_usd": 1.234, "num_turns": 9}\' "$2" "$4"\n')
            reviewers = [{"label": "first", "command": [failing], "output": "text"},
                         {"label": "second", "command": [json_out, "--model", "{model}", "--effort", "{effort}", "-p", "{prompt}"],
                          "output": "claude-json"}]
            report, label, usage = rn.run_reviewer("brief", Path(d), Path(d) / "out.json", "opus", "medium", reviewers, Path(d) / "err")
            self.assertEqual((report, label, usage), ("Report for opus at medium", "second", {"cost_usd": 1.23, "turns": 9}))
            self.assertIn("first failed", (Path(d) / "err").read_text())

    def test_api_key_is_passed_only_when_available_and_unset_env_is_removed(self):
        with tempfile.TemporaryDirectory() as d:
            show = script(d, "show", 'echo "key=${ANTHROPIC_API_KEY:-none} token=${OTHER_TOKEN:-none}"\n')
            no_key = script(d, "nokey", "exit 1\n")
            has_key = script(d, "haskey", "echo sk-test\n")
            with mock.patch.dict(os.environ, {"OTHER_TOKEN": "t"}):
                reviewers = [{"label": "credits", "command": [show], "api_key_command": [no_key]},
                             {"label": "plain", "command": [show], "unset_env": ["OTHER_TOKEN"]}]
                report, label, _ = rn.run_reviewer("b", Path(d), Path(d) / "o", "m", "e", reviewers, Path(d) / "err")
                self.assertEqual((report.strip(), label), ("key=none token=none", "plain"))
                reviewers[0]["api_key_command"] = [has_key]
                report, label, _ = rn.run_reviewer("b", Path(d), Path(d) / "o", "m", "e", reviewers, Path(d) / "err")
                self.assertEqual((report.strip(), label), ("key=sk-test token=t", "credits"))

    def test_all_reviewers_failing(self):
        with tempfile.TemporaryDirectory() as d:
            broken = script(d, "broken", 'echo \'{"is_error": true, "result": "x"}\'\n')
            report, label, _ = rn.run_reviewer("b", Path(d), Path(d) / "o", "m", "e",
                                               [{"command": [broken], "output": "claude-json"}], Path(d) / "err")
            self.assertIsNone(report)
            self.assertIn("all reviewers failed", label)


class Issues(unittest.TestCase):
    def test_issue_commands_follow_the_json_contract(self):
        with tempfile.TemporaryDirectory() as d:
            lister = script(d, "list", 'echo \'[{"number": 3, "title": "T", "state": "open", "created_at": "2026-10-01T00:00:00Z", '
                                       '"milestone": null}]\'; echo "$1" > ' + d + "/listed\n")
            creator = script(d, "create", "cat > " + d + '/request.json; echo \'{"ref": "#9", "url": "https://example/9"}\'\n')
            cfg = {"issues": {"repo": "o/r", "labels": ["review"], "command": {"list": [lister, "{repo}"], "create": [creator]}}}
            self.assertEqual(rn.fetch_issues(cfg)[0]["number"], 3)
            self.assertEqual((Path(d) / "listed").read_text().strip(), "o/r")
            self.assertEqual(rn.file_issue(cfg, "Title", "Body", "req-1", []), ("#9", "#9 https://example/9"))
            self.assertEqual(json.loads((Path(d) / "request.json").read_text()),
                             {"repo": "o/r", "title": "Title", "body": "Body", "labels": ["review"], "request_id": "req-1"})
            rn.file_issue(cfg, "Title", "Body", "req-2", [], ["review", "severity/low"])
            self.assertEqual(json.loads((Path(d) / "request.json").read_text())["labels"], ["review", "severity/low"])

    def test_without_an_issue_repo_reports_stay_files(self):
        self.assertEqual(rn.fetch_issues({}), [])
        ref, where = rn.file_issue({}, "T", "B", "r", [])
        self.assertEqual(ref, "report")

    def test_gh_does_not_file_the_same_open_title_twice(self):
        cfg = {"issues": {"repo": "o/r"}}
        known = [{"number": 4, "title": "Nightly review 2026-10-21: x", "state": "open"}]
        with mock.patch.object(rn.subprocess, "run") as run:
            self.assertEqual(rn.file_issue(cfg, "Nightly review 2026-10-21: x", "B", "r", known)[0], "#4")
            run.assert_not_called()


class EndToEnd(unittest.TestCase):
    def test_a_run_against_a_real_repository(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            origin, repo = d / "origin.git", d / "repo"
            git = lambda *a, cwd=repo: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
            subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
            subprocess.run(["git", "clone", "-q", str(origin), str(repo)], check=True, capture_output=True)
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "T")
            (repo / "src" / "ui").mkdir(parents=True)
            (repo / "src" / "ui" / "view.py").write_text("print(1)\n")
            git("add", "-A")
            git("commit", "-q", "-m", "one")
            git("push", "-q", "origin", "HEAD:main")
            reviewer = script(d, "reviewer", 'ls .review/types > "$(dirname "$0")/seen"; echo "Review type: x\n\n0 critical, 0 high, 1 medium, 0 low"\n')
            plan_dir = d / "plan"
            plan_dir.mkdir()
            (plan_dir / "areas.txt").write_text("UI | src/ui/: everything\n")
            (plan_dir / "review-plan.json").write_text(json.dumps({
                "app": "Example", "repo": str(repo), "app_paths": ["src/"], "areas_file": "areas.txt",
                "state_dir": str(d / "state"),
                "layers": {"ui": {"title": "UI", "paths": ["src/ui/"]}},
                "types": {"regression": {"scope": "diff"}, "area-bug-hunt": {"scope": "area", "cadence_days": 1},
                          "maintainability": {"scope": "layer", "cadence_days": 7}},
                "reviewers": [{"label": "fake", "command": [reviewer], "output": "text"}]}))
            out = StringIO()
            with redirect_stdout(out):
                self.assertEqual(rn.main([str(plan_dir), "--record", "regression"]), 0)
                self.assertEqual(rn.main([str(plan_dir), "--plan"]), 0)
                code = rn.main([str(plan_dir), "--type", "area-bug-hunt", "--type", "maintainability"])
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("never reviewed", out.getvalue())
            self.assertIn("Reviewer: fake", out.getvalue())
            self.assertIn("not filed (the plan has no issue repo)", out.getvalue())
            self.assertEqual((d / "seen").read_text().split(), ["area-bug-hunt.md", "maintainability.md"])
            ledger = rn.read_ledger(d / "state" / "ledger.jsonl")
            self.assertEqual([(e["type"], e["mode"]) for e in ledger],
                             [("regression", "recorded"), ("area-bug-hunt", "manual"), ("maintainability", "manual")])
            self.assertEqual(ledger[1]["counts"]["medium"], 1)
            self.assertEqual(ledger[2]["delivered"], "report")
            self.assertEqual(len(list((d / "state" / "reports").glob("*.md"))), 1)
            self.assertFalse((d / "state" / "worktree" / ".review").exists())
            git("worktree", "remove", "--force", str(d / "state" / "worktree"))

    def test_a_nightly_run_files_one_issue_per_triaged_finding(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            repo = d / "repo"
            git = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
            repo.mkdir()
            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "T")
            (repo / "src").mkdir()
            (repo / "src" / "a.py").write_text("print(1)\n")
            git("add", "-A")
            git("commit", "-q", "-m", "one")
            findings = json.dumps({"findings": [
                {"title": "Real bug", "severity": "medium", "confidence": "CONFIRMED", "body": "Scenario."},
                {"title": "Known bug", "severity": "high", "confidence": "CONFIRMED", "body": "Seen."},
                {"title": "Maybe", "severity": "low", "confidence": "PLAUSIBLE", "body": "?"}]})
            decisions = json.dumps({"decisions": [{"id": "1.2", "decision": "file", "reason": "Confirmed."},
                                                  {"id": "1.1", "decision": "duplicate", "issue": 3, "reason": "Same."}]})
            (d / "findings.json").write_text(findings)
            (d / "decisions.json").write_text(decisions)
            reviewer = d / "reviewer"
            reviewer.write_text("#!/usr/bin/env python3\nimport os, sys\nd = os.path.dirname(sys.argv[0])\n"
                                "if 'triage' in sys.argv[1]:\n"
                                "    open(os.path.join(d, 'triage-seen'), 'w').write(' '.join(os.listdir('.review')))\n"
                                "    print('Notes\\n```json\\n' + open(os.path.join(d, 'decisions.json')).read() + '\\n```')\n"
                                "else:\n"
                                "    print('Review type: x\\n\\nSummary.\\n```json\\n' + open(os.path.join(d, 'findings.json')).read() + '\\n```')\n")
            reviewer.chmod(0o755)
            reviewer = str(reviewer)
            creator = script(d, "create", "cat >> " + str(d) + '/requests.jsonl; echo >> ' + str(d) + '/requests.jsonl; echo \'{"ref": "o/r#21", "url": "https://example/21"}\'\n')
            lister = script(d, "list", 'echo \'[{"number": 3, "title": "Known bug", "state": "open", "created_at": "2026-10-01T00:00:00Z", "milestone": null}]\'\n')
            plan_dir = d / "plan"
            plan_dir.mkdir()
            (plan_dir / "review-plan.json").write_text(json.dumps({
                "app": "Example", "repo": str(repo), "ref": "main", "app_paths": ["src/"], "state_dir": str(d / "state"),
                "layers": {"src": {"title": "Source", "paths": ["src/"]}},
                "types": {"maintainability": {"scope": "layer", "cadence_days": 7}},
                "issues": {"repo": "o/r", "labels": ["qa"], "severity_labels": {"medium": ["severity/medium"]},
                           "command": {"list": [lister, "{repo}"], "create": [creator]}},
                "reviewers": [{"label": "fake", "command": [reviewer, "{prompt}"], "output": "text"}]}))
            out = StringIO()
            with redirect_stdout(out):
                code = rn.main([str(plan_dir), "--nightly", "--count", "1"])
            self.assertEqual(code, 0, out.getvalue())
            requests = [json.loads(line) for line in (d / "requests.jsonl").read_text().split("\n") if line.strip()]
            self.assertEqual([(r["title"], r["labels"]) for r in requests], [("Real bug", ["qa", "severity/medium"])])
            self.assertIn("Scenario.", requests[0]["body"])
            self.assertIn("finding 1.2", requests[0]["body"])
            self.assertIn("Triage: Confirmed.", requests[0]["body"])
            self.assertIn("candidates.json", (d / "triage-seen").read_text())
            report = next((d / "state" / "reports").glob("*.md")).read_text()
            self.assertIn("1.2 (medium) Real bug: filed as o/r#21. Confirmed.", report)
            self.assertIn("1.1 (high) Known bug: duplicate of #3. Same.", report)
            self.assertIn("1.3 (low) Maybe: skipped. not confirmed", report)
            ledger = rn.read_ledger(d / "state" / "ledger.jsonl")
            self.assertEqual(ledger[0]["delivered"], ["o/r#21"])
            self.assertEqual(ledger[0]["counts"], {"critical": 0, "high": 1, "medium": 1, "low": 1})
            self.assertFalse((d / "state" / "worktree" / ".review").exists())
            git("worktree", "remove", "--force", str(d / "state" / "worktree"))


if __name__ == "__main__":
    unittest.main()
