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


# --- C02: DoS / limits / clamps ----------------------------------------------
def test_oversize_post_returns_413():                       # B9
    import http.client
    import threading
    from http.server import ThreadingHTTPServer

    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.putrequest("POST", "/api/workflow")
        conn.putheader("Content-Length", str(app._MAX_CONTENT + 1))   # oversize, body not sent
        conn.putheader("Content-Type", "application/json")
        conn.endheaders()
        assert conn.getresponse().status == 413
    finally:
        srv.shutdown()


def test_handler_has_socket_timeout():                      # B9: anti-slowloris
    assert isinstance(app.Handler.timeout, (int, float)) and app.Handler.timeout > 0


def test_deferral_pct_is_clamped():                         # B12
    from datetime import date

    from foo_agent.calculators.context import CalcContext
    from foo_agent.calculators.contributions import _deferral_pct
    over = CalcContext(profile={"contributions": {"employer_401k": {"pct": 5.0}}}, params={}, as_of=date(2026, 6, 14))
    neg = CalcContext(profile={"contributions": {"employer_401k": {"pct": -2}}}, params={}, as_of=date(2026, 6, 14))
    assert float(_deferral_pct(over)) == 1.0       # > 100% of pay -> clamped to 1
    assert float(_deferral_pct(neg)) == 0.0        # negative -> clamped to 0


def test_copilot_rejects_invalid_choice():                  # B15
    from foo_agent.agents.copilot import start, turn
    state = start(profile={}, as_of="2026-06-14")
    res = turn(state, "<script>alert(1)</script>", as_of="2026-06-14")   # answering filing_status
    assert res["status"] == "collecting"
    # the malicious free text was NOT stored as the filing_status enum
    assert (res["state"]["profile"].get("household") or {}).get("filing_status") is None
    assert res["next_question"]["field"] == "household.filing_status"


def test_pdf_render_is_lock_serialized():                   # B17
    from foo_agent.report import pdf
    import threading as _t
    assert isinstance(pdf._PDF_EPOCH_LOCK, type(_t.Lock()))


# --- C12: the balance-sheet/liabilities intake feeds a sane plan -------------
def _guided_base():
    # what the guided Q&A collects BEFORE the C12 balance-sheet step
    return {"schema_version": "1.0.0", "as_of": AS_OF,
            "household": {"filing_status": "single", "state": "TX", "primary_age": 35},
            "income": {"gross_annual": 120000}, "expenses": {"monthly_essential": 4000},
            "accounts": {"cash_emergency": {"balance": 20000},
                         "employer_401k": {"match_offered": False}, "hsa": {"eligible": False}}}


def test_balances_lift_funded_ratio_out_of_the_floor():
    from foo_agent.workflow.orchestrator import run
    import copy
    without = run(copy.deepcopy(_guided_base()), AS_OF, trials=300)
    withp = copy.deepcopy(_guided_base())
    withp["accounts"]["taxable"] = {"balance": 50000}
    withp["accounts"]["employer_401k"]["balance"] = 100000
    withp["accounts"]["roth_ira"] = {"balance": 30000}
    withb = run(withp, AS_OF, trials=300)
    assert without["status"] == "ready" and withb["status"] == "ready"
    fr0 = float(without["projection"]["funded_ratio"])
    fr1 = float(withb["projection"]["funded_ratio"])
    assert fr1 > fr0 * 2          # real balances move the needle out of the ~0 floor
    # and the buckets reflect the collected accounts (C07 routing)
    assert float(withb["projection"]["buckets"]["taxable"]) > 0


def test_collected_high_interest_debt_fires_foo_rule():
    from foo_agent.workflow.orchestrator import run
    p = _guided_base()
    p["accounts"]["taxable"] = {"balance": 50000}
    p["debts"] = [{"id": "credit_card", "type": "credit_card", "balance": 9000, "apr": 0.2299}]
    r = run(p, AS_OF, trials=300)
    rule_ids = {rec["rule_id"] for rec in r["recommendations"]}
    assert "foo.debt.high_interest" in rule_ids       # the collected debt drives the FOO step


def test_bad_apr_from_intake_is_rejected_400():
    # the UI converts % -> fraction (<=2); a raw out-of-range apr must fail closed, not slip through
    bad = _guided_base()
    bad["debts"] = [{"id": "x", "type": "credit_card", "balance": 9000, "apr": 22.99}]  # should be 0.2299
    code, _, _ = app.handle_post("/api/workflow", json.dumps({"profile": bad}).encode())
    assert code == 400
