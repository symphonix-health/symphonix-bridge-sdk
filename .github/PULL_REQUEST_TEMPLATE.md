<!--
PR template for caid-agent and (by copy) the twenty-seven BulletTrain repos.
The architecture compliance section enforces the BulletTrain Integration
Constitution. See docs/architecture/bullettrain-integration-constitution.md.
-->

## Summary

<!-- 1-3 bullets on what changed and why -->

## Test plan

<!-- Bulleted markdown checklist of TODOs for testing this PR -->
- [ ]
- [ ]

---

## BulletTrain Integration Architecture Compliance

Required for any PR that touches workflow / orchestration / handler / route / service code in scope (the eleven BulletTrain repos). Skip this section ONLY if the PR is exclusively docs / tests / connector internals / non-BulletTrain code — say so explicitly.

- [ ] Does this workflow call any external system?
- [ ] If yes, does it use the BulletTrain Integration Engine? (`from bullettrain.connectors import get_connector`)
- [ ] Are all external APIs wrapped by approved connectors registered in `connectors/manifests/`?
- [ ] Are schemas validated through the Schema Mediator (no vendor-shape dict subscripts in workflow files)?
- [ ] Are audit logs generated (`audit_log` / `AuditEvent` / `HealthcareAuditTrail` present in the enclosing function of every external interaction)?
- [ ] Are trace IDs propagated (correlation_id passed through every connector exchange)?
- [ ] Are retries, timeouts and errors handled by the integration layer (no `for attempt in range(N)` with `sleep` around HTTP in workflow code)?
- [ ] Are there any hardcoded external URLs? (must be **No** — endpoints come from connector manifests)
- [ ] Are there any external SDKs (`twilio`, `stripe`, `openai`, `anthropic`, `boto3`, `sendgrid`, `slack_sdk`, `google.cloud`, `azure`, `salesforce`) in orchestration code? (must be **No** — SDKs only in `connectors/`)
- [ ] Are secrets handled only through approved secret management (`get_secret(...)`, not literal `Bearer …` or `sk-…`)?
- [ ] Has an ADR been added or updated where needed (`docs/architecture/architecture-decision-records/`)?

If ANY answer above is wrong, the PR is rejected per constitution rule 7. The author moves the call into a connector before re-requesting review.

If a temporary bypass is genuinely required, link the exception ADR (status: Proposed, expiry date set, owner named) below — without an ADR, the bypass is invalid:

- Exception ADR: <link>
