"""GCIAu — regulatory branch: policies, checklists, threat briefings."""

import datetime
import json


THEMES = {
    "phishing": "Social engineering & phishing awareness: verify sender identity, never click "
                "unexpected links, use a password manager, enable 2FA on every account.",
    "deepfake": "Deepfake/media authenticity: treat high-stakes voice/video requests as untrusted "
                "until verified out-of-band; keep a family code word.",
    "device": "Endpoint hardening: keep OS updated, lock screen immediately, disable unknown-sources "
              "installs, review app permissions quarterly.",
    "network": "Network hygiene: change default router credentials, use WPA2/WPA3, segment IoT "
               "devices, disable UPnP, rotate admin passwords.",
    "data": "Data sovereignty: back up critical files offline, encrypt sensitive files, minimize "
            "cloud exposure, audit sharing links monthly.",
}


def briefing(theme="device"):
    return {
        "agency": "GCIAu — Global Cyber Intelligence Authority",
        "generated": datetime.datetime.utcnow().isoformat() + "Z",
        "theme": theme,
        "guidance": THEMES.get(theme, THEMES["device"]),
    }


def checklist(items=None):
    if items is None:
        items = list(THEMES.keys())
    rows = []
    for t in items:
        rows.append({"id": t, "status": "pending", "action": THEMES.get(t, "")})
    return {"checklist": rows, "count": len(rows)}


def export_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path
