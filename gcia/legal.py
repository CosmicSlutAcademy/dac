"""GCI legal shield — paperwork + evidence chain for judicial protection.

Every engagement gets written authorization, scope, consent, liability caps,
and a hash-linked evidence manifest. Templates are starting points: each one
carries a "review by qualified counsel" disclaimer and must be adapted to the
operator's jurisdiction.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path

LEGAL_DIR = Path(os.path.expanduser("~/.gcia/legal"))
LEDGER = LEGAL_DIR / "engagements.jsonl"
REPORTS_DIR = Path(os.path.expanduser("~/.gcia/reports"))

DISCLAIMER = ("*Template only — not legal advice. Have qualified counsel in the "
              "operator's jurisdiction review before use.*")

TEMPLATES = {
    "authorize": """# Authorized Security Engagement — Written Consent

{DISCLAIMER}

**Parties**
- Client / Asset Owner: {client}
- Operator (GCI — GCIA/GCIAu): {operator}
- Date: {date}

**Authorized Scope (exact)**
{scope}

**Engagement Window**
{date_start} → {date_end}

**Authorized Testing Rules**
1. Only the assets listed above, nothing else.
2. No destructive operations; no data exfiltration; no modification of
   third-party systems.
3. No social engineering of individuals not named in scope.
4. Findings and evidence handled confidentially, encrypted, and reported to
   the client owner only.
5. This authorization can be revoked in writing at any time.

**No Guarantee**
The operator provides due diligence and good-faith effort; no warranty or
guarantee of any particular outcome is provided.

**Signatures**
Client / Asset Owner: ______________________   Date: ________
Operator:              ______________________   Date: ________

Attestation (SHA-256): {attestation}
""",
    "agree": """# GCI Security Services Agreement

{DISCLAIMER}

**Parties**: Operator (GCI — GCIA/GCIAu) and Client: {client}
**Date**: {date}

1. **Services.** The operator will perform the authorized services described
   in the statement of work for the client's own environments.
2. **Fees.** As agreed in the statement of work. Pro-bono engagements under
   GCIAu Charter §7 are $0.
3. **Authorization.** Services are performed only within the written
   authorization and scope provided by the client; both parties may revoke.
4. **Confidentiality.** Both parties keep engagement data confidential,
   encrypted at rest, and do not disclose to third parties without written
   consent.
5. **LIMITATION OF LIABILITY.** To the maximum extent permitted by law, the
   operator's aggregate liability is capped at the total fees paid for the
   engagement. Neither party is liable for indirect, incidental, or
   consequential damages.
6. **Indemnification.** The client indemnifies the operator against claims
   arising from the client's own data, misconfiguration, or unauthorized
   changes made by the client.
7. **Data.** Personal data is processed under the client's consent and kept
   on-device, encrypted; an export at any time is guaranteed.
8. **Termination.** Either party may end the engagement on written notice;
   no new work starts after termination.

Signed: ______________________  Client: {client}
Signed: ______________________  Operator: {operator}
""",
    "nda": """# Mutual Non-Disclosure Agreement

{DISCLAIMER}

**Parties**: {client} and Operator (GCI — GCIA/GCIAu). Date: {date}

1. **Purpose.** Exchanging information for a security engagement.
2. **Confidential Information.** Findings, evidence, system details, personal
   data, and any material marked confidential.
3. **Obligations.** Keep confidential information secret, use it only for the
   engagement, and return or destroy it at the end of the engagement.
4. **Term.** 3 years from the engagement end.
5. **Exclusions.** Public information; information independently developed;
   information required to be disclosed by law (with prompt notice).

Signed: ______________________  {client}
Signed: ______________________  {operator}
""",
    "consent": """# Personal Data Processing Consent (Mindguard / Contact-Log)

{DISCLAIMER}

**Data subject**: {client}  **Date**: {date}  **Operator**: {operator}

1. **Purpose.** Recording mind-layer experience entries (sleep, stress,
   context, notes) to provide wellbeing posture checks and evidence discipline.
2. **What is stored.** The encrypted contact-log at ~/.gcia (AES-256-CBC,
   integrity-checked, key mode 0600).
3. **Your rights.** Access, correction, deletion, and full export at any time;
   the journal can be wiped with `gcia contact-log` controls.
4. **No sharing.** Entries are never sold or shared; reports contain only
   aggregate statistics unless separate consent is given.
5. **No clinical claims.** These records are not medical records and are not a
   substitute for professional care.

Signed: ______________________  {client}
""",
}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _ledger(entry):
    LEGAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _write(kind, client, fields):
    LEGAL_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc)
    name = client.replace(" ", "-").lower() or "client"
    path = LEGAL_DIR / f"{kind}-{name}-{ts.strftime('%Y%m%dT%H%M%S')}.md"
    fields = dict(fields, attestation="")
    body = TEMPLATES[kind].format(DISCLAIMER=DISCLAIMER, **fields)
    attest = None
    if kind == "authorize":
        attest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        body = body.replace("Attestation (SHA-256): \n",
                            f"Attestation (SHA-256): {attest}\n")
    path.write_text(body)
    path.chmod(0o600)
    h = _sha256(path)
    _ledger({"ts": _now(), "kind": kind, "client": client, "hash": h,
             "attestation": attest, "path": str(path)})
    return {"path": str(path), "hash": h, "attestation": attest,
            "kind": kind, "client": client}


def authorize(client, scope, operator="GCI Operator", date_start=None, date_end=None):
    date = datetime.date.today().isoformat()
    return _write("authorize", client, {
        "client": client, "operator": operator, "date": date,
        "scope": scope or "(no scope defined — must not begin work!)",
        "date_start": date_start or date, "date_end": date_end or "(TBD)"})


def agree(client, operator="GCI Operator"):
    return _write("agree", client, {"client": client, "operator": operator,
                                    "date": datetime.date.today().isoformat()})


def nda(client, operator="GCI Operator"):
    return _write("nda", client, {"client": client, "operator": operator,
                                  "date": datetime.date.today().isoformat()})


def consent(client, operator="GCI Operator"):
    return _write("consent", client, {"client": client, "operator": operator,
                                      "date": datetime.date.today().isoformat()})


def engagements(limit=20):
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows[-limit:]


def manifest():
    """Hash-chain evidence manifest: authorizations, agreements, reports."""
    LEGAL_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    if LEDGER.exists():
        files += [r["path"] for r in engagements(limit=200) if Path(r["path"]).exists()]
    if REPORTS_DIR.exists():
        files += sorted(str(p) for p in REPORTS_DIR.glob("*.html"))
    files = list(dict.fromkeys(files))
    chain = []
    prev = "GENESIS"
    for f in files:
        h = _sha256(f)
        chain.append({"file": str(f), "sha256": h, "prev": prev, "ts": _now()})
        prev = h
    out = LEGAL_DIR / f"evidence-manifest-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    out.write_text(json.dumps({"head": prev, "count": len(chain), "chain": chain}, indent=2))
    out.chmod(0o600)
    return {"path": str(out), "head": prev, "count": len(chain)}
