"""Coverage guards for CI selection; runs without scientific dependencies."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ci_plan import changed_paths, main, plan_changes


class ChangePlanTests(unittest.TestCase):
    def test_docs_only_skips_science_and_packages(self):
        plan = plan_changes(["README.md", "docs/gui.md", "mkdocs.yml", "src/aceneurotools/ephys/README.md"])
        self.assertTrue(plan["docs"])
        self.assertFalse(plan["tests"] or plan["package"] or plan["conda"])

    def test_gui_runs_gui_and_alias_contracts_but_not_unrelated_science(self):
        plan = plan_changes(["src/aceneurotools/gui/neurons.py"])
        self.assertIn("tests/test_gui_neurons.py", plan["test_paths"])
        self.assertIn("tests/test_calcium_imaging_names.py", plan["test_paths"])
        self.assertNotIn("tests/test_wavelets.py", plan["test_paths"])
        self.assertTrue(plan["package"])
        self.assertFalse(plan["conda"])

    def test_styles_only_check_packaged_assets(self):
        plan = plan_changes(["src/aceneurotools/gui/style.css"])
        self.assertTrue(plan["package"])
        self.assertFalse(plan["docs"] or plan["tests"] or plan["conda"])

    def test_each_scientific_group_keeps_downstream_integration(self):
        for path, expected in [
            ("src/aceneurotools/ephys/channel.py", "tests/test_rhs2116_data_manager.py"),
            ("src/aceneurotools/miniscope/ucla_data_manager.py", "tests/test_onix_data_manager.py"),
            ("src/aceneurotools/calcium_imaging/movie_io.py", "tests/test_miniscope_filtering.py"),
            ("src/aceneurotools/multimodal/signal_utils.py", "tests/test_mutual_information.py"),
        ]:
            with self.subTest(path=path):
                plan = plan_changes([path])
                self.assertIn(expected, plan["test_paths"])
                self.assertIn("tests/test_gui_multimodal.py", plan["test_paths"])
                self.assertIn("tests/test_miniscope_ephys_alignment.py", plan["test_paths"])
                self.assertTrue(plan["docs"] and plan["tests"] and plan["package"])

    def test_shared_dependencies_ci_and_unknown_paths_fail_open_to_full(self):
        for path in [
            "src/aceneurotools/shared/csv_worker.py",
            "src/aceneurotools/pipelines/ephys.py",
            "pyproject.toml",
            "environment.yml",
            "conda-lock.yml",
            "recipe/recipe.yaml",
            ".github/workflows/ci.yml",
            "scripts/ci_plan.py",
            "tests/parity_probe.py",
            "src/aceneurotools/new_area/reader.py",
            "unknown/config.ini",
        ]:
            with self.subTest(path=path):
                plan = plan_changes([path])
                self.assertEqual(plan["test_paths"], ["tests/"])
                self.assertTrue(all(plan[key] for key in ("docs", "tests", "package", "conda")))

    def test_test_only_change_runs_that_file(self):
        plan = plan_changes(["tests/test_wavelets.py"])
        self.assertEqual(plan["test_paths"], ["tests/test_wavelets.py"])
        self.assertFalse(plan["docs"] or plan["package"] or plan["conda"])

    def test_deleted_test_triggers_full_suite(self):
        self.assertEqual(plan_changes(["tests/test_removed.py"])["test_paths"], ["tests/"])

    def test_gui_test_changes_keep_importing_fixture_consumers(self):
        plan = plan_changes(["tests/test_gui_server.py"])
        self.assertIn("tests/test_gui_launch_security.py", plan["test_paths"])
        self.assertIn("tests/test_gui_parity.py", plan["test_paths"])
        self.assertIn("tests/test_gui_multimodal.py", plan["test_paths"])
        self.assertFalse(plan["package"])

    def test_mixed_changes_union_selected_tests(self):
        plan = plan_changes(["docs/gui.md", "src/aceneurotools/gui/neurons.js", "tests/test_wavelets.py"])
        self.assertTrue(plan["docs"])
        self.assertIn("tests/test_gui_neurons.py", plan["test_paths"])
        self.assertIn("tests/test_wavelets.py", plan["test_paths"])

    def test_new_unclassified_tests_are_included_in_code_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "tests/test_new_feature.py").touch()
            plan = plan_changes(["src/aceneurotools/gui/fields.py"], root=root)
            self.assertIn("tests/test_new_feature.py", plan["test_paths"])

    def test_native_entry_points_require_platform_packages(self):
        for path in ("src/aceneurotools/gui/server.py", "src/aceneurotools/gui/native_dialogs.py"):
            self.assertTrue(plan_changes([path])["conda"])

    def test_pr_uses_merge_base_and_push_includes_entire_commit_range(self):
        cases = [
            (
                {"pull_request": {"base": {"sha": "base"}, "head": {"sha": "head"}}},
                "pull_request",
                "refs/pull/1/merge",
                "base...head",
            ),
            ({"before": "before", "after": "after"}, "push", "refs/heads/main", "before..after"),
        ]
        for event, name, ref, revision_range in cases:
            with (
                self.subTest(name=name),
                patch("scripts.ci_plan.subprocess.check_output", return_value=b"old.py\0new.py\0") as diff,
            ):
                self.assertEqual(changed_paths(event, name, ref), ["old.py", "new.py"])
                self.assertIn(revision_range, diff.call_args.args[0])
                self.assertIn("--no-renames", diff.call_args.args[0])

    def test_unavailable_base_tags_and_manual_runs_force_full(self):
        from subprocess import CalledProcessError

        with patch("scripts.ci_plan.subprocess.check_output", side_effect=CalledProcessError(128, "git")):
            self.assertIsNone(changed_paths({"before": "old", "after": "new"}, "push", "refs/heads/main"))
        self.assertIsNone(changed_paths({"before": "0" * 40, "after": "new"}, "push", "refs/heads/main"))
        for event_name, ref in [
            ("workflow_dispatch", "refs/heads/main"),
            ("push", "refs/tags/v1"),
            ("merge_group", "refs/heads/queue"),
        ]:
            self.assertIsNone(changed_paths({}, event_name, ref))
        self.assertEqual(plan_changes([], force_full=True)["test_paths"], ["tests/"])

    def test_real_git_range_includes_all_pr_commits_and_both_rename_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(
                    ["git", "-c", "user.name=CI Test", "-c", "user.email=ci@example.invalid", *args],
                    cwd=root,
                    text=True,
                ).strip()

            git("init", "-q", "-b", "main")
            (root / "old.py").write_text("original\n")
            git("add", ".")
            git("commit", "-qm", "base")
            before = git("rev-parse", "HEAD")
            git("switch", "-qc", "feature")
            (root / "first.py").write_text("first commit\n")
            git("add", ".")
            git("commit", "-qm", "first")
            git("mv", "old.py", "new.py")
            git("commit", "-qm", "rename")
            head = git("rev-parse", "HEAD")
            git("switch", "-q", "main")
            (root / "unrelated.md").write_text("base branch only\n")
            git("add", ".")
            git("commit", "-qm", "advance base")
            base = git("rev-parse", "HEAD")
            with patch("scripts.ci_plan.ROOT", root):
                pull_request = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
                expected = {"first.py", "old.py", "new.py"}
                self.assertEqual(set(changed_paths(pull_request, "pull_request", "refs/pull/1/merge")), expected)
                self.assertEqual(
                    set(changed_paths({"before": before, "after": head}, "push", "refs/heads/main")), expected
                )

    def test_runner_passes_test_paths_as_arguments_without_shell_expansion(self):
        with (
            patch.dict("os.environ", {"CI_TEST_PATHS": json.dumps(["tests/test_wavelets.py"])}),
            patch("sys.argv", ["ci_plan.py", "--run-tests"]),
            patch("scripts.ci_plan.subprocess.call", return_value=0) as run,
        ):
            with self.assertRaises(SystemExit) as outcome:
                main()
            self.assertEqual(outcome.exception.code, 0)
            self.assertIn("tests/test_wavelets.py", run.call_args.args[0])
            self.assertNotIn("shell", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
