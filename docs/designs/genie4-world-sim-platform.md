# Governed Genie 4 World-Simulation Platform (81-Repo Estate Design)

*   **Author:** Dr Josh Tedam
*   **Status:** Proposed
*   **Date:** 2026-11-19

--------------------------------------------------------------------------------

## Overview

This document defines the architecture, governance controls, commercial gates, and Wave 1 implementation plan for introducing interactive 3D world simulation—targeting Google DeepMind's Genie 4—across the **81 non-forked first-party repositories** (`79` in `symphonix-health` plus `africa-marketplace` and `elocute`, excluding the `26` upstream forks in `workspace-forks.json`).

Rather than embedding vendor world-model SDKs inside individual repositories, the estate will route every world-simulation request through one shared, governed adapter (`WorldSimProvider`) hosted in `symphonix-bridge-sdk`. Healthcare repositories consume it through `BulletTrain` (`/v1/world-sim/*`), while standalone commercial repositories (`elocute` and `africa-marketplace`) import the same governed library directly to preserve commerce-to-clinical isolation. Until Genie 4's Gemini API reaches general availability (GA) with published pricing, an enterprise SLA, and a healthcare BAA/DPIA, all workflows run end-to-end against `symphonix-emulator-kit` and degrade across a 3-rung fallback ladder without charging live simulation credits.

## The Problem

Across our `81` non-forked repositories, three distinct product surfaces hit a ceiling that static 2D interfaces, pre-built 3D scenes, and audio-only conversational agents cannot clear economically:

1. **Clinical staff situational rehearsal (`nursing-station`, `picis-system`, `ambulance-ems`, `maternity-system`, `triage-api`, `gp-system`, `community-nursing`):** Hospital trusts and training deaneries pay heavily for physical OSCE stations, manikin labs, and hand-authored Unity/Unreal scenes. Static forms and audio-only chatbots miss spatial hazard recognition, environmental crowding, alarm fatigue, and mid-scenario escalation under realistic ambient noise.
2. **Commercial immersion & virtual showrooms (`elocute`, `africa-marketplace`):** *Elocute Learn* teaches 44 Received Pronunciation (RP) phonemes in clean, quiet drills, leaving learners unprepared for real-world acoustic stress (noisy cafés, high-pressure interviews, multi-speaker interruptions). On `africa-marketplace`, high-ticket categories (real estate/rentals, furniture, artisan workshops, hospitality, wholesale farm-gate lots) suffer from low buyer trust on static photos, while custom 3D scanning is unaffordable for most sellers.
3. **Clinician-supervised patient familiarization and graded exposure (`vr-therapy`, `rehabilitation`, `citizen-portal`, `mha-administration`, `hear-the-risk`):** Building bespoke 3D scenes for every phobia trigger, discharge kitchen layout, or MRI/chemotherapy unit takes weeks per asset.

At the same time, adopting Genie 4 naively across the estate introduces four unacceptable failure modes:
- **Uncontrolled PHI and clinical safety exposure:** Sending real patient home photos, DICOM scans, or unvalidated free-text prompts to an uncertified preview model violates UK-GDPR/HIPAA and DCB0129/DCB0160 clinical safety duties.
- **Scale drift and object-permanence loss:** Pixel-generated worlds cannot be trusted to display accurate vital signs, drug doses, anatomical measurements, or calibrated device readings.
- **Hard 2-minute session cap:** Standard 10–45 minute clinical drills and exposure sessions fail unless redesigned around short, structured micro-vignettes.
- **Unbounded GPU inference cost:** Without hard per-tenant quotas, buyer-qualified tokens, and a pre-GA unit-economics gate, per-minute world-model costs (`\$0.32–\$2.05` per 2-minute vignette) will invert B2C and seller subscription margins.

## Goals

*   **Exhaustive 81/81 Repository Classification:** Account for every non-forked first-party repository (`9` Tier-1 paid-subscription production candidates, `5` Tier-2 clinician-supervised PoCs, `14` Tier-3 shared platform/governance/research enablers, and `53` Tier-4 explicit cuts) with zero omissions and automated enforcement against shadow vendor SDK imports.
*   **Single Governed Platform Adapter:** Centralize zero-PHI input enforcement, 120-second hard session caps, SynthID provenance logging, quota accounting, and 3-rung fallback (`genie4_api` -> `emulator_replay` -> `static_vignette_fallback`) in `symphonix-bridge-sdk` + `BulletTrain` rather than duplicating logic per repo.
*   **Technical Zero-PHI Guarantee:** Enforce synthetic-seed allowlists (blocking arbitrary photo uploads on healthcare tenants), template-bound steering intents from `prompt-engine`, and deterministic PII/NHS-number egress scrubbing so zero PHI can reach external world-model endpoints.
*   **Deterministic Clinical Precision Alongside Generative Immersion:** Separate spatial/acoustic simulation (70% generative canvas) from quantitative vitals, drug doses, scoring checklists, timers, and instant-abort controls (30% deterministic SFDS v2.4 HUD) inside a single `100vh`, full-width, zero-downscroll `<WorldSimViewport />` tab panel.
*   **Protected Paid-Subscription Unit Economics (`>= 65%` Gross Margin):** Gate live Genie 4 billing behind explicit API GA, `>= 99.5%` SLA, and pricing ceilings (`<= \$0.45/min` before flipping live B2C `elocute` billing; buyer-qualified walkthrough tokens on `africa-marketplace`; pooled 12-vignette/seat/month quotas on B2B Trust training tiers).
*   **Wave 1 Narrow-Wedge Delivery:** Prove the end-to-end architecture on the shared platform spine (`symphonix-bridge-sdk`, `BulletTrain`, `symphonix-emulator-kit`, `design-system`, `ormdet-governance-console`, `csaa`) plus `2` Tier-1 pilots (`nursing-station` B2B and `elocute` B2C) and `1` Tier-2 clinician-supervised PoC (`vr-therapy`) before expanding to the remaining `7` Tier-1 and `4` Tier-2 repos.

## Non-Goals

*   **No live production patient-facing Genie 4 sessions** prior to Gemini API GA, executed BAA/DPIA, and human Clinical Safety Officer (CSO) DCB0129/DCB0160 release sign-off in `csaa`.
*   **No real patient photos, clinical imaging (DICOM), or PHI** passed as text prompts or image-to-world seeds.
*   **No quantitative clinical rendering inside generative pixels** (no vital-sign waveforms, ventilator settings, infusion doses, or anatomical/range-of-motion measurements read off Genie 4 frames).
*   **No vehicle driving simulation** in `ambulance-ems` (Genie 4 handles complex vehicle controls poorly), **no integration into *Elocute Live*** (250ms virtual-camera latency ceiling), and **no integration into `africa-marketplace` WhatsApp/USSD/SMS staple-goods flows** (2G/3G bandwidth mismatch).
*   **No new standalone `world-sim-service` microservice repository** and **no direct per-repo Genie 4 SDK dependencies** outside `symphonix-bridge-sdk`.
*   **No Genie 4 adoption in the 53 Tier-4 repositories** (deterministic clinical/diagnostic systems such as `pacs-ris`, `blood-transfusion`, `lis`, `pharmacy-system`, `genomics-interpretation`, `epaccs`, `mortuary-and-me`, `enterprise-epr`; transactional pathways/registries; ERP/GRC/eClaims; `tool-library`; headless interop shims; `symphonix-health-counterpoint`; static docs/marketing sites including `symphonix-public`).

## Open Questions

*   **Question 1 (Published Genie 4 API Pricing & Rate Limits):** Exact per-minute inference pricing, concurrent stream caps, and regional data-residency endpoints for Genie 4 via the Gemini API are not yet published. Live billing activation remains gated until these numbers are verified against the `>= 65%` gross-margin threshold (`<= \$0.45/min` for B2C `elocute`).
*   **Question 2 (`hear-the-risk` Disposition):** Confirm before Wave 2 whether `hear-the-risk` remains a low-priority Tier-2 research/education PoC or is cut to Tier 4 to concentrate PoC validation on `vr-therapy` and `rehabilitation`.
*   **Question 3 (`gpconnect` & `integration-adaptors` Inventory Reconciliation):** Both repositories appear in `estate_repo_inventory.json` and `workspace-forks.json`. Both are Tier-4 cuts regardless, but `workspace-tooling` should clarify their canonical fork status.

## Critical User Journeys (CUJs)

### CUJ 1: B2B Clinical Staff Relay Micro-Vignette Drill (`nursing-station` — Tier 1 Pilot)

*   **Given**: A hospital trust subscribes to the paid Simulation Add-On (`12` pooled vignettes/learner seat/month). A nurse educator opens the Training Sandbox tab in `nursing-station` (`100vh` SFDS v2.4 viewport) and selects a curated synthetic ward-bay deterioration scenario (`seed_id = "ward_bay_sepsis_01"`, `3 x 2-minute` acts).
*   **When**: The educator starts Act 1 and triggers a template-bound mid-session steering event (`intent = "escalate_alarm_fatigue_and_family_interruption"`).
*   **Then**: `BulletTrain` verifies OIDC claims, tenant quota, synthetic-seed allowlist, and zero-PHI rules; streams a 120-second interactive vignette (from `genie4_api` when GA and enabled, or `emulator_replay` today) in the 70% canvas while rendering deterministic NEWS2 vitals, escalation checklist, countdown timer, and instant-abort bar in the 30% SFDS HUD; logs a WORM SynthID provenance receipt to PostgreSQL 15 and `ormdet-governance-console`; and pauses after 120 seconds for a 60-second deterministic debrief before Gemini 3.8 Flash seeds Act 2.

### CUJ 2: B2C Commercial Paid Immersion Session (`elocute` — Tier 1 Pilot)

*   **Given**: A paid *Elocute Immersion Pro* subscriber (`10` live vignettes/month quota) launches a 2-minute *Elocute Learn* workplace scenario ("Noisy Café Technical Interview") with target RP phonemes.
*   **When**: The learner speaks and navigates inside the interactive 3D café while the system steers background acoustic load (`intent = "increase_ambient_chatter"`).
*   **Then**: `elocute` invokes `symphonix-bridge-sdk`'s `WorldSimProvider` directly (without `BulletTrain`), enforces the 120-second cap and monthly vignette quota, streams synchronized audio and character dialogue (or falls back to `emulator_replay` without deducting a live credit if the API is unavailable or B2C pricing exceeds `\$0.45/min`), and records phoneme accuracy alongside the SynthID session digest.

### CUJ 3: Clinician-Supervised Patient Exposure PoC with Instant Abort (`vr-therapy` — Tier 2 PoC)

*   **Given**: `csaa` has logged the DCB0129/DCB0160 world-model hazard assessment and marked the environment `poc_only` (`release_gate == "blocked"` for unsupervised production). A clinician supervises a consented PoC participant inside `vr-therapy` using a curated synthetic hospital-corridor seed (`seed_id = "clinic_waiting_calm_02"`).
*   **When**: The participant's distress score crosses threshold or the clinician presses the `<WorldSimViewport />` instant-abort control.
*   **Then**: The viewport cuts to the calm static local fallback within `< 200ms`, terminates the upstream stream immediately, logs the abort reason and SynthID receipt to `BulletTrain` and `ormdet-governance-console`, and blocks any further steering prompts until the clinician explicitly resets the session.

### CUJ 4: Zero-PHI Context-Firewall Rejection & Pre-GA Fallback (`BulletTrain` + `symphonix-bridge-sdk`)

*   **Given**: A user attempts to start a healthcare simulation session with a free-text prompt containing an NHS number or patient name, or attempts to upload an arbitrary photo on a healthcare tenant.
*   **When**: The request hits `BulletTrain` `/v1/world-sim/sessions`.
*   **Then**: The zero-PHI firewall hard-rejects the request (`HTTP 422`) before any external network call, emits a sanitized rejection audit event to `ormdet-governance-console`, and deducts zero tenant quota. Separately, if a valid synthetic request hits an upstream `429`/`503` or pre-GA feature flag, `symphonix-bridge-sdk` transitions down the 3-rung fallback ladder (`emulator_replay` -> `static_vignette_fallback`), surfaces the fallback banner in `<WorldSimViewport />`, and deducts zero live credits.

--------------------------------------------------------------------------------

## Technical Plan (Architecture)

### 1. System Topology & Component Boundaries

All world-simulation capabilities across the `81` non-forked repositories are centralized behind a single governed Python package (`bridge_sdk.adapters.world_sim`) inside `symphonix-bridge-sdk`. Healthcare repositories never call vendor SDKs directly; they call `BulletTrain` (`services/api_gateway`), which mounts `/v1/world-sim/*` using `symphonix-bridge-sdk`. Standalone commercial repositories (`elocute` via `services/llm-gateway` and `africa-marketplace` via its buyer-web backend) import `symphonix-bridge-sdk` directly with their own commercial auth and billing so `BulletTrain` remains strictly isolated from non-clinical commerce.

```text
+-----------------------------------------------------------------------------------+
| Clients (100vh Full-Width SFDS v2.4 <WorldSimViewport /> from design-system)      |
|  70% Generative Canvas (WebRTC or Multiplexed WS) | 30% Deterministic SFDS HUD    |
|  [Wave 1: nursing-station, vr-therapy (PoC)]      | [Wave 1: elocute Learn]       |
+-----------------------+---------------------------+---------------+---------------+
                        | OIDC JWT + Tenant Policy                  | Commercial JWT
                        v                                           v
+-----------------------------------------------+   +-------------------------------+
| BulletTrain (services/api_gateway)            |   | elocute/services/llm-gateway  |
|  /v1/world-sim/sessions (REST + WS/WebRTC)    |   | (and Wave 2 africa-marketplace)|
|  - Entitlement & Pooled Quota Gate            |   |  - B2C Quota (10/mo) &        |
|  - Zero-PHI Context Firewall (422 on hit)     |   |    <= $0.45/min Margin Gate   |
|  - CSAA Release-Gate Check (Tier 2 PoC lock)  |   +---------------+---------------+
+-----------------------+-----------------------+                   |
                        | imports                                   | imports
                        +---------------------+---------------------+
                                              v
              +---------------------------------------------------------------+
              | symphonix-bridge-sdk (bridge_sdk.adapters.world_sim)          |
              |  - WorldSimProvider interface + configurable transport        |
              |    (`webrtc` | `ws_multiplex` | `auto_fallback` per tenant)   |
              |  - Hard 120s Session Timer & <200ms Local Abort Controller    |
              |  - Relay Micro-Vignette Handoff (Gemini 3.8 Flash Act summary)|
              |  - Circuit Breaker (G11), Semaphore (G21), Residency (G17)    |
              +-------+-----------------------+-----------------------+-------+
                      | Rung 1 (GA + Margin)  | Rung 2 (Pre-GA/429)   | Rung 3
                      v                       v                       v
         +-----------------------+ +-----------------------+ +-------------------+
         | Google DeepMind       | | symphonix-emulator-kit| | Local Static      |
         | Genie 4 API           | | WorldSimEmulator      | | Vignette / Audio  |
         | (+ Gemini 3.8 Flash)  | | (Deterministic 120s   | | Tabletop Fallback |
         | [Feature-Flagged Off] | |  streams + SynthID)   | | (Zero GPU Cost)   |
         +-----------+-----------+ +-----------+-----------+ +---------+---------+
                     |                         |                       |
                     +------------+------------+-----------------------+
                                  v
         +--------------------------------------------------------------------+
         | Dual-Engine WORM Provenance & Governance Plane                     |
         |  - PostgreSQL 15 (`world_sim.session_receipts`, BEFORE DELETE WORM)|
         |  - Per-service 3-tier SQLite WAL mirror (`sh_kf_state_001_wal.db`) |
         |  - ormdet-governance-console (SynthID + Zero-PHI rejection feed)   |
         |  - csaa (DCB0129/0160 Hazard Log + Tier 2 `release_gate` lock)     |
         |  - alerting & dashboards (80%/95% quota alerts, gross-margin view) |
         +--------------------------------------------------------------------+
```

### 2. Core Contracts & Mechanisms

#### A. `WorldSimProvider` & 3-Rung Fallback Ladder (`symphonix-bridge-sdk`)
`bridge_sdk/adapters/world_sim.py` exposes one async contract (`create_session`, `steer_session`, `abort_session`, `complete_act`) backed by three providers selected automatically by feature flag, unit-economics gate, and circuit breaker (`G11`):
1. **Rung 1 (`genie4_api`):** Calls the Genie 4 API when `WORLD_SIM_GENIE4_GA_ENABLED == true`, tenant entitlement is active, and configured per-minute price passes the tier margin ceiling (`<= \$0.45/min` for B2C `elocute`; `<= \$1.00/min` for B2B Trust seats).
2. **Rung 2 (`emulator_replay`):** Routes to `symphonix-emulator-kit`'s `WorldSimEmulator` (`backends/world_sim.py`), streaming pre-recorded or procedurally branched 120-second synthetic vignettes with deterministic SynthID test receipts and fault-injection hooks (`429`/`503`). Deducts zero live credits.
3. **Rung 3 (`static_vignette_fallback`):** Serves static synthetic scene cards plus deterministic SFDS audio/text tabletop prompts locally when both upstream API and emulator are unreachable. Deducts zero live credits.

#### B. Configurable Media & Control Transport (`webrtc` | `ws_multiplex` | `auto_fallback`)
Each tenant policy specifies `transport_mode`:
- **`webrtc`:** Streams interactive video and synchronized audio over WebRTC (UDP/SRTP) with a separate authenticated WebSocket (`/v1/world-sim/sessions/{id}/control`) for template-bound steering intents, 1-second server-authoritative countdown ticks, and instant abort signals.
- **`ws_multiplex`:** Multiplexes fragmented H.264/Opus binary chunks and JSON control frames over a single TLS/443 WebSocket (reusing `bridge_sdk/adapters/websocket_adapter.py`), requiring zero TURN infrastructure behind locked-down NHS/hospital proxies.
- **`auto_fallback`:** Attempts WebRTC ICE negotiation with a strict 2-second timeout; if UDP is blocked or times out, transparently binds the same session token to `ws_multiplex` and records `transport_used = "ws_multiplex_fallback"` in the session receipt.

#### C. Technical Zero-PHI Context Firewall
Every request entering `BulletTrain` `/v1/world-sim/*` (and commercial requests configured with `strict_synthetic_mode = true`) passes three deterministic gates before any upstream call:
1. **Synthetic-Seed Allowlist:** Healthcare tenants may only pass an immutable `seed_asset_id` registered in `prompt-engine` (e.g., `ward_bay_sepsis_01`, `clinic_waiting_calm_02`). Arbitrary image uploads are rejected (`HTTP 422`) on healthcare tenants. (`africa-marketplace` Wave 2 commercial showrooms run a dedicated face/licence-plate/PII redaction check on seller showroom photos before egress.)
2. **Template-Bound Steering Intents:** Mid-session steering accepts only `intent_id` + strictly typed enum parameters defined in `prompt-engine` YAML templates (no raw free-text prompt injection on healthcare tenants).
3. **Deterministic PII/NHS-Number Scrubber:** Reuses `vr-therapy/backend/src/phi_scrub.py` patterns (NHS number checksums, DOBs, postcodes, phone/email, names) on all text fields and returns `HTTP 422` + sanitized rejection receipt to `ormdet-governance-console` on any match.

#### D. Hard 120-Second Session Cap, Relay Micro-Vignettes & `< 200ms` Instant Abort
- **Server-authoritative 120s timer:** `WorldSimProvider` starts a monotonic 120-second timer at stream start, emits server ticks over the control channel, and hard-closes the upstream Genie 4 stream at `t = 120.0s`.
- **Relay Micro-Vignettes (`3 x 2-minute` acts):** Multi-step clinical drills (`nursing-station`) pause at `t = 120s` for a 60-second deterministic SFDS debrief/decision gate. Gemini 3.8 Flash summarizes the Act `k` state into a strictly typed, zero-PHI JSON handoff payload (`act_summary_schema`) to seed Act `k + 1`.
- **Instant Abort (`< 200ms`):** Pressing the `<WorldSimViewport />` abort control (or crossing the distress threshold in `vr-therapy/backend/src/fsm.py`) immediately swaps the 70% canvas locally to a bundled calm static frame (`< 200ms` client-side, independent of network RTT) while firing an asynchronous `POST /v1/world-sim/sessions/{id}/abort` that terminates the upstream stream and locks steering until explicit clinician reset.

#### E. Canonical SFDS v2.4 `<WorldSimViewport />` (`design-system`)
Delivered in `design-system/ui_kits/clinical-react/WorldSimViewport.tsx` as a full-width, `100vh`, zero-vertical-downscroll tab panel:
- **Left 70% (`WorldSimCanvas`):** Renders the generative stream (WebRTC `<video>` or `ws_multiplex` WebCodecs/MSE canvas) with SynthID watermark badge, active transport indicator, and fallback banner.
- **Right 30% (`DeterministicHudPanel`):** Renders quantitative vitals/NEWS2/checklists (never inside generative pixels), template-bound steering buttons, 120-second countdown ring, and the always-visible instant-abort bar.

#### F. Dual-Engine Persistence & WORM Provenance Schema (`L-431`)
Every session lifecycle event is persisted across both live **PostgreSQL 15** (`bt-postgres-dev`, schema `world_sim`) and per-service **3-tier SQLite WAL** (`data/{sibling_slug}_sh_kf_state_001_wal.db`):
- `world_sim.session_receipts`: `(session_id UUID PK, tenant_id, repo_slug, actor_persona, tier, provider_rung, transport_used, seed_asset_id, synthid_digest, started_at, ended_at, duration_ms CHECK (duration_ms <= 125000), abort_reason, credit_deducted BOOLEAN, estimated_cost_usd NUMERIC(8,4), created_at)` protected by `BEFORE DELETE` WORM trigger (`client_registry.forbid_clinical_record_delete()`).
- `world_sim.firewall_rejections`: `(rejection_id UUID PK, tenant_id, repo_slug, rule_triggered, field_name, created_at)` — stores rule metadata only, never the rejected raw input string, and streams to `ormdet-governance-console`.
- `world_sim.tenant_quotas`: `(tenant_id, billing_period, plan_tier, included_vignettes, used_vignettes, topup_vignettes, transport_mode, max_cost_per_min_usd)` enforced atomically via `SELECT ... FOR UPDATE` in PostgreSQL 15 before starting any Rung 1 (`genie4_api`) stream.

--------------------------------------------------------------------------------

## Alternatives Considered

### Alternative A: Direct Per-Repository Genie 4 SDK Integration

*   **Pros**: Each Tier 1 and Tier 2 repository could customize its own Genie 4 prompts, billing hooks, and UI loop without waiting on `symphonix-bridge-sdk` or `BulletTrain` releases.
*   **Cons**: Duplicates zero-PHI scrubbing, 120-second session timers, SynthID WORM provenance logging, and cost circuit-breakers across 14 repositories. A single misconfigured repository could leak PHI or trigger unbounded GPU spend.
*   **Reason for Rejection**: Rejected by author: a single shared governed platform adapter is mandatory to enforce zero-PHI controls, quota ceilings, and audit consistency across the `81`-repo estate.

### Alternative B: New Standalone `world-sim-service` Microservice Repository

*   **Pros**: Clean deployment isolation and independent scaling from `BulletTrain` and commercial backends.
*   **Cons**: Creates a redundant 82nd repository that duplicates circuit breakers, backpressure semaphores (`G21`), retry/fallback (`G11`), data residency (`G17`), OIDC auth, and PostgreSQL 15 WORM logging already maintained in `symphonix-bridge-sdk` and `BulletTrain`. Would also force either cross-boundary coupling with `africa-marketplace` or duplicated deployment plumbing.
*   **Reason for Rejection**: Rejected by author: hosting `WorldSimProvider` in `symphonix-bridge-sdk` (mounted in `BulletTrain` for healthcare and imported directly by `elocute` and `africa-marketplace`) achieves both reuse and commerce-to-clinical isolation without adding a new service repo.

### Alternative C: Real Patient Home Photos (Image-to-World) & Open-Ended Patient Prompt Steering

*   **Pros**: Higher personalization in `community-nursing` (fall-risk walkthrough of a real home), `rehabilitation`, and `citizen-portal`.
*   **Cons**: Sends identifiable domestic photographs and unvalidated free-text PHI to an external pre-GA world model with no executed BAA/DPIA, and exposes patients to unscripted visual or acoustic hallucinations without clinical safety bounds.
*   **Reason for Rejection**: Rejected by author: all Genie 4 inputs must remain strictly synthetic and de-identified (zero real patient photos, zero PHI), using curated synthetic archetype seeds and template-bound steering intents.

### Alternative D: Unlimited "All-You-Can-Eat" B2C Sessions & Open Buyer Browsing

*   **Pros**: Simpler marketing copy for *Elocute Immersion Pro* and frictionless showroom browsing on `africa-marketplace`.
*   **Cons**: At estimated Genie 4 inference costs (`\$0.32–\$2.05` per 2-minute vignette), heavy B2C users or casual anonymous buyers would drive gross margins negative within days.
*   **Reason for Rejection**: Rejected by author: paid subscriptions must sustain `>= 65%` gross margin via hard monthly vignette quotas (`10/month` on `elocute` with `<= \$0.45/min` GA cost gate) and buyer-qualified walkthrough tokens on `africa-marketplace`.

### Alternative E: Fixed Single Transport (WebRTC-Only or Multiplexed-WebSocket-Only)

*   **Pros**: Half the media transport code and test surface compared to configurable transport.
*   **Cons**: WebRTC-only fails behind locked-down hospital trust proxies that block outbound UDP unless dedicated TLS/443 TURN relays are operated; multiplexed-WebSocket-only suffers TCP head-of-line stutter on congested Wi-Fi and mobile connections.
*   **Reason for Rejection**: Rejected by author: locking per-tenant configurable transport (`webrtc`, `ws_multiplex`, or `auto_fallback`) lets hospital trusts pin `ws_multiplex` while commercial and open networks use low-latency `webrtc`.

### Alternative F: Defer All Design & Build Work Until Genie 4 API Reaches GA

*   **Pros**: Zero engineering spend if Google delays or reprices the Genie 4 Gemini API.
*   **Cons**: Delays `<WorldSimViewport />` UX validation, `csaa` DCB0129/DCB0160 hazard logging, zero-PHI firewall verification, and B2B pilot sales readiness by months after GA.
*   **Reason for Rejection**: Rejected by author: building against `symphonix-emulator-kit` (`Rung 2`) proves the full contract, UI, governance, and fallback behavior today with zero vendor lock-in.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security & Privacy:**
    *   Zero PHI leaves any healthcare tenant (allowlisted synthetic `seed_asset_id`, template-bound `intent_id`, deterministic PII scrubber returning `HTTP 422`).
    *   OIDC JWT + RBAC capability check (`world_sim:run_training` for Tier 1 clinical siblings; `world_sim:run_poc_supervised` + `csaa` `release_gate` verification for Tier 2 PoCs).
    *   `workspace-tooling` Semgrep rule (`no-direct-world-sim-sdk`) blocks direct imports of Genie 4 / vendor world-model SDKs outside `symphonix-bridge-sdk`.
*   **Clinical Safety (DCB0129/DCB0160):**
    *   Tier 2 patient-facing PoCs (`vr-therapy`, etc.) are hard-blocked from production release (`csaa` `release_gate == "blocked"`) until API GA, executed BAA/DPIA, and human CSO sign-off.
    *   Client-side instant abort swaps to calm static frame in `< 200ms` regardless of upstream network latency.
    *   Quantitative clinical telemetry is strictly isolated in the 30% deterministic SFDS HUD to eliminate scale-drift and hallucination hazards.
*   **Performance, Latency & Quota Economics:**
    *   Session startup target: `<= 2.5s` on `webrtc` / `ws_multiplex` (`<= 4.5s` worst-case on `auto_fallback` after 2s ICE timeout).
    *   Hard server-enforced 120-second stream cutoff (`duration_ms <= 125000` including graceful teardown).
    *   Unit-economics circuit breaker: `alerting` fires at `80%` and `95%` tenant quota and blocks Rung 1 (`genie4_api`) auto-promotion if measured unit cost breaches `\$0.45/min` (B2C) or `\$1.00/min` (B2B).
*   **Rollout & Rollback:**
    *   All Wave 1 repos ship with `WORLD_SIM_GENIE4_GA_ENABLED=false` (running Rung 2 `symphonix-emulator-kit`).
    *   Instant rollback from Rung 1 (`genie4_api`) to Rung 2 (`emulator_replay`) is a single runtime feature-flag toggle in `BulletTrain` / `elocute` with zero schema migration or client redeployment.

--------------------------------------------------------------------------------

### Future Improvements

*   **Wave 2 Tier-1 Expansion (7 Remaining Paid-Subscription Repos):** Onboard `africa-marketplace` (Verified Virtual Showroom with face/PII photo redaction and buyer-qualified walkthrough tokens), `picis-system`, `ambulance-ems` (on-foot scene size-up only), `maternity-system`, `triage-api`, `gp-system`, and `community-nursing` after Wave 1 passes API GA and `>= 65%` gross-margin verification.
*   **Wave 2 Tier-2 PoC Expansion (4 Remaining PoC Repos):** Onboard `rehabilitation`, `citizen-portal`, `mha-administration`, and (pending Open Question 2) `hear-the-risk` under `csaa` PoC-only release locks.
*   **Adaptive Bitrate & Regional TURN Auto-Provisioning:** Add optional managed TLS/443 TURN relays for hospital trusts that want `webrtc` instead of pinning `ws_multiplex`.
*   **Empirical Failure-Mode Benchmarks (`symphonix-research-lab`):** Automated scale-drift, object-permanence, and Gemini 3.8 Flash act-handoff accuracy benchmarks once Genie 4 API early access opens.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

All paths below are relative to the workspace root (`<WORKSPACE_ROOT>/`). Wave 1 covers the shared platform spine (`symphonix-bridge-sdk`, `BulletTrain`, `symphonix-emulator-kit`, `design-system`, `prompt-engine`, `ormdet-governance-console`, `csaa`, `workspace-tooling`) plus the three Wave 1 pilot consumers (`nursing-station`, `elocute`, `vr-therapy`).

### Target Files to Create/Modify

#### 1. `symphonix-bridge-sdk/src/bridge_sdk/adapters/world_sim.py` (Create)
*   **Type / Scope**: Python Shared Adapter Library (`WorldSimProvider`)
*   **Proposed Changes**: Define the canonical `WorldSimProvider` interface (`create_session`, `steer_session`, `abort_session`, `complete_act`), request/response Pydantic schemas (`WorldSimSessionRequest`, `WorldSimSteeringIntent`, `WorldSimReceipt`, `ActSummaryHandoff`), 3-rung provider router (`genie4_api`, `emulator_replay`, `static_vignette_fallback`), configurable transport negotiator (`webrtc`, `ws_multiplex`, `auto_fallback` with 2-second ICE timeout reusing `bridge_sdk/adapters/websocket_adapter.py`), server-authoritative 120-second monotonic cutoff timer, and zero-PHI context firewall (synthetic `seed_asset_id` allowlist, template-bound `intent_id` validation, deterministic PII/NHS-number scrubber). Reuse existing circuit breaker (`G11`), backpressure semaphore (`G21`), and data-residency guard (`G17`).

#### 2. `symphonix-bridge-sdk/tests/test_world_sim_adapter.py` (Create)
*   **Type / Scope**: Python Unit & Contract Tests
*   **Proposed Changes**: Verify zero-PHI `422` rejection on NHS numbers, DOBs, names, and disallowed photo uploads; verify 120-second hard cutoff (`duration_ms <= 125000`); verify 3-rung fallback transitions on `429`/`503` and `WORLD_SIM_GENIE4_GA_ENABLED=false` with `credit_deducted == False`; verify all three transport modes (`webrtc`, `ws_multiplex`, `auto_fallback`); verify margin-gate refusal when configured per-minute price exceeds tier ceiling (`\$0.45/min` B2C, `\$1.00/min` B2B).

#### 3. `symphonix-emulator-kit/src/symphonix_emulator_kit/backends/world_sim.py` (Create)
*   **Type / Scope**: Python Deterministic Emulator Backend (`WorldSimEmulator`)
*   **Proposed Changes**: Implement `WorldSimEmulator` extending `backends/base.py`, emitting deterministic 120-second synthetic micro-vignette streams over both `ws_multiplex` and mock WebRTC signaling, deterministic SynthID test digests, template-bound steering state transitions, and configurable fault injection (`429`, `503`, `ice_timeout`).

#### 4. `symphonix-emulator-kit/src/symphonix_emulator_kit/registry.py` (Modify)
*   **Type / Scope**: Python Emulator Registry
*   **Proposed Changes**: Register `WorldSimEmulator` under the `world_sim` backend key so `BulletTrain`, `elocute`, and CI pipelines resolve it consistently in Rung 2.

#### 5. `symphonix-emulator-kit/tests/test_world_sim_emulator.py` (Create)
*   **Type / Scope**: Python Unit Tests
*   **Proposed Changes**: Verify deterministic 120-second stream lifecycle, steering state transitions, SynthID digest generation, and `429`/`503`/`ice_timeout` fault-injection modes.

#### 6. `prompt-engine/config/world_sim_seeds.yaml` (Create)
*   **Type / Scope**: Audited Configuration / Seed & Steering Catalog
*   **Proposed Changes**: Define the canonical Wave 1 synthetic seed allowlist (`ward_bay_sepsis_01`, `elocute_noisy_cafe_01`, `clinic_waiting_calm_02`), versioned template-bound steering intents (`escalate_alarm_fatigue_and_family_interruption`, `increase_ambient_chatter`, `step_down_stimulus`), strict enum parameter schemas, and clinical-safety negative prompt clauses.

#### 7. `BulletTrain/alembic/versions/20261119_world_sim_worm_tables.py` (Create)
*   **Type / Scope**: PostgreSQL 15 Database Migration (`bt-postgres-dev`)
*   **Proposed Changes**: Create schema `world_sim` and tables `world_sim.session_receipts` (with `CHECK (duration_ms <= 125000)` and `BEFORE DELETE` WORM trigger `client_registry.forbid_clinical_record_delete()`), `world_sim.firewall_rejections` (rule metadata only, zero raw input text), and `world_sim.tenant_quotas` (`SELECT ... FOR UPDATE` quota tracking and per-tenant `transport_mode` + `max_cost_per_min_usd`).

#### 8. `BulletTrain/services/api_gateway/world_sim_proxy.py` (Create)
*   **Type / Scope**: FastAPI Gateway Router (`/v1/world-sim/*`)
*   **Proposed Changes**: Mount `POST /v1/world-sim/sessions`, `POST /v1/world-sim/sessions/{id}/steer`, `POST /v1/world-sim/sessions/{id}/abort`, `POST /v1/world-sim/sessions/{id}/complete-act`, and `WS /v1/world-sim/sessions/{id}/control`. Enforce OIDC JWT + RBAC (`world_sim:run_training` vs. `world_sim:run_poc_supervised`), `csaa` `release_gate` verification for Tier 2 PoCs, atomic PostgreSQL 15 quota reservation via `commercial_metering.py`, dual-engine receipt persistence, and forwarding of SynthID receipts and sanitized firewall rejections to `ormdet-governance-console`.

#### 9. `BulletTrain/services/api_gateway/commercial_metering.py` (Modify)
*   **Type / Scope**: Python Metering & Quota Module
*   **Proposed Changes**: Add pooled B2B vignette accounting (`world_sim.tenant_quotas`) ensuring zero credit deduction on `emulator_replay`, `static_vignette_fallback`, or `HTTP 422` firewall rejections, and emitting 80%/95% quota telemetry events for `alerting` and `dashboards`.

#### 10. `BulletTrain/tests/test_world_sim_gateway.py` (Create)
*   **Type / Scope**: Dual-Engine Integration Tests (PostgreSQL 15 + SQLite WAL)
*   **Proposed Changes**: Test full `/v1/world-sim/*` lifecycle against isolated PostgreSQL 15 sandbox schema + SQLite WAL: OIDC/RBAC enforcement, `csaa` PoC production block, `HTTP 422` zero-PHI rejection with zero credit deduction, WORM `DELETE` protection trigger assertion, and Rung 1 -> Rung 2 -> Rung 3 fallback behavior.

#### 11. `design-system/ui_kits/clinical-react/WorldSimViewport.tsx` (Create)
*   **Type / Scope**: React / TypeScript SFDS v2.4 UI Component
*   **Proposed Changes**: Implement `<WorldSimViewport />` as a full-width, `100vh`, zero-vertical-downscroll tab panel with a 70/30 split (`WorldSimCanvas` supporting `webrtc` + `ws_multiplex` + `auto_fallback`, SynthID badge, and fallback banner on the left; `DeterministicHudPanel` with quantitative clinical telemetry, template-bound steering buttons, 120s countdown ring, and `< 200ms` local-swap instant-abort bar on the right). Enforce `light`, `dark`, and `high-contrast` SFDS v2.4 theme parity.

#### 12. `design-system/tests/WorldSimViewport.test.tsx` (Create)
*   **Type / Scope**: Frontend Component & Accessibility Tests
*   **Proposed Changes**: Verify `< 200ms` local calm-fallback swap on abort click, 120s countdown lock, fallback banner visibility, keyboard accessibility, and zero quantitative clinical data rendered inside the canvas element.

#### 13. `ormdet-governance-console/backend/src/ormdet_gateway.py` (Modify)
*   **Type / Scope**: Python Governance Ingestion Endpoint
*   **Proposed Changes**: Add ingestion handlers for `world_sim.session_receipt` (SynthID provenance digest, provider rung, transport mode, abort reason) and `world_sim.firewall_rejection` (sanitized rule metadata) persisted across PostgreSQL 15 (`sibling_ormdet`) and SQLite WAL.

#### 14. `csaa/csaa/hazards.py` (Modify)
*   **Type / Scope**: Clinical Safety Hazard Catalog (DCB0129/DCB0160)
*   **Proposed Changes**: Register canonical generative world-model hazard entries (`WM-HZ-01` scale drift / quantitative misread, `WM-HZ-02` object permanence loss, `WM-HZ-03` unscripted distress trigger, `WM-HZ-04` PHI egress attempt) and enforce `release_gate == "blocked"` on Tier 2 patient-facing PoCs until human CSO sign-off is recorded.

#### 15. `workspace-tooling/tools/semgrep/no_direct_world_sim_sdk.yaml` (Create)
*   **Type / Scope**: Static Analysis Policy Rule
*   **Proposed Changes**: Fail CI/pre-commit if any of the `81` non-forked repositories outside `symphonix-bridge-sdk` directly imports Genie 4 or vendor world-model client libraries.

#### 16. `nursing-station/backend/nursing_station/world_sim_training.py` (Create) & `nursing-station/frontend/src/components/TrainingSandboxTab.tsx` (Create)
*   **Type / Scope**: Wave 1 Tier-1 B2B Pilot (`nursing-station`)
*   **Proposed Changes**: Wire the `3 x 2-minute` ward-bay sepsis relay micro-vignette workflow (`seed_id = "ward_bay_sepsis_01"`) to `BulletTrain` `/v1/world-sim/*`, render `<WorldSimViewport />` in a dedicated WAI-ARIA Training Sandbox tab with deterministic NEWS2 vitals and 60-second Act debrief gates in the 30% HUD, and mirror receipts to `sibling_nursing` SQLite WAL + PostgreSQL 15.

#### 17. `elocute/services/llm-gateway/app/world_sim_router.py` (Create) & `elocute/apps/web/src/features/immersion/ImmersionProTab.tsx` (Create)
*   **Type / Scope**: Wave 1 Tier-1 B2C Pilot (`elocute` — *Elocute Learn* only)
*   **Proposed Changes**: Import `bridge_sdk.adapters.world_sim` directly (no `BulletTrain` dependency), enforce the `10` live vignettes/month paid quota and `<= \$0.45/min` B2C margin gate, mount `<WorldSimViewport />` inside *Elocute Learn* (`seed_id = "elocute_noisy_cafe_01"`), and record RP phoneme scores alongside the SynthID session digest. Explicitly exclude *Elocute Live*.

#### 18. `vr-therapy/backend/src/world_sim_poc.py` (Create) & `vr-therapy/frontend/src/components/ExposurePocTab.tsx` (Create)
*   **Type / Scope**: Wave 1 Tier-2 Clinician-Supervised PoC (`vr-therapy`)
*   **Proposed Changes**: Wire clinician-supervised 2-minute graded exposure bursts (`seed_id = "clinic_waiting_calm_02"`) to `BulletTrain` `/v1/world-sim/*` with `world_sim:run_poc_supervised` RBAC, integrate `vr-therapy/backend/src/fsm.py` distress-threshold auto-abort with `<WorldSimViewport />`'s `< 200ms` calm-fallback swap, and enforce `csaa` `poc_only` badge and production release lock.

### Verification Plan

*   **Unit & Contract Tests (`0 failed, 0 skipped`):**
    *   `symphonix-bridge-sdk`: `pytest tests/test_world_sim_adapter.py` (plus full suite regression).
    *   `symphonix-emulator-kit`: `pytest tests/test_world_sim_emulator.py` (plus full suite).
    *   `csaa` & `ormdet-governance-console`: `pytest` verifying DCB0129/0160 hazard registration, Tier 2 `release_gate == "blocked"`, and SynthID/firewall receipt ingestion.
*   **Dual-Engine Integration Tests (PostgreSQL 15 + SQLite WAL):**
    *   `BulletTrain`: `pytest tests/test_world_sim_gateway.py` against live PostgreSQL 15 (`bt-postgres-dev`, isolated sandbox schema with teardown) and SQLite WAL, asserting `BEFORE DELETE` WORM triggers, atomic quota deduction, `HTTP 422` zero-PHI rejections, and 3-rung fallback.
    *   Pilot suites (`nursing-station`, `elocute`, `vr-therapy`): full backend + frontend test suites verifying relay Act handoff, B2C `<= \$0.45/min` margin lock, and distress-threshold `< 200ms` abort.
*   **Static Analysis & Estate Guard:**
    *   Run `semgrep --config workspace-tooling/tools/semgrep/no_direct_world_sim_sdk.yaml` across all `81` non-forked repositories (`0` findings).
    *   Run `ruff check`, `mypy`, and TypeScript `tsc --noEmit` across modified packages.
*   **Headed Browser UI & Layout Verification (`signalbox-mcp`, Compact JSON Verdicts, `screenshots: []`):**
    *   Launch live headed SignalBox sessions on `WinSta0\Default` (`no_viewport=True`, maximized) with domain-relevant personas (`triage-nurse-superpersona` / `nurse` on `nursing-station`, `clinician-superpersona` on `vr-therapy`, learner persona on `elocute`).
    *   Verify `browser_layout_audit` across `light`, `dark`, and `high-contrast` themes: `scrollHeight <= innerHeight`, `mainRect.width >= window.innerWidth - 2`, single-row `role="tablist"`, `< 200ms` abort swap, fallback banner visibility, and zero quantitative clinical telemetry inside the generative canvas. Persist compact JSON verdicts in `docs/verification/frontend-headed-evidence.json`.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
