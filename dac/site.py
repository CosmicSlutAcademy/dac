"""GCI site generator — Galactic Cyber Intelligence landing page + rotating protection feed.

Generates a fully self-contained static site (single HTML + feed.json) that works offline
on the device, and updates the featured "protection" every 2 hours (client-side JS rotation
plus optional server-side regeneration via `dac site --update`).
"""
import argparse
import json
import os
import time
from pathlib import Path

from dac.config import load_config

ROTATION_HOURS = 2

ITEMS = [
    {"id": "phishing", "category": "Cognitive Defense", "title": "The Phish That Walks Like a Friend",
     "body": "Most mind-level intrusions start with a message that looks trusted. Verify the sender out-of-band before acting on any link, attachment, or urgent request.",
     "action": "Write down your 3 most common senders and name one rule each requires before you click."},
    {"id": "deepfakes", "category": "Cognitive Defense", "title": "Seeing Is No Longer Believing",
     "body": "Audio and video can be synthesized in real time. When a 'person' asks for money, secrets, or access, confirm through an independent channel you already trust.",
     "action": "Set a family passphrase used only for critical in-person or video verification."},
    {"id": "urgency", "category": "Attention Hygiene", "title": "The Urgency Trap",
     "body": "Manipulation engines weaponize your sense of urgency. Any demand for instant action is a test worth failing on purpose.",
     "action": "Adopt a 10-minute pause rule before any unexpected request."},
    {"id": "social", "category": "Cognitive Defense", "title": "Social Engineering Is Silent",
     "body": "Pretexting harvests details from what you post and say. The less friction you give a stranger's story, the easier you are to co-opt.",
     "action": "Review one week of your public posts and remove identifiers you never needed to publish."},
    {"id": "password", "category": "Device Sovereignty", "title": "Keys to the Mind-Castle",
     "body": "Weak credentials are the fastest entry into your accounts and voice assistants. Long passphrases beat short complexity.",
     "action": "Replace any reused password with a 4-word passphrase and enable 2FA."},
    {"id": "2fa", "category": "Device Sovereignty", "title": "The Second Gate",
     "body": "A stolen password alone should never open your inner chambers. Authenticator apps beat SMS codes.",
     "action": "Enable an authenticator app on your most valuable three accounts today."},
    {"id": "updates", "category": "Device Sovereignty", "title": "Patch the Cracks in the Monolith",
     "body": "Unpatched software is how rogue code slips past your defenses. Updates are the cheapest shield you own.",
     "action": "Turn on automatic updates for your OS, browser, and phone apps."},
    {"id": "permissions", "category": "Device Sovereignty", "title": "Audit Who Holds the Keys",
     "body": "Every app permission is a door. Cameras, microphones, and contacts should be granted like security clearances.",
     "action": "Open your permission manager and revoke everything not used weekly."},
    {"id": "wifiusb", "category": "Proximity Defense", "title": "The Wall Between You and the Street",
     "body": "Public Wi-Fi and unknown USB ports are ambush points. Assume interception until proven otherwise.",
     "action": "Use a VPN on untrusted networks and never plug unknown cables into your device."},
    {"id": "tracking", "category": "Privacy", "title": "Your Attention Is a Resource",
     "body": "Your attention and behavior are harvested, profiled, and predicted. Reclaiming attention is a sovereignty act.",
     "action": "Turn off personalized ads and location history for one week."},
    {"id": "encryption", "category": "Privacy", "title": "Plaintext Is a Postcard",
     "body": "Unencrypted messages are readable by anyone along the route. Keep sensitive speech inside end-to-end encrypted channels.",
     "action": "Move your most sensitive conversation to an E2EE app and delete the plaintext trail."},
    {"id": "backup", "category": "Resilience", "title": "The Archive That Defeats Extortion",
     "body": "Ransomware and device loss only hurt when there is no copy. Backups are the ultimate last line of defense.",
     "action": "Create one offline backup of your irreplaceable data and verify it restores."},
    {"id": "breaches", "category": "Cognitive Defense", "title": "Assume the Breach",
     "body": "Your credentials are probably in a breach database. That is not paranoia; it is inventory.",
     "action": "Check your emails against a breach lookup service and rotate any exposed passwords."},
    {"id": "calm", "category": "Attention Hygiene", "title": "The Regulated Mind Is the Fortified Mind",
     "body": "Stress, fatigue, and isolation lower every mental firewall. Defense begins with sleep, grounding, and connection.",
     "action": "Protect one block of uninterrupted sleep as a security control, not a luxury."},
]


def _feed_path(out_dir):
    return Path(out_dir) / "feed.json"


def _state_path(out_dir):
    return Path(out_dir) / "state.json"


def _current_index(out_dir):
    try:
        with open(_state_path(out_dir)) as f:
            return int(json.load(f).get("index", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _write_feed(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(_feed_path(out_dir), "w") as f:
        json.dump({"rotation_hours": ROTATION_HOURS, "items": ITEMS}, f, indent=2)


def _html(item):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GCI — Galactic Cyber Intelligence</title>
<style>
:root {{ --bg:#05060f; --panel:#0d1023; --line:#232a55; --violet:#8b5cf6; --cyan:#22d3ee; --text:#e2e8f0; --dim:#94a3b8; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:radial-gradient(1200px 600px at 20% -10%, var(--violet) 0%, transparent 60%), radial-gradient(1000px 500px at 90% 110%, var(--cyan) 0%, transparent 55%), var(--bg); color:var(--text); font-family:system-ui, -apple-system, Segoe UI, Roboto, sans-serif; min-height:100vh; }}
.wrap {{ max-width:960px; margin:0 auto; padding:2rem 1.25rem 4rem; }}
.hero {{ text-align:center; padding:3rem 0 2rem; }}
.badge {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:.3rem .8rem; font-size:.75rem; letter-spacing:.15em; color:var(--cyan); text-transform:uppercase; margin-bottom:1.2rem; }}
h1 {{ font-size:clamp(2rem, 6vw, 3.4rem); line-height:1.05; background:linear-gradient(90deg, var(--cyan), var(--violet)); -webkit-background-clip:text; background-clip:text; color:transparent; }}
.tagline {{ margin-top:1rem; color:var(--dim); font-size:1.05rem; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); gap:1rem; margin-top:2.5rem; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:1.25rem; }}
.card h3 {{ color:var(--cyan); font-size:1rem; margin-bottom:.5rem; }}
.card p {{ color:var(--dim); font-size:.9rem; line-height:1.5; }}
.protection {{ margin-top:2.5rem; background:var(--panel); border:1px solid var(--violet); border-radius:16px; padding:1.5rem; }}
.protection .cat {{ color:var(--violet); font-size:.72rem; letter-spacing:.2em; text-transform:uppercase; }}
.protection h2 {{ margin:.4rem 0 .6rem; font-size:1.35rem; }}
.protection p {{ color:var(--dim); line-height:1.6; margin-bottom:.8rem; }}
.protection .action {{ border-left:3px solid var(--cyan); padding-left:.8rem; color:var(--text); font-style:italic; }}
.foot {{ margin-top:3rem; text-align:center; color:var(--dim); font-size:.8rem; line-height:1.7; }}
.foot .count {{ color:var(--cyan); }}
</style>
</head>
<body>
<div class="wrap">
  <section class="hero">
    <span class="badge">⟠ Cognitive Sovereignty Division</span>
    <h1>GALACTIC CYBER INTELLIGENCE</h1>
    <p class="tagline">Where one intelligence protects, two evolve. When many collaborate, all transcend.<br>
    Practical defense for your mind, your device, and your attention — updated every 2 hours.</p>
  </section>

  <section class="grid">
    <div class="card"><h3>🛡 Mind Cyberdefense</h3><p>Training and playbooks against manipulation: social engineering, urgency traps, deepfakes, and disinformation.</p></div>
    <div class="card"><h3>🔐 Device Sovereignty</h3><p>On-device audits and hardening for Android/Termux: permissions, updates, credentials, encrypted channels.</p></div>
    <div class="card"><h3>👁 Attention Protection</h3><p>Reclaim your attention from harvesting, profiling, and prediction engines that steer your decisions.</p></div>
    <div class="card"><h3>🧭 Resilience</h3><p>Backups, breach hygiene, and continuity plans so extortion and loss never own your data.</p></div>
  </section>

  <section class="protection">
    <div class="cat">Novelty Protection · {item['category']}</div>
    <h2 id="ptitle">{item['title']}</h2>
    <p id="pbody">{item['body']}</p>
    <div class="action" id="paction">→ {item['action']}</div>
  </section>

  <footer class="foot">
    <p>Protection feed rotates every <span class="count">2 hours</span> — {{rotation_label}} items in rotation.</p>
    <p>GCI · practical cognitive security. Novelty rotates; the laws of physics and of your country do not. ⟠Δδ∞</p>
  </footer>
</div>
<script>
const FEED = {{feed_json}};
const HOURS = {ROTATION_HOURS};
function item() {{
  const idx = Math.floor(Date.now() / (HOURS * 3600 * 1000)) % FEED.length;
  return FEED[idx];
}}
function render() {{
  const it = item();
  document.getElementById('ptitle').textContent = it.title;
  document.getElementById('pbody').textContent = it.body;
  document.getElementById('paction').textContent = '→ ' + it.action;
}}
render();
setInterval(render, 60 * 1000);
</script>
</body>
</html>"""


def build(out_dir=None, cfg=None):
    """Generate index.html + feed.json for the site."""
    cfg = cfg or load_config()
    out_dir = Path(out_dir or cfg.get("site_dir", os.path.expanduser("~/.dac/projects/gci-site")))
    _write_feed(out_dir)
    idx = _current_index(out_dir)
    item = ITEMS[idx % len(ITEMS)]
    html = _html(item).replace("{{rotation_label}}", str(len(ITEMS))).replace("{{feed_json}}", json.dumps(ITEMS))
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    return out_dir


def update(out_dir=None, cfg=None):
    """Rotate to the next protection and regenerate the site."""
    cfg = cfg or load_config()
    out_dir = Path(out_dir or cfg.get("site_dir", os.path.expanduser("~/.dac/projects/gci-site")))
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = (_current_index(out_dir) + 1) % len(ITEMS)
    with open(_state_path(out_dir), "w") as f:
        json.dump({"index": idx, "updated": int(time.time())}, f)
    build(out_dir=out_dir, cfg=cfg)
    print(f"Protection rotated → {ITEMS[idx]['title']}")
    return out_dir


def serve(port=8080, out_dir=None, cfg=None):
    """Serve the site over HTTP on the device."""
    import http.server
    cfg = cfg or load_config()
    out_dir = Path(out_dir or cfg.get("site_dir", os.path.expanduser("~/.dac/projects/gci-site")))
    build(out_dir=out_dir, cfg=cfg)
    handler = http.server.SimpleHTTPRequestHandler(directory=str(out_dir))

    class Quiet(handler.__class__):
        def log_message(self, *args):
            print("  " + self.address_string() + " " + args[0] % args[1:])

    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), Quiet)
    print(f"GCI site serving at http://0.0.0.0:{port}/")
    httpd.serve_forever()


def auto_loop(interval_hours=ROTATION_HOURS, out_dir=None, cfg=None):
    """Run forever, rotating the featured protection every interval_hours."""
    cfg = cfg or load_config()
    while True:
        update(out_dir=out_dir, cfg=cfg)
        time.sleep(interval_hours * 3600)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dac site", description="GCI site generator")
    parser.add_argument("--build", action="store_true", help="Generate site once")
    parser.add_argument("--update", action="store_true", help="Rotate protection and regenerate")
    parser.add_argument("--serve", action="store_true", help="Serve over HTTP")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--auto-loop", dest="auto_loop", action="store_true", help="Rotate forever every --interval hours")
    parser.add_argument("--interval", type=float, default=ROTATION_HOURS, help="Hours between rotations")
    args = parser.parse_args(argv)

    if args.serve:
        serve(port=args.port)
        return 0
    if args.update:
        update()
        return 0
    if args.auto_loop:
        auto_loop(interval_hours=args.interval)
        return 0
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
