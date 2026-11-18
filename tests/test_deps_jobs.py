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
