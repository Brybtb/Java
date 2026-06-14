"""C00 hygiene: the web layer maps client errors to 400, rejects non-finite input,
never 500s on a null profile, reports llm_active honestly, and sanitizes faults.
Tests call the pure handle_post()/adapter directly — no live server, no network."""
import json

import foo_agent.agents.llm as llm_mod
import web.app as app


def test_profile_null_does_not_500():                 # B13
    code, body, _ = app.handle_post("/api/workflow", b'{"profile":null,"as_of":"2026-06-14"}')
    assert code == 200
    assert json.loads(body)["status"] == "collecting"
    assert b"NoneType" not in body                    # old bug leaked an AttributeError


def test_nonfinite_rejected_400():                    # B11
    code, body, _ = app.handle_post("/api/workflow",
                                    b'{"profile":{"income":{"gross_annual":Infinity}}}')
    assert code == 400
    assert b"non-finite" in body


def test_bad_json_400():
    code, _, _ = app.handle_post("/api/workflow", b"{not json")
    assert code == 400


def test_invalid_enum_returns_400(profile):           # B10
    bad = dict(profile)
    bad["household"] = dict(profile["household"], filing_status="not_a_status")
    code, _, _ = app.handle_post("/api/workflow", json.dumps({"profile": bad}).encode())
    assert code == 400


def test_llm_active_false_without_llm():              # D2
    code, body, _ = app.handle_post("/api/copilot/turn", b'{"profile":{},"message":null}')
    d = json.loads(body)
    assert d.get("llm_active") is False
    assert d.get("llm_used") is False


def test_500_is_sanitized(monkeypatch):               # D3
    def boom(*a, **k):
        raise RuntimeError("SECRET internal detail")
    monkeypatch.setattr(app, "dispatch", boom)
    code, body, _ = app.handle_post("/api/workflow", b"{}")
    assert code == 500
    assert b"SECRET" not in body
    assert b"internal error" in body


def test_llm_uses_api_key_header_not_bearer(monkeypatch):   # D1b
    seen = []

    class _Resp:
        status_code = 200
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"final": "ok"}'}]}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.append(headers or {})
        return _Resp()

    monkeypatch.setattr(llm_mod.requests, "post", fake_post)
    call = llm_mod.make_gemini(api_key="AQ.test-key", model="gemini-2.5-flash")
    assert call("hi")                                 # returns the model text
    assert seen and all("x-goog-api-key" in h for h in seen)
    assert not any("Authorization" in h for h in seen)
