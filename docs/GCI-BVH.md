# GCI Behavior Verification Harness (BVH)

Makes agents/pilots *behave*: every command is previewed against a rule map
keyed to the §MDH-ATA governance registry before execution.

## Commands
```bash
gcia bvh rules            # list rules (registry-linked verdicts)
gcia bvh preview "rm -rf /"    # sandboxed preview, no execution
gcia bvh run "gcia audit"      # check -> execute -> verify -> journal
gcia bvh run "git push ..." --approve   # operator approval for mutations
gcia bvh journal            # recent verified actions
gcia bvh anomaly            # predictive anomaly scan (containment, mutations,
                            # failures, emergent patterns, remote pressure)
```

## Model
- `allow` — read-only/investigation: executes.
- `warn` — mutation/network: requires `--approve` (Human Authorization §MDH-ATA-57).
- `deny` — destructive/exfil/unsafe: fails closed, never executes (`--force` is
  the operator override, journaled).
- Unknown patterns are `warn` by default (emergent behavior §MDH-ATA-38).

Patrol runs the anomaly scan each cycle; the deck has a BVH card under GCIAu.
Journal: `~/.gcia/bvh-journal.jsonl` (append-only, mode 0600).
