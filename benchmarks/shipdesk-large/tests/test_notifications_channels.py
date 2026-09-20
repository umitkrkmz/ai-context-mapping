import json

from shipdesk.notifications import email_templates, push_templates, sms_templates, webhook_payloads


def test_email_mentions_free_shipping():
    assert "Shipping is free" in email_templates.order_confirmation("A1", 5000, True)
    assert "free" not in email_templates.order_confirmation("A1", 5000, False).lower()


def test_sms_truncates_long_messages():
    assert len(sms_templates.shipped("X" * 400)) == 160


def test_push_refund_payload():
    assert push_templates.refund("A1", 250)["body"] == "A1: 2.50"


def test_webhook_payload_is_sorted_json():
    payload = webhook_payloads.order_event("shipped", "A1", 100)
    assert json.loads(payload)["event"] == "shipped"
    assert payload.index("event") < payload.index("order_id")
