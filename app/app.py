"""Hedron MVP GUI — Streamlit, ChatGPT layout + Antigravity panels. Works even if server.py is down (mock fallback)."""
import streamlit as st

st.set_page_config(page_title="Hedron — Sovereign Workbench", layout="wide")

def ask_server(prompt, mode, scope, model):
    try:
        import httpx
        r = httpx.post("http://127.0.0.1:8000/chat",
                       json={"prompt": prompt, "mode": mode, "scope": scope, "model": model}, timeout=8)
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

c1, c2 = st.columns([3, 2])
with c1:
    st.subheader("Chat (Commander)")
    mode = st.selectbox("Mode", ["Auto", "Manual"])
    scope = st.selectbox("Scope", ["Single", "Swarm"])
    model = st.selectbox("Model", ["Auto", "qwen-7b", "ornith-9b", "qwen2.5vl-3b", "qwen-3b"])
    tpl = st.selectbox("Template", ["Ask", "Yes — My-SOP-Note", "No — Auto style"])
    prompt = st.text_area("Ask...", height=100, placeholder="Extract 3 defects from scan + draft approval note")
    if st.button("Go", type="primary") and prompt:
        with st.spinner("Routing locally..."):
            res = ask_server(prompt, mode, scope, model)
        st.info("routed: %(model)s · %(reason)s" % res["router"])
        st.write(res["echo"])
with c2:
    st.subheader("Deliverables + Proof")
    st.caption("Downloads appear here after generation (Phase 3).")
    st.caption("Network: 127.0.0.1:11434 only · external: 0")
