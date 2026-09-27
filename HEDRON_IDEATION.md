# HEDRON — Provable Agentic AI for Confidential Industry
## Production ideation + PRD + architecture (SIH 26117 · MRPL)

**One line:** The AI workbench for industry that cannot use the cloud — every answer cited or refused, every action audited, deployable air-gapped or in confidential cloud, at zero per-query cost.
**Status:** Production design. Edge deployment proven on a workstation; Workstation/Server tiers specified here.

---

## PART A — IDEATION

### 1. Problem (MRPL's words, taken seriously)

Refineries, PSUs, defence-linked manufacturing and government offices produce high volumes of sensitive knowledge work: approval notes, board decks, engineering calculations, internal-tool code, scanned drawings, inspection reports. Company policy keeps this data on premises, so teams either do the work manually — losing thousands of engineer-hours — or quietly paste confidential material (P&IDs, financials, vendor terms, unreleased designs, correspondence, strategy) into public AI tools, creating unmeasured breach exposure. Open-weight models are now capable enough for a genuinely useful assistant. Nothing deployable exists that industrial users can work with the way they use Claude or Codex. That gap is the product.

### 2. Why existing answers fail

- **Public AI assistants:** disqualified by confidentiality. Data leaves the premises by design.
- **Private cloud AI (GPU VMs, SaaS):** recurring per-token/per-seat cost that scales against the organization; still requires trusting a third party with plaintext-adjacent data; needs connectivity field sites don't have.
- **DIY local models:** raw chatbots with no grounding (hallucinate procedures), no audit (useless for compliance), no tools (can't produce files), no routing (one giant model for every job = slow, VRAM-hungry, expensive hardware).
- **Hedron's position:** not "local ChatGPT" — a *provable workbench*. The differentiator is proof, not place: cited-or-refused answers, hash-chained audit, visible zero-egress, governed file outputs.

### 3. Product principles

1. **Provable over plausible.** No factual claim without a `[doc p.X]` cite or tool output. Unknown → `not in SOP`, stated plainly.
2. **Confidential by construction.** Air-gap capable; confidential-cloud capable; never both required. Proof layer identical in both.
3. **Right brain per job.** A router picks the model per subtask and shows its reason. Small models for small jobs is a cost strategy, not a compromise.
4. **Files, not chat replies.** Approval notes, decks, sheets, code, PDFs are the output. Chat is the interface.
5. **Updates without retraining.** New circulars become cited knowledge in seconds via Vault ingest. Models are never retrained for knowledge.
6. **Auditable by default.** Every prompt, route, cite, file and verdict is hash-chained. Compliance (RTI, ISO, internal vigilance) reads the log, not a dashboard claim.

### 4. Users

| Persona | Uses | Needs |
|---|---|---|
| Process/shift engineer | SOP answers, approval drafts, calc checks | Fast cites, Hindi prompts, kiosk-simple UI |
| Design/consulting engineer | P&ID review, vendor compare, board decks | Vision + tables, template-governed decks |
| IT/automation engineer | Internal-tool code, spreadsheet models | Sandboxed execution with verdicts |
| Vigilance/audit officer | Proof review, incident replay | Audit chain, export, zero-egress evidence |
| Dept head | Shutdown briefs, decision notes | One-click agent runs, governed formats |

### 5. Novelty (what nobody else ships together)

- **Cite-or-refuse as product law,** enforced in the generation path, not a prompt suggestion.
- **Session-scoped confidentiality:** uploads belong to the chat that uploaded them; exact-name grounding; new chat is cryptographically fresh (new session id, empty registry).
- **Signed Vault packs:** knowledge moves sites as `.hpack` (chunks + Merkle root + signature), verified on import — updates without trust.
- **Router economy:** per-subtask model selection with published reasons + live per-answer cost (`tokens / VRAM / ₹0.00`).
- **Proof as UI:** `● Local · 0 external` is a live endpoint, not a badge graphic; cable-pull is a demo step, not a claim.
- **Template governance:** `.htemplate` packs lock org branding/structure into every generated file.

---

## PART B — PRD

### 6. Functional requirements

- **F1 Commander chat:** Auto/Manual mode, Single/Swarm scope, per-model pin, template flow (Ask / Yes→which / No→auto), sessions with titles, bounded memory, file attach.
- **F2 Vault:** PDF/image/office ingest → chunk-by-heading → embeddings → hybrid vector+FTS retrieval with relevance gate; freshness stamps; exact-name lookup; signed pack import/export.
- **F3 Router:** score classifier, per-node model+reason, forced research→build Swarm fan-out, manual override, switch toasts.
- **F4 Agent runs:** one-button multi-step jobs (inspect scan → extract findings → draft note → Word file) with visible plan and per-step model tags.
- **F5 Code Lab:** sandboxed Python (no sockets, timeout, byte caps), stdout + verdict inline, recalc gate for sheets.
- **F6 Artifacts:** docx/pdf/pptx/xlsx builders with anti-slop gates (cites, overflow, contrast, recalc), native save, traversal-safe downloads, chat intent ("give it as docx") builds inline.
- **F7 Proof:** network map, audit chain + verify + export, genome display, cost meter, models registry.
- **F8 Multilingual:** Hindi/Hinglish prompts and OCR (`hin+eng`), same grounding rules.

### 7. Non-functional requirements

- **Security:** zero egress by default; jail sandbox; upload allowlist (pdf/png/jpg/office); traversal-safe file serving; no secrets in repo or logs; personal uploads never leave disk.
- **Performance (Edge floor):** first answer <60s cold / <15s warm; Swarm sequential under VRAM cap; 256-token node cap; 4K context on 6GB VRAM.
- **Reliability:** offline cache fallback, OOM unload-and-retry, CPU-only flag, clean double-click boot, offline-capable UI (zero CDN).
- **Portability:** same binary Edge laptop → dept workstation → confidential VM; GGUF drop-in model policy.

### 8. Acceptance criteria (mapped to PS 26117)

- Auto-selection across ≥2 task types with visible reasons. Agentic scan→findings→Word run end-to-end. Sandboxed code task with PASS verdict. Image/scan understanding with cites. Local KB grounding on every factual answer. Visible zero-external-call evidence throughout. New model addable via registry without redesign. Full run on a single mid-range-GPU workstation.

---

## PART C — ARCHITECTURE

### 9. System blueprint

```
[Desktop shell | CLI] → Commander UI (chat, vault, artifacts, proof)
  → Classifier → Router (per-node model+reason, fan-out, manual pins)
  → Session store (isolated memory + file registry, bounded, no rot)
  → Orchestrator (Single direct / Swarm research→build / Agent plan loop)
  → Vault RG engine (ingest → chunk → embed → Chroma vectors + FTS5 → relevance gate → cites)
  → Genome (tag-matched operating rules injected per task type)
  → Tool mesh, all jailed (python_jail, docx/pdf/pptx/xlsx writers, OCR, template vault)
  → Release gates (cites≥1 when required, recalc 0, overflow, contrast)
  → Proof + audit (packet map, hash chain, export)
```

### 10. Data flows

- **Ask flow:** prompt → classify → route → session memory + file registry resolve → Vault retrieve (named-first, global fallback minus foreign uploads) → genome rules → generate (pixels attached for vision) → reply hygiene strip → cites/file attach → audit log.
- **Ingest flow:** upload → allowlist → OCR (images) / per-page text (PDF) → chunk-by-heading → embed → dual-store → session registry → freshness stamp.
- **Agent flow:** plan (research/build nodes) → per-step generate → verifier gates → artifact build → download + audit.
- **Sync flow (multi-site):** export `.hpack` (chunks + Merkle root + signature) → import verifies signature + root before indexing.

### 11. Deployment topologies

- **Edge (this laptop):** 6GB VRAM, 1–2 resident models, sequential Swarm, SQLite+Chroma, Tesseract. SIH demo target.
- **Workstation (dept server):** 24GB VRAM, 14–32B models, parallel Swarm, 8K ctx, Hindi pack, LibreOffice headless.
- **Confidential cloud (HQ):** TEE VMs, same binary + signed packs, central audit aggregation. Identical proof endpoints.

### 12. Tech bill (all local, $0 license)

Ollama (GGUF Q4) · FastAPI + pywebview shell · Chroma + SQLite FTS5 · nomic-embed · Tesseract + Qwen-VL · python-docx/openpyxl/python-pptx/reportlab · pytesseract/Pillow · psutil proof · Python jail (subprocess, socket-blocked).

### 13. Roadmap to December

E1 agent runs + code-in-chat → E2 proof/cost/freshness surfaces + models registry + template vault → E3 sync packs + Hindi + hardening → freeze end-November (named commit) → December rehearsal only. The 7-minute demo (leak story → cited answer → `not in SOP` → vision toast → chat-to-file → agent run → cable-pull → cost/audit close) is the acceptance test.

### 14. Honest limits (stated, not hidden)

Small models reason less deeply than frontier ones — the router, decomposition and verifier exist because of this. Vision OCR degrades on handwriting (VL + Tesseract vote; low-confidence flagged, never guessed). First answer pays model-load time (pre-warm in runbook). These are engineered around, not marketed away.
