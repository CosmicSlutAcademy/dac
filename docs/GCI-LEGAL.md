# GCI Judicial Protection — legal shield for the ethical services stack

The strongest defense against judicial action is **documented authorization +
scope + consent + evidence discipline**. This layer exists to produce exactly
that on every engagement.

## Workflow — never skip a step

1. **Authorize first.** `gcia legal authorize "Client" --scope "exact assets"`
   — written consent naming the precise scope, window, rules, and operator.
   No work begins without it (the template forces a scope field).
2. **Agree terms.** `gcia legal agree "Client"` — liability capped at fees
   paid, mutual confidentiality, termination, no-guarantee.
3. **NDA.** `gcia legal nda "Client"` for confidential findings.
4. **Consent for personal data.** `gcia legal consent "Client"` when using
   contact-log/mindguard data (access, deletion, export rights baked in).
5. **Document everything.** Every artifact (authorization, agreement, report)
   is SHA-256 hashed into the engagements ledger; `gcia legal manifest`
   builds a hash-chained evidence trail (`prev` links every record).
6. **Stay in scope.** The BVH gate enforces scope mechanically: `deny`
   verdicts stop destructive/exfil commands; `warn` mutations need approval.
   Out-of-scope work is the number one legal exposure — the tools make it
   hard to do by accident.

## What protects you (and what doesn't)

- Written authorization + exact scope = the core defense.
- Liability caps + indemnification + no-guarantee clauses limit exposure.
- Encrypted, hashed evidence = provable chain of custody if disputed.
- Templates are starting points only — **not legal advice**; have counsel in
  your jurisdiction review, and know local data/security laws before selling.
- No paperwork can protect deliberate unauthorized access or harm; the tools
  are designed to make both hard.

## Commands

```bash
gcia legal authorize "Client" --scope "10.0.0.0/24, www.example" --start 2026-10-01 --end 2026-11-01
gcia legal agree "Client" | gcia legal nda "Client" | gcia legal consent "Client"
gcia legal engagements          # ledger of every signed record
gcia legal manifest             # hash-chain evidence manifest
```
