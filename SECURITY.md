# Security Policy Template

**Repository:** `symphonix-health/{repo}`  
**Environment:** Development / lab / synthetic-data only  
**Classification:** Non-production  

## Security posture

This repository is part of the Symphonix Health development estate. It contains **synthetic but realistic healthcare data** for design, integration, and assurance work. It is **not** intended to host production patient data or production secrets.

## Reporting security issues

Please report suspected security issues to the Symphonix Health security team. Do not open public issues for undisclosed vulnerabilities.

## Allowed data

- Synthetic personas and seeded records.
- Test/demo keys marked with a `*.QUARANTINE_NOTICE.md`.
- Local SQLite databases used for smoke tests.

## Prohibited data

- Production credentials, tokens, or certificates.
- Real patient identifiable information (PII/PHI).
- Production private keys.
- Unredacted runtime logs or DB dumps.

## Local development

- Use the repo-local `.env.example` for configuration templates.
- Never commit `.env*.local` files.
- Run pre-commit hooks before pushing.

## Compliance

This repository participates in the Symphonix Health SOC 2 readiness programme. Controls, evidence, and exceptions are tracked in `symphonix-assurance/reports/compliance/SOC2_READINESS_SCORECARD.md`.
