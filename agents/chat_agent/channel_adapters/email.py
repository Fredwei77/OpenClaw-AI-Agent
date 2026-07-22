from __future__ import annotations

from agents.email_agent.email_agent import EmailAgent


class EmailChannelAdapter:
    name = "email"

    async def send(self, lead: dict, message: dict, idempotency_key: str) -> dict:
        email = str(lead.get("email") or "").strip()
        if not email:
            raise ValueError("Lead does not have an email address")
        agent = EmailAgent()
        result = await agent.send_single_email(
            to_email=email,
            to_name=str(lead.get("username") or ""),
            subject=str(message.get("subject") or ""),
            body_html=str(message.get("body") or "").replace("\n", "<br>"),
        )
        if not result.success:
            raise RuntimeError(result.error or "SMTP delivery failed")
        return {
            "provider": "smtp",
            "provider_message_id": result.message_id or idempotency_key,
        }
