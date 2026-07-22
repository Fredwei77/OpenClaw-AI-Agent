"""JSONB response normalization for Chat Agent draft fields."""

from datetime import datetime

from backend.api.leads import _to_marketing_message


def test_lead_detail_decodes_json_string_fields():
    message = _to_marketing_message(
        {
            "id": 1,
            "channel": "linkedin_dm",
            "subject": "",
            "body": "Hello",
            "cta": "",
            "sequence_step": 1,
            "status": "approved",
            "personalization_evidence": '["profile signal"]',
            "quality_score": 90,
            "risk_flags": "[]",
            "generation_provider": "local",
            "generation_model": "local-chat-v1",
            "approved_at": None,
            "sent_at": None,
            "provider": None,
            "attempts": 0,
            "last_error": None,
            "delivery_task_id": None,
            "created_at": datetime.now(),
        }
    )
    assert message.personalization_evidence == ["profile signal"]
    assert message.risk_flags == []
