"""P3 regression coverage for optimization metrics, templates, and A/B testing."""

from pathlib import Path

from backend.api.chat import ChatGenerateRequest
from backend.api.optimization import (
    ExperimentCreate,
    PromptEvaluationCreate,
    TemplateCreate,
    TemplateVersionCreate,
    estimate_message_cost,
    render_template_text,
)


def test_optimization_request_contracts_and_helpers():
    template = TemplateCreate(name="LinkedIn direct", channel="linkedin_dm")
    version = TemplateVersionCreate(body="Hi {{username}}, noticed {{industry}}.", cta="Compare notes")
    experiment = ExperimentCreate(
        name="CTA test",
        variants=[
            {"template_version_id": 1, "label": "A"},
            {"template_version_id": 2, "label": "B", "weight": 2},
        ],
    )
    evaluation = PromptEvaluationCreate(name="Concise prompt", prompt="Write less", score=85)
    request = ChatGenerateRequest(lead_ids=[1], ab_experiment_id=3)

    assert template.channel == "linkedin_dm"
    assert version.status == "active"
    assert experiment.goal == "reply_rate"
    assert evaluation.score == 85
    assert request.ab_experiment_id == 3

    rendered = render_template_text(
        version.body,
        {"username": "Alex"},
        {"industry": "fitness retail"},
    )
    assert rendered == "Hi Alex, noticed fitness retail."
    assert estimate_message_cost("local-chat-v1", "local", [{"body": "x"}]) == 0
    assert estimate_message_cost("qwen/qwen3-30b-a3b-instruct-2507", "openrouter", [{"body": "x" * 4000}]) > 0


def test_optimization_schema_and_routes_are_registered():
    schema = Path("database/migrations/init.sql").read_text(encoding="utf-8")
    runtime_schema = Path("backend/db.py").read_text(encoding="utf-8")
    main = Path("backend/main.py").read_text(encoding="utf-8")
    chat = Path("backend/api/chat.py").read_text(encoding="utf-8")
    frontend = Path("frontend/src/App.jsx").read_text(encoding="utf-8")

    for table in (
        "message_templates",
        "message_template_versions",
        "ab_experiments",
        "ab_variants",
        "prompt_evaluations",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
        assert f"CREATE TABLE IF NOT EXISTS {table}" in runtime_schema
    for field in (
        "template_version_id",
        "ab_experiment_id",
        "ab_variant_id",
        "estimated_cost_usd",
    ):
        assert f"marketing_messages ADD COLUMN IF NOT EXISTS {field}" in schema
    assert 'prefix="/api/optimization"' in main
    assert "apply_template_or_experiment" in chat
    assert "/api/optimization/summary?days=30" in frontend
    assert "A/B Variants" in frontend
