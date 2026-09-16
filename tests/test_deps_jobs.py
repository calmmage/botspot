"""Structural + unit checks for the weekly dep jobs (not live GitHub)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location(
    "suggest_library_improvement",
    ROOT / "scripts" / "suggest_library_improvement.py",
)
assert _SPEC and _SPEC.loader
_suggest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_suggest)
already_has_open_suggestion = _suggest.already_has_open_suggestion
build_prompt = _suggest.build_prompt
run = _suggest.run


def test_upgrade_script_is_uv_lock_upgrade():
    script = (ROOT / "scripts" / "upgrade-deps.sh").read_text(encoding="utf-8")
    assert "uv lock --upgrade" in script


def test_dependabot_stops_per_package_prs():
    text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert "open-pull-requests-limit: 0" in text
    assert "python-dependencies" in text
    assert "patterns:" in text
    assert '"*"' in text or "- '*'" in text or '- "*"' in text
    # enable-beta-ecosystems is a top-level key; nesting it under updates is invalid.
    nested = any(
        (line.startswith(" ") or line.startswith("\t"))
        and line.strip().startswith("enable-beta-ecosystems:")
        for line in text.splitlines()
    )
    assert not nested


def test_weekly_batch_workflow_tests_then_merges():
    text = (ROOT / ".github" / "workflows" / "deps-weekly.yml").read_text(encoding="utf-8")
    assert "cron:" in text
    assert "scripts/upgrade-deps.sh" in text
    assert "pytest" in text
    assert "gh pr merge" in text


def test_automerge_covers_dependabot_and_weekly_branch():
    text = (ROOT / ".github" / "workflows" / "deps-automerge.yml").read_text(encoding="utf-8")
    assert "dependabot[bot]" in text
    assert "deps/weekly-" in text
    assert "--auto" in text


def test_agentic_workflow_is_capped_and_separate():
    text = (ROOT / ".github" / "workflows" / "deps-suggest.yml").read_text(encoding="utf-8")
    assert "cron:" in text
    assert "suggest_library_improvement.py" in text
    assert "XAI_API_KEY" in text
    weekly = (ROOT / ".github" / "workflows" / "deps-weekly.yml").read_text(encoding="utf-8")
    assert "suggest_library_improvement.py" not in weekly


def test_already_has_open_suggestion_caps_at_one():
    assert already_has_open_suggestion(
        [{"labels": [{"name": "weekly-library-improvement"}]}]
    )
    assert not already_has_open_suggestion([{"labels": [{"name": "bug"}]}])
    assert not already_has_open_suggestion([])


def test_build_prompt_rejects_bump_flood():
    prompt = build_prompt("[project]\nname = 'botspot'\n")
    assert "ONE" in prompt
    assert "Not a version bump" in prompt


def test_run_noops_without_llm_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    created = []
    assert run(api_key="", token="t", create=lambda *a, **k: created.append(a)) == 0
    assert created == []


def test_run_skips_when_open_issue_exists():
    created = []
    issues = [{"labels": [{"name": "weekly-library-improvement"}]}]
    assert (
        run(
            issues=issues,
            api_key="k",
            token="t",
            create=lambda *a, **k: created.append(a) or {"html_url": "x"},
            suggest=lambda *_: ("t", "b"),
            pyproject_text="x",
        )
        == 0
    )
    assert created == []


def test_run_creates_exactly_one_issue():
    created = []

    def create(token, repo, title, body):
        created.append((title, body))
        return {"html_url": "https://example.test/1"}

    assert (
        run(
            issues=[],
            api_key="k",
            token="t",
            create=create,
            suggest=lambda *_: ("Use X", "Because Y"),
            repo="calmmage/botspot",
            pyproject_text="name='botspot'",
        )
        == 0
    )
    assert created == [("Use X", "Because Y")]
