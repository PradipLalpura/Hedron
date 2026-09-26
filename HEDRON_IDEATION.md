# HEDRON — Sovereign Agentic AI Workbench
## Confidential · Local-first · Cloud-capable · Cost-efficient

**Tagline:** Every confidential job. Done on your machine. Real files. Zero egress.
**One line:** Hedron is not a local chatbot — it is a provable AI workbench: every answer cited or refused, every action audited, runnable air-gapped or in a confidential cloud, at zero per-query cost.
**Scope:** SIH 26117 (MRPL) — near-production on one workstation, December. Full Edge vision below; Workstation/Server tiers are architecture, not builds.

---

## 1. Problem

Refineries, PSUs, defence-linked manufacturing and government offices generate routine but sensitive knowledge work: approval notes, board presentations, engineering calculations, internal-tool code, scanned drawings and inspection reports. None of this can go through cloud AI assistants — the data (P&IDs, financials, vendor negotiations, unreleased designs, correspondence, strategy) is confidential and policy keeps it on premises. So people either do the work manually, or quietly paste confidential material into public tools anyway. Open-weight models are now good enough for a genuinely useful assistant. Nothing deployable exists that industrial users can work with the way they use Claude or Codex. Hedron is that workbench.

## 2. Confidential core (non-negotiable)

- **Air-gap proof, not promise:** live `external: 0` counter, localhost-only map, cable-pull demo. Proof endpoint reports calls, audit events, chain status.
- **Audit chain:** every chat, upload and artifact appends a hash-linked event (GENESIS root, prev→hash). Tamper-evident; RTI/compliance-ready. Verify on demand.
- **Session isolation:** each chat is a fresh session — own bounded memory (last turns, capped chars), own file registry. One chat's uploads never ground another's answers. New chat = zero history, zero files.
- **Exact-name grounding:** file content is used only when attached this turn or named exactly in the prompt. Built-in SOPs are shared knowledge; uploads are per-chat private.
- **Honest by architecture:** factual claims carry `[doc p.X]` cites or the system says `not in SOP` to your face. Measured hallucination rate on vault questions: ~0.
- **Jailed execution:** code runs with no sockets, 5s timeout, byte caps. Broken refs and external links fail the release gate.
- **No-egress stack:** Ollama + local RAG + Tesseract + Office writers, all on localhost. No accounts, no keys, no telemetry.

## 3. Hedron features (proven in MVP, frozen)

- **Router with reasons:** per-subtask model pick across code (Ornith-9B), docs (Qwen-7B), vision (Qwen-VL), fallback (Qwen-3B). Every pick shows `model · reason`; mid-work switches toast. Manual pin respected.
- **Single / Swarm:** score classifier (<30 Single, >70 or 5+ files Swarm); forced Swarm fans out to research (cites) + build (deliverable) — two models, not one twice.
- **Vault RAG:** chunk-by-heading → nomic-embed → Chroma, FTS fallback, keyword-overlap gate so vectors can't hallucinate neighbors. Unknown questions return `not in SOP`.
- **Multimodal:** real pixels to the VL model (preprocessed, resized) + Tesseract OCR text as Vault chunks and vision context. Scans, photos, drawings, P&IDs.
- **Chat-to-file:** "give it as docx/pdf/pptx/xlsx" builds jury-ready files from the answer — markdown stripped, titles cut at word boundaries, xlsx formulas live. Native save dialog; path-traversal blocked.
- **Sessions UI:** new chat, switcher with titles + turn counts, per-chat threads, memory badge.
- **Resilience:** LRU model unload (2-resident cap), OOM unload-and-retry, offline disk cache (`[cached]` fallback), `HEDRON_FORCE_CPU` CPU-only mode, 256-token Swarm cap, 4K context on 6GB VRAM.
- **Desktop shell:** native window (pywebview) over a single offline HTML file; dark mission-control + light document themes with toggle. Streamlit kept as fallback.
- **Templates:** Ask / Yes→My-SOP-Note (forces cite-or-refuse format) / No→auto.

## 4. Cloud + local: hybrid doctrine (the cloud objection, absorbed)

The same binary runs in two postures with an identical proof layer:
- **Field / office (air-gapped):** laptop or dept workstation, zero egress, offline cache. This is the SIH demo.
- **HQ confidential cloud:** TEE confidential VMs (AMD SEV-SNP / Intel TDX class) for central deployment; Vault sync moves as **signed packs** (`.hpack`: chunks + Merkle root, signature-verified on import) — updates travel without trust, models never leave the enclave boundary.
- Compliance holds in both because the proof (`0 external`, audit chain, cite-or-refuse) is architectural, not environmental. "We want cloud" becomes a deployment option, not a rejection.

## 5. Advanced extras (new for Edge)

- **Cost meter:** per-answer tokens, VRAM resident, `cost: ₹0.00`. TCO slide: 500-seat SaaS AI ≈ ₹1.5Cr/yr vs Hedron's one-time commodity hardware + ₹0 inference.
- **Freshness:** every cite carries ingested-at ("updated 2 min ago"); the 30-second update race (upload circular → ask → new cite) is a demo beat. Hedron is never retrained, only re-grounded.
- **Agent runs:** one button chains upload → OCR → extract → draft → download with visible plan steps (`POST /agent/run`, step events).
- **Code-in-chat:** code blocks execute in the jail; verdict + stdout render inline.
- **Model fleet tiers:** E (this laptop) → W (dept server, 14B/32B, parallel Swarm) → S (central, 70B+, vLLM). Drop-in GGUF policy: new weights, no redesign. UI models registry.
- **Template vault:** `.htemplate` packs (MRPL presets default), Yes→which/Upload/No→auto with memory.
- **Multilingual floor use:** Hindi/Hinglish prompts routed like English; Tesseract `hin+eng` OCR.
- **Anti-slop gates:** no invented metrics, placeholders as grey "to confirm", 2-font5169 cap, overflow/recalc/contrast checks before any file ships.

## 6. December Edge scope (demo vs slide)

- **Demo live:** cited answers, `not in SOP`, vision toast, agent run, code verdict, chat-to-file downloads, cable-pull proof, update race, cost meter.
- **Architecture slides only:** W/S tiers, confidential-VM posture, fleet roadmap, voice (offline Whisper) as future.
- **Freeze rule:** code locks end-November at a named commit. December is rehearsal only.

## Appendix A — Laptop setup runbook

1. Install (once, with internet): Python 3.12+ (ADD TO PATH), Ollama, Tesseract 5.4 (UB-Mannheim).
2. `git clone https://github.com/PradipLalpura/Hedron.git` + `pip install -r app\requirements.txt`.
3. Models — pendrive copy of `%USERPROFILE%\.ollama\models` (~16GB), or `ollama pull qwen2.5:7b qwen2.5:3b qwen2.5vl:3b nomic-embed-text hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M`.
4. Daily: `ollama serve` → `ollama run qwen2.5:7b hi` (pre-warm) → `python app\server.py` → `python app\desktop.py` (or double-click `start.bat`).
5. Trouble: `[mock:]` = Ollama down; backend offline banner = server down; OOM = `set HEDRON_FORCE_CPU=1`.
6. Vault ships with 2 demo SOPs + scan + valve photo; personal uploads stay in `app\sops\` (local only, never pushed).

## Appendix B — 7-minute demo script

M1 (30s): leak story — "this P&ID would be pasted into a public chatbot today." M2 (1 min): cited torque answer with `[SOP-PUMP-01 p.2]`. M3 (30s): unknown Q → `not in SOP`. M4 (1 min): scan photo → vision toast → "give it as docx" → download opens. M5 (1 min): agent run end-to-end (scan → findings → approval note). M6 (30s): **pull the LAN cable, repeat M2.** M7 (1 min): cost meter ₹0.00 + audit chain + TCO line. Q/A armor: confidentiality (air-gap + audit), updates (30-sec race), cost (TCO), scale (tiers), cloud (hybrid TEE option).
