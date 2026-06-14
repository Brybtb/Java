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


# --- C05: bracket-aware intake endpoint (NOTE-1) -----------------------------
AS_OF = "2026-06-14"


def test_intake_brackets_single_bands_are_gross_and_dated():
    out = app._intake_brackets("single", AS_OF)
    assert out["filing_status"] == "single"
    assert out["as_of"] == AS_OF
    assert out["standard_deduction"] == 16100             # TY2026 single std deduction
    bands = out["bands"]
    assert bands[0]["lower"] == 0                          # first band always starts at $0 gross
    # taxable threshold 12400 -> gross 12400 + 16100 std deduction (bracket-aware shift)
    assert bands[0]["upper"] == 28500
    assert bands[0]["rate"] == 0.10
    assert bands[0]["value"] == 14250                      # representative midpoint for the pill
    assert bands[-1]["upper"] is None                      # top bracket is open-ended
    assert bands[-1]["rate"] == 0.37
    assert "+" in bands[-1]["label"]


def test_intake_brackets_rates_match_engine_params():
    from datetime import date
    from foo_agent.rules.loader import load_params
    params = load_params(date(2026, 6, 14), "TX")["tax"]
    for fs in ("single", "married_filing_jointly", "head_of_household"):
        out = app._intake_brackets(fs, AS_OF)
        assert [b["rate"] for b in out["bands"]] == [b["rate"] for b in params["brackets"][fs]]
        assert out["standard_deduction"] == params["standard_deduction"][fs]


def test_intake_brackets_filing_status_changes_bands():
    single = app._intake_brackets("single", AS_OF)
    mfj = app._intake_brackets("married_filing_jointly", AS_OF)
    # MFJ has a larger standard deduction, so the first gross band ends higher.
    assert mfj["standard_deduction"] > single["standard_deduction"]
    assert mfj["bands"][0]["upper"] != single["bands"][0]["upper"]


def test_intake_brackets_endpoint_200():
    code, body, ctype = app.handle_get("/api/intake/brackets", "filing_status=single&as_of=" + AS_OF)
    assert code == 200
    assert ctype == "application/json"
    assert json.loads(body)["bands"]


def test_intake_brackets_bad_filing_status_400():
    code, body, _ = app.handle_get("/api/intake/brackets", "filing_status=not_a_status")
    assert code == 400
    assert b"filing_status" in body


def test_intake_brackets_missing_filing_status_400():
    code, body, _ = app.handle_get("/api/intake/brackets", "")
    assert code == 400


def test_intake_brackets_unknown_path_404():
    code, _, _ = app.handle_get("/api/nope", "")
    assert code == 404
