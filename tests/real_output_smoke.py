"""End-to-end smoke test for automatic AI output and signed webhook delivery."""

import hashlib
import hmac
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, parse, request


BASE_URL = "http://127.0.0.1:8000"
CALLBACK_SECRET = "real-output-smoke-secret"
received = []


class CallbackHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        timestamp = self.headers.get("X-OpenClaw-Timestamp", "")
        signature = self.headers.get("X-OpenClaw-Signature", "")
        expected = hmac.new(
            CALLBACK_SECRET.encode(),
            timestamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        received.append(
            {
                "payload": json.loads(body),
                "signature_valid": signature == f"sha256={expected}",
                "idempotency_key": self.headers.get("Idempotency-Key"),
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"accepted":true}')

    def log_message(self, *_args):
        return


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
        with request.urlopen(req, timeout=20) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except error.HTTPError as exc:
        raise RuntimeError(f"{method} {path}: {exc.code} {exc.read().decode()}") from exc


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    callback_url = f"http://127.0.0.1:{server.server_port}/callback"

    try:
        suffix = uuid.uuid4().hex[:10]
        email = f"real-output-{suffix}@example.com"
        password = "test-password-123"
        api("/api/auth/register", "POST", {"email": email, "password": password, "role": "user"})
        token = api(
            "/api/auth/login",
            "POST",
            {"username": email, "password": password},
            form=True,
        )["access_token"]

        settings = api(
            "/api/automations/settings",
            "PUT",
            {
                "ai_provider": "local",
                "ai_model": "",
                "reply_mode": "automatic",
                "min_confidence": 0,
                "handoff_score": 100,
                "max_auto_replies_per_hour": 5,
                "blocked_terms": [],
                "outbound_webhook_enabled": True,
                "outbound_webhook_url": callback_url,
                "outbound_webhook_secret": CALLBACK_SECRET,
            },
            token=token,
        )
        assert settings["reply_mode"] == "automatic"
        assert settings["webhook_secret_configured"] is True

        flow = api("/api/automations/templates/ai-qualification", "POST", token=token)
        event = api(
            "/api/webhooks/simulate",
            "POST",
            {
                "event_id": f"real-output-{suffix}",
                "event_type": "inbound_message",
                "channel": "webhook",
                "contact": {
                    "external_id": f"buyer-{suffix}",
                    "name": "Output Buyer",
                    "email": f"buyer-{suffix}@example.com",
                    "tags": [],
                },
                "message": {"content": "Hello, can you tell me more about the product?"},
                "metadata": {"source": "real_output_smoke"},
            },
            token=token,
        )
        assert len(event["run_ids"]) == 1

        deadline = time.time() + 15
        deliveries = []
        while time.time() < deadline:
            deliveries = api("/api/automations/deliveries/recent?limit=10", token=token)
            if deliveries and deliveries[0]["status"] == "delivered" and received:
                break
            time.sleep(0.5)

        messages = api(f"/api/conversations/{event['conversation_id']}/messages", token=token)
        calls = api("/api/automations/ai-calls/recent?limit=10", token=token)

        assert deliveries and deliveries[0]["status"] == "delivered", deliveries
        assert received and received[0]["signature_valid"] is True
        assert received[0]["idempotency_key"].startswith("message-")
        assert received[0]["payload"]["event"] == "automation.message.created"
        assert received[0]["payload"]["content"]
        assert [item["status"] for item in messages] == ["received", "sent"]
        assert calls and calls[0]["provider"] == "local"
        assert calls[0]["status"] == "completed"

        print(
            json.dumps(
                {
                    "flow_id": flow["id"],
                    "run_ids": event["run_ids"],
                    "message_statuses": [item["status"] for item in messages],
                    "delivery_status": deliveries[0]["status"],
                    "delivery_attempts": deliveries[0]["attempts"],
                    "signature_valid": received[0]["signature_valid"],
                    "idempotency_key": received[0]["idempotency_key"],
                    "ai_provider": calls[0]["provider"],
                    "intent": calls[0]["output"]["intent"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
