"""SMTP transport configuration regression tests."""

from agents.email_agent.email_agent import EmailAgent


def test_email_agent_supports_implicit_tls(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.163.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USE_SSL", "true")
    monkeypatch.setenv("FROM_NAME", "Fred Wei")
    agent = EmailAgent()
    assert agent.smtp_host == "smtp.163.com"
    assert agent.smtp_port == 465
    assert agent.smtp_use_ssl is True
    assert agent.from_name == "Fred Wei"


def test_email_agent_defaults_to_starttls(monkeypatch):
    monkeypatch.setenv("SMTP_USE_SSL", "false")
    agent = EmailAgent()
    assert agent.smtp_use_ssl is False
