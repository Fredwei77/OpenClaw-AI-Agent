"""Local API smoke test for the webhook automation MVP.

Run with the backend available at http://127.0.0.1:8000.
"""

import json
import time
import uuid
from urllib import error, parse, request


BASE_URL = "http://127.0.0.1:8000"


def api(path, method="GET", body=None, token=None, form=False):
    headers = {}
    data = None
    if body is not None:
        if form:
            data = parse.urlencode(body).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=15) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except error.HTTPError as exc:
        raise RuntimeError(f"{method} {path}: {exc.code} {exc.read().decode()}") from exc


def main():
    suffix = uuid.uuid4().hex[:10]
    email = f"automation-{suffix}@example.com"
    password = "test-password-123"
    api(
        "/api/auth/register",
        "POST",
        {"email": email, "password": password, "role": "user"},
    )
    token = api(
        "/api/auth/login",
        "POST",
        {"username": email, "password": password},
        form=True,
    )["access_token"]

    flow = api("/api/automations/templates/welcome", "POST", token=token)
    ai_flow = api("/api/automations/templates/ai-qualification", "POST", token=token)
    delayed_flow = api(
        "/api/automations/",
        "POST",
        {
            "name": "Delayed follow-up smoke test",
            "trigger_type": "inbound_message",
            "trigger_config": {
                "channel": "webhook",
                "keywords": ["delay-smoke"],
                "keyword_match": "any",
            },
            "definition": {
                "steps": [
                    {"type": "delay", "config": {"seconds": 1}},
                    {
                        "type": "send_message",
                        "config": {"content": "Delayed follow-up for {{contact.name}}"},
                    },
                    {"type": "add_tag", "config": {"tag": "delayed-follow-up"}},
                    {"type": "end", "config": {}},
                ]
            },
            "status": "active",
        },
        token=token,
    )
    event_payload = {
        "event_id": f"smoke-{suffix}",
        "event_type": "inbound_message",
        "channel": "webhook",
        "contact": {
            "external_id": f"buyer-{suffix}",
            "name": "Smoke Buyer",
            "email": f"buyer-{suffix}@example.com",
            "tags": ["smoke-test"],
        },
        "message": {
            "content": "delay-smoke: Please send enterprise pricing and a demo today. I need a human sales representative."
        },
        "metadata": {"source": "automation_smoke"},
    }
    event = api(
        "/api/webhooks/simulate",
        "POST",
        event_payload,
        token=token,
    )
    duplicate = api(
        "/api/webhooks/simulate",
        "POST",
        event_payload,
        token=token,
    )
    deadline = time.time() + 10
    runs = []
    while time.time() < deadline:
        runs = api("/api/automations/runs/recent?limit=10", token=token)
        delayed_run = next(
            (item for item in runs if item["flow_id"] == delayed_flow["id"]),
            None,
        )
        if delayed_run and delayed_run["status"] == "completed":
            break
        time.sleep(0.5)
    conversations = api("/api/conversations/?limit=10", token=token)
    messages = api(
        f"/api/conversations/{event['conversation_id']}/messages",
        token=token,
    )
    lead = api(f"/api/leads/{event['lead_id']}", token=token)
    delayed_run = next(item for item in runs if item["flow_id"] == delayed_flow["id"])
    run_detail = api(f"/api/automations/runs/{delayed_run['id']}", token=token)
    analytics = api("/api/automations/analytics?days=30", token=token)

    assert len(event["run_ids"]) == 3, event
    assert duplicate["duplicate"] is True
    assert duplicate["run_ids"] == []
    assert any(item["flow_id"] == flow["id"] and item["status"] == "completed" for item in runs)
    assert any(item["flow_id"] == ai_flow["id"] and item["status"] == "completed" for item in runs)
    assert any(item["flow_id"] == delayed_flow["id"] and item["status"] == "suppressed" for item in runs)
    assert conversations and conversations[0]["id"] == event["conversation_id"]
    conversation = conversations[0]
    assert conversation["mode"] == "human"
    assert conversation["intent"] in {"purchase", "pricing", "demo"}
    assert conversation["quality_score"] >= 50
    assert [item["direction"] for item in messages] == ["inbound", "outbound", "outbound"]
    assert lead["status"] == "qualified"
    assert "webhook-inbound" in lead["tags"]
    assert "ai-qualified" in lead["tags"]
    assert any(step["step_type"] == "human_guard" for step in run_detail["steps"])
    assert analytics["summary"]["total_runs"] >= 3
    assert analytics["summary"]["human_handoffs"] >= 1

    blocked_event = api(
        "/api/webhooks/simulate",
        "POST",
        {
            **event_payload,
            "event_id": f"blocked-{suffix}",
            "message": {"content": "This message arrives while a human owns the conversation."},
        },
        token=token,
    )
    assert blocked_event["run_ids"] == []

    takeover = api(
        f"/api/conversations/{event['conversation_id']}/takeover",
        "POST",
        {"reason": "Smoke test human ownership."},
        token=token,
    )
    assert takeover["mode"] == "human"
    manual = api(
        f"/api/conversations/{event['conversation_id']}/messages",
        "POST",
        {"content": "A human representative is following up now."},
        token=token,
    )
    assert manual["metadata"]["source"] == "human"
    released = api(
        f"/api/conversations/{event['conversation_id']}/release",
        "POST",
        token=token,
    )
    assert released["mode"] == "automation"

    resumed_event = api(
        "/api/webhooks/simulate",
        "POST",
        {
            **event_payload,
            "event_id": f"resumed-{suffix}",
            "message": {"content": "delay-smoke: Thanks, please continue with the details."},
        },
        token=token,
    )
    assert len(resumed_event["run_ids"]) == 3
    resumed_deadline = time.time() + 10
    resumed_messages = []
    final_lead = lead
    while time.time() < resumed_deadline:
        resumed_messages = api(
            f"/api/conversations/{event['conversation_id']}/messages",
            token=token,
        )
        final_lead = api(f"/api/leads/{event['lead_id']}", token=token)
        if (
            any(item["content"].startswith("Delayed follow-up") for item in resumed_messages)
            and "delayed-follow-up" in final_lead["tags"]
        ):
            break
        time.sleep(0.5)
    assert any(item["content"].startswith("Delayed follow-up") for item in resumed_messages)
    assert "delayed-follow-up" in final_lead["tags"]
    events = api(
        f"/api/conversations/{event['conversation_id']}/events",
        token=token,
    )
    event_types = {item["event_type"] for item in events}
    assert {"handoff_requested", "human_takeover", "manual_reply_sent", "automation_resumed"} <= event_types

    print(
        json.dumps(
            {
                "flow_id": flow["id"],
                "ai_flow_id": ai_flow["id"],
                "delayed_flow_id": delayed_flow["id"],
                "run_ids": event["run_ids"],
                "duplicate_suppressed": duplicate["duplicate"],
                "human_mode_blocked_runs": blocked_event["run_ids"],
                "resumed_run_ids": resumed_event["run_ids"],
                "conversation_id": event["conversation_id"],
                "lead_id": event["lead_id"],
                "lead_status": lead["status"],
                "lead_score": conversation["quality_score"],
                "intent": conversation["intent"],
                "lead_tags": final_lead["tags"],
                "message_directions": [item["direction"] for item in messages],
                "audit_events": sorted(event_types),
                "analytics": analytics["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
