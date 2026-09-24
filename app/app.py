"""Hedron MVP GUI — Streamlit, ChatGPT layout + Antigravity panels. Works even if server.py is down (mock fallback)."""
import streamlit as st

st.set_page_config(page_title="Hedron — Sovereign Workbench", layout="wide")

# ── Session-state defaults ────────────────────────────────────────────
if "routed_model" not in st.session_state:
    st.session_state.routed_model = "qwen-7b"
if "routed_reason" not in st.session_state:
    st.session_state.routed_reason = "doc/summary default"
if "last_model_picker" not in st.session_state:
    st.session_state.last_model_picker = "Auto"
if "template" not in st.session_state:
    st.session_state.template = "Ask"

def ask_server(prompt, mode, scope, model, template):
    try:
        import httpx
        r = httpx.post("http://127.0.0.1:8000/chat",
                       json={"prompt": prompt, "mode": mode, "scope": scope, "model": model,
                             "template": template}, timeout=8)
        return r.json()
    except Exception:
        p = prompt.lower()
        m = "ornith-9b" if any(k in p for k in ("code", "calc", "fix")) else ("qwen2.5vl-3b" if any(k in p for k in ("scan", "photo", "image")) else "qwen-7b")
        return {"echo": prompt, "router": {"model": m, "reason": "local fallback"}, "mode": mode, "scope": scope}

with st.sidebar:
    st.title("Hedron")
    st.caption("Sovereign workbench · 100% local")
    st.divider()
    st.write("Vault pins")
    st.write("Templates")
    st.success("Proof: ● Local · 0 external")

    # ── Template store (persisted across reruns) ────────────────────────
    tpl = st.selectbox("Template", ["Ask", "Yes — My-SOP-Note", "No — Auto style"],
                       index=["Ask", "Yes — My-SOP-Note", "No — Auto style"].index(st.session_state.template))
    st.session_state.template = tpl

c1, c2 = st.columns([3, 2])
with c1:
    st.subheader("Chat (Commander)")
    mode = st.selectbox("Mode", ["Auto", "Manual"], index=["Auto", "Manual"].index(st.session_state.get("mode_selector","Auto")))
    st.session_state.mode_selector = mode
    scope = st.selectbox("Scope", ["Auto", "Single", "Swarm"],
                         index=["Auto", "Single", "Swarm"].index(st.session_state.get("scope_selector","Auto")))
    st.session_state.scope_selector = scope
    model = st.selectbox("Model", ["Auto", "qwen-7b", "ornith-9b", "qwen2.5vl-3b", "qwen-3b"],
                         index=["Auto", "qwen-7b", "ornith-9b", "qwen2.5vl-3b", "qwen-3b"].index(st.session_state.get("model_selector","Auto")))
    st.session_state.model_selector = model
    prompt = st.text_area("Ask...", height=100, placeholder="Extract 3 defects from scan + draft approval note")
    if st.button("Go", type="primary") and prompt:
        with st.spinner("Routing locally..."):
            res = ask_server(prompt, mode, scope, model, st.session_state.template)
        # ── extract router from first node (Single) or node[0] (Swarm) ────
        if res.get("nodes") and len(res["nodes"]) > 0:
            first = res["nodes"][0]
            routed_m = first.get("router", {}).get("model", res.get("scope", "?"))
            routed_r = first.get("router", {}).get("reason", "?")
        else:
            fb = res.get("router", {})
            routed_m = fb.get("model", "qwen-7b")
            routed_r = fb.get("reason", "local fallback")
        # ── model-switch toast ────────────────────────────────────────
        if routed_m != st.session_state.last_model_picker:
            st.toast(f"model switched → {routed_m} ({routed_r})", icon="🧠")
        st.session_state.last_model_picker = routed_m
        st.info("routed: %(model)s · %(reason)s" % {"model": routed_m, "reason": routed_r})
        for n in res.get("nodes", [])[:1]:
            st.write(n.get("answer", ""))
            if n.get("cites"):
                st.caption("cites: " + " ".join(n["cites"]))
        st.write(res.get("echo", ""))
        # ── Swarm extra nodes (optional) ──────────────────────────────
        if res.get("scope") == "Swarm" and len(res.get("nodes", [])) > 1:
            with st.expander("Swarm nodes"):
                for n in res["nodes"][1:]:
                    st.caption(f"→ {n['router']['model']}: {n['answer'][:80].replace(chr(10),' ')}")
        else:
            st.write(res.get("echo", ""))
with c2:
    st.subheader("Deliverables + Proof")
    try:
        import httpx as _hx
        _p = _hx.get("http://127.0.0.1:8000/proof", timeout=3).json()
        st.metric("External calls", _p.get("external_calls", 0))
        st.caption("audit events: %(audit_events)s · chain %(chain_ok)s" % {
            "audit_events": _p.get("audit_events", "?"), "chain_ok": "ok" if _p.get("chain_ok") else "?"})
    except Exception:
        st.caption("backend offline — proof unavailable")
    st.caption("Downloads appear here after generation (Phase 3).")
    st.caption("Network: 127.0.0.1:11434 only · external: 0")
    st.caption(f"routed: {st.session_state.routed_model} · {st.session_state.routed_reason}")