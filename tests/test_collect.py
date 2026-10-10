"""Tests for the evidence rules and activity stats, run against a small throwaway git repo."""

import datetime as dt
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
import collect  # noqa: E402

CURRICULUM = textwrap.dedent("""
    program: {name: Test program, institute: Test, months: 6, course_page: x, course_repo: a/b, owner: Me, start_date: "2026-09-28"}
    modules:
      - id: M1
        title: One
        schedule: Week 1
        weeks: [1]
        topics:
          - name: Uses OpenAI
            evidence: [{imports: [openai]}]
          - name: Uses LangChain (sibling package)
            evidence: [{imports: [langchain]}]
          - name: HyDE
            evidence: [{patterns: ["\\\\bHyDE\\\\b"]}]
          - name: Two providers in one file
            evidence: [{providers: {any: [openai, ollama], min: 2}}]
          - name: Capstone folder only at top level
            evidence: [{paths: ["*capstone*/**"]}]
          - name: Concept only
        project:
          name: Three chains
          evidence: [{count: {pattern: "\\\\w+_chain\\\\s*=", min: 3}}]
""")


def git(repo, *args, date=None):
    env = None
    if date:
        env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date, "PATH": "/usr/bin:/bin"}
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, env=env)


class CollectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        repo = cls.repo = cls.tmp.name
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "t@example.com")
        git(repo, "config", "user.name", "Tester")
        files = {
            "a/compare.py": "import openai\nimport ollama\n",
            "a/notes.py": "city = 'Hyderabad'\n",
            "a/nb.ipynb": json.dumps({"cells": [{"cell_type": "code", "source": [
                "%pip install x\n", "from langchain_core.prompts import PromptTemplate\n",
                "a_chain = 1\n", "b_chain = 2\n", "c_chain = 3\n"]}]}),
            "module/03_capstone/app.py": "import openai\n",
            "a/requirements.txt": "openai\n",
        }
        for i, (path, text) in enumerate(files.items()):
            p = Path(repo) / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
            git(repo, "add", path)
            git(repo, "commit", "-q", "-m", f"add {path}", date=f"2026-10-0{1 + (i % 2)}T10:00:00+05:30")
        cls.data = collect.collect(repo, cls._curriculum(), dt.date(2026, 10, 3))

    @classmethod
    def _curriculum(cls):
        p = Path(cls.tmp.name).parent / "curriculum_test.yaml"
        p.write_text(CURRICULUM)
        return p

    def topic(self, name):
        return next(t for t in self.data["modules"][0]["topics"] if t["name"] == name)

    def test_imports(self):
        self.assertTrue(self.topic("Uses OpenAI")["evidence"])

    def test_sibling_package_and_notebook(self):
        ev = self.topic("Uses LangChain (sibling package)")["evidence"]
        self.assertEqual(ev[0]["path"], "a/nb.ipynb")

    def test_word_boundary_avoids_false_positive(self):
        self.assertEqual(self.topic("HyDE")["evidence"], [])

    def test_providers_in_one_file(self):
        self.assertEqual(self.topic("Two providers in one file")["evidence"][0]["path"], "a/compare.py")

    def test_nested_capstone_folder_does_not_count(self):
        self.assertEqual(self.topic("Capstone folder only at top level")["evidence"], [])

    def test_concept_topics_are_not_trackable(self):
        self.assertFalse(self.topic("Concept only")["trackable"])

    def test_project_count_rule_and_status(self):
        m = self.data["modules"][0]
        self.assertTrue(m["project"]["evidence"])
        self.assertEqual((m["covered"], m["trackable"]), (3, 5))
        self.assertEqual(m["status"], "completed")  # project built and 60% of trackable topics

    def test_activity_and_streaks(self):
        s = self.data["stats"]
        self.assertEqual(s["commits"], 5)
        self.assertEqual(s["active_days"], 2)
        self.assertEqual((s["current_streak"], s["longest_streak"]), (2, 2))
        self.assertEqual(self.data["program"]["week_now"], 1)

    def test_projects_from_requirements(self):
        self.assertEqual([p["path"] for p in self.data["projects"]], ["a"])
        self.assertIn("openai", self.data["projects"][0]["libraries"])


if __name__ == "__main__":
    unittest.main()
