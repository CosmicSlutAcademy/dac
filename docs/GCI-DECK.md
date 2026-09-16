# GCI Command Deck — one UI for GCIA + GCIAu

The deck is a single stdlib web app (`gcia deck`). Same code runs on the phone
and the PC, so there is no separate APK vs desktop software — one codebase,
two towers.

## Phone (Termux on Android)

```bash
dac quick "install gcia"          # or: curl -sL https://raw.githubusercontent.com/CosmicSlutAcademy/dac/main/install-dac.sh | bash
gcia deck --port 8890
# open in Termux:  http://127.0.0.1:8890
```

Run it permanently next to the patrol:

```bash
tmux new-session -d -s deck 'gcia deck --port 8890'
```

## PC (Windows 11 via WSL)

1. Install WSL + Ubuntu: `wsl --install -d Ubuntu` (Admin PowerShell), reboot.
2. Inside Ubuntu:
   ```bash
   sudo apt update && sudo apt install -y python3 git curl
   curl -sL https://raw.githubusercontent.com/CosmicSlutAcademy/dac/main/install-dac.sh | bash
   gcia deck --port 8890
   ```
3. Open PowerToys/just browse: the deck prints a URL. From Windows browser use
   `http://127.0.0.1:8890` (WSL2 localhost forwarding works automatically).
   If WSL is WSL1 or forwarding is off, run once in Ubuntu:
   `gcia remote laptop` and check `ip addr` for the WSL IP.

## Linking the two towers

```bash
# on phone: share its SSH key
gcia laptop --port 8023
# on PC (WSL): copy phone ~/.ssh/id_ed25519.pub to a file, then
gcia remote grant phone /path/to/phone.pub
# verify
gcia remote list
gcia remote audit user@<phone-ip> --port 8023
```

Remote peers are forced-command locked: they can only run
`audit, status, brief, recon, scan` from the allowlist (see `gcia agent`).

## Exposing the deck to the other tower (LAN)

Never open it without a token:

```bash
gcia deck --host 0.0.0.0 --port 8890 --token <long-random>
# open from the other tower:  http://<ip>:8890/?token=<long-random>
```

## What's in the UI

- GCIA (cyan): device audit, LAN recon/scan, encrypted contact-log, patrol.
- GCIAu (gold): mindguard predictive care scan, charter, briefings,
  remote peers + agent journal.

## Mind-layer note

The contact-log treats experiences (awake, dream, hypnagogic, meditation) as
honest reports; the `label` field keeps speculation labeled. See
`docs/gciau-charter.md` for the rules both branches operate under.
