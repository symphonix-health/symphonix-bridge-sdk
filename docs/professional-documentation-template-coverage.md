# Professional documentation template coverage

Repository: `symphonix-bridge-sdk`

The Bridge SDK transports structured clinical, operational, and agent evidence
between services. It does not author final clinical documents. Its
documentation responsibility is to preserve the metadata that downstream
professional templates require: provenance, consent, owner, freshness, audit
reference, and next action.

## Supported catalogue mappings

| Bridge SDK evidence | Catalogue template | Reason |
| --- | --- | --- |
| Human handoff packet | DOC-TPL-009 SBAR handover | Carries situation, background, assessment, recommendation, owner, and timestamp. |
| Patient-identity closed-loop evidence | DOC-TPL-020 Clinical risk assessment | Records identity-matching controls and residual risk. |
| Consent and data-sharing projection | DOC-TPL-020 Clinical risk assessment | Provides consent state, policy boundary, and accountable owner. |
| Agent escalation or handoff | DOC-TPL-021 Escalation note | Captures urgent owner transfer and required human action. |
| Medicines or pharmacy agent evidence | DOC-TPL-022 Medicines reconciliation | Preserves medication-related source, action, and audit fields for the final pharmacy document. |
| Safeguarding or governance alert envelope | DOC-TPL-028 Safeguarding concern | Carries red-flag state and review requirements without silently filing a final document. |

## Required metadata carried by envelopes

Bridge SDK envelopes used in professional documentation must preserve:

- source service
- source record or correlation identifier
- agent or human author where known
- generated timestamp
- tenant or jurisdiction boundary
- consent state
- confidence or freshness state
- owner and next action
- audit reference
- safety-scope or escalation state when applicable

## Human review rule

Bridge SDK evidence is transport evidence, not a final author. Downstream
systems must render AI or agent evidence as draft/supporting material until a
qualified human completes the professional document and signs it.

## Gap handling

If an envelope cannot be mapped to a catalogue template, the consuming repo
must record a template-selection gap and show the gap in the rendered
professional document. Silent filing is blocked.
