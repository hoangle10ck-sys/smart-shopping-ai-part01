---
name: fullstack-debugger
description: Diagnose and fix root causes of bugs across Next.js, TypeScript, FastAPI, SQLAlchemy, external product sources, and frontend-backend integration.
---

# Fullstack Debugger

1. Reproduce the issue when safe and possible.
2. Identify the exact failing layer: frontend, API, business logic, external source, or persistence.
3. Trace the data flow from user input to API response and database persistence.
4. Inspect logs and exceptions without exposing credentials, sensitive URLs, or response bodies.
5. Form a specific root-cause hypothesis and verify it against the code.
6. Implement the smallest reliable fix.
7. Add a regression test.
8. Run the relevant tests in an isolated environment.
9. Check related flows for regressions.

Do not guess that a problem is fixed merely because the application starts.

Do not suppress exceptions, hardcode successful responses, fabricate product data, or bypass validation.

Respect all repository data-protection and Git-safety rules.

Report the root cause, files changed, reproduction steps, verification evidence, and remaining uncertainty.