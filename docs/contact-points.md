# Contact points

Apero has **one DevOps team**. They own everything operational. If you're not sure who to ping, ping them.

| Topic                                                                                                | Channel             | Email             | Hours      |
|------------------------------------------------------------------------------------------------------|---------------------|-------------------|------------|
| Anything operational — security, leaked secrets, deploys, k8s, infra, secret manager, package mirrors, SSO, MCP servers, this template | **#devops**         | devops@apero.vn   | 24/7 for incidents · business hours otherwise |
| AI assistant / vibecode / how-do-I questions                                                         | **#vibecode-help**  | vibecode@apero.vn | business   |

## Severity decoder

- **Sev 1** — production down, customer-impacting, or active security incident → page **#devops** immediately. Do not wait for business hours.
- **Sev 2** — broken with a workaround → file a ticket in **#devops**.
- **Sev 3** — question, "is this normal?" → ask in **#devops** during business hours, or **#vibecode-help** if it's about the AI / template.

## Found a real secret in a repo?

Treat as **Sev 1** even if you think the repo is private.

1. Do not push more changes.
2. Post in **#devops** with the file path (NOT the secret).
3. Wait for an acknowledgement before continuing.
