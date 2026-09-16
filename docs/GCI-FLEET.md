# GCI Fleet — Principal Coder + Specialist Captain/Pilot Bots

The fleet is the autocoding crew: captains plan and review, pilots execute
inside scoped tool allowlists, and the principal (DAC's local LLM) assigns
missions. It degrades safely: if the principal model is offline, a
deterministic dispatcher runs the same mission.

## Roles

- `captain-core` — Principal Coder: plan, review, decide next iteration.
- `captain-defense` — commands recon/scan/audit/patrol.
- `captain-mindguard` — commands guard/contact-log/telegram (care protocol).
- Pilots: `pilot-recon`, `pilot-scan`, `pilot-audit`, `pilot-patrol`,
  `pilot-guard`, `pilot-brief`, `pilot-contact`, `pilot-code`, `pilot-telegram`.

## Commands

```bash
gcia fleet roster                # list the crew
gcia fleet run pilot-audit       # execute one specialist
gcia fleet run pilot-scan -- args?  # (use --host/--ports style args in brief)
gcia fleet brief "protect the network and check wellbeing"   # full mission
gcia fleet status                # deck/llm/telegram/sshd health
```

`fleet brief` prints the mission plan, per-pilot results, the synthesized
report, and saves it to `~/.gcia/fleet/mission-<ts>.md` (mode 0600).

## BVH gate

Every pilot action routes through the Behavior Verification Harness
(`docs/GCI-BVH.md`): preview rules → execute → verify → journal.

- `allow` actions run immediately (investigation tools).
- `warn` actions (mutations, `dac quick`, network) are blocked unless you
  approve them: `gcia fleet run <role> <args> --approve`.
- `deny` actions fail closed and never execute from the fleet.
- `fleet brief` missions run fail-closed (no auto-approvals): blocked actions
  appear in the mission report, and you rerun them with an explicit `--approve`.

## Rules

- Captains never execute tools directly — they assign.
- Pilots are allowlisted: one role, one tool family, bounded timeouts.
- `pilot-code` runs `dac quick <task>` — the autonomous coding executor.
- Every mission is journaled; nothing runs without a task from the operator
  or the principal.
