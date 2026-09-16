"""GCIA CLI — investigation (gcia) and regulatory (gciau) branches."""

import argparse
import json
import sys
from pathlib import Path

from gcia import __version__


def _print(label, value):
    print(f"{label}: {value}")


def cmd_recon(args):
    from gcia.recon import local_ips, sweep, scan_ports, reverse_lookup
    ips = local_ips()
    if not ips:
        print("No private IP found — are you on a network?")
        return 1
    target = args.ip or ips[0]
    print(f"# GCIA Recon on {target}/{args.prefix}")
    print(f"Local addresses: {', '.join(ips)}")
    live = sweep(target, args.prefix)
    print(f"Live hosts ({len(live)}):")
    for h in live:
        name = reverse_lookup(h)
        ports = scan_ports(h) if args.scan else []
        print(f"  {h}  {name}  ports={ports}")
    return 0


def cmd_scan(args):
    from gcia.recon import scan_ports, reverse_lookup
    ports = [int(p) for p in args.ports.split(",")] if args.ports else None
    print(f"# GCIA Port Scan: {args.host}")
    print(f"Open: {scan_ports(args.host, ports)}")
    return 0


def cmd_audit(args):
    from gcia.audit import run_full_audit
    a = run_full_audit()
    print("# GCIA Device Audit")
    for k, v in a.items():
        _print(k, v)
    return 0


def cmd_vault(args):
    from gcia.vault import generate_key, encrypt_file, decrypt_file, checksum
    if args.keygen:
        p = generate_key(args.keygen)
        print(f"Key created: {p} (mode 0600)")
        return 0
    if args.encrypt:
        dst = encrypt_file(args.key, args.encrypt)
        print(f"Encrypted -> {dst}")
        print(f"SHA256: {checksum(args.encrypt)}")
        return 0
    if args.decrypt:
        dst = decrypt_file(args.key, args.decrypt)
        print(f"Decrypted -> {dst}")
        return 0
    print("Use --keygen, --encrypt FILE, or --decrypt FILE")
    return 1


def cmd_brief(args):
    from gcia.policy import briefing, checklist, export_json
    b = briefing(args.theme)
    out = args.output or f"gciau-briefing-{args.theme}.json"
    export_json(b, out)
    print(f"Briefing written: {out}")
    print(b["guidance"])
    if args.checklist:
        c = export_json(checklist(), f"gciau-checklist.json")
        print(f"Checklist: {c}")
    return 0


def cmd_contact_log(args):
    from gcia.contactlog import add_entry, list_entries, stats, export_plain, drop_entry, _GALACTIC_NOTE
    if args.action == "add":
        e = add_entry(args.text, mode=args.mode, mood=args.mood, sleep_h=args.sleep,
                      stress=args.stress, context=args.context, label=args.label,
                      tags=args.tags.split(",") if args.tags else None)
        print(f"Contact logged: {e['id']} [{e['mode']}/{e['label']}]")
        return 0
    if args.action == "list":
        es = list_entries(limit=args.limit)
        if not es:
            print("No contact-log entries yet. Add one with: gcia contact-log add --text \"...\"")
        for e in es:
            print(f"{e['ts']}  {e['id']}  [{e.get('mode')}/{e.get('label')}]  sleep={e.get('sleep_h')} stress={e.get('stress')}")
            if e.get("context"):
                print(f"  context: {e['context']}")
            print(f"  {e['content']}")
        return 0
    if args.action == "stats":
        import json as _json
        print(_json.dumps(stats(), indent=2))
        return 0
    if args.action == "export":
        out = export_plain(args.output)
        print(f"Exported (mode 0600): {out}")
        return 0
    if args.action == "drop":
        ok = drop_entry(args.id)
        print("Removed" if ok else "not found")
        return 0 if ok else 1
    print(_GALACTIC_NOTE)
    return 0


def cmd_guard(args):
    from gcia.guard import guard_scan, format_report
    r = guard_scan(limit=args.limit)
    print(format_report(r))
    return 0


def cmd_deck(args):
    from gcia.deck import serve
    try:
        serve(host=args.host, port=args.port, token=args.token)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_alert(args):
    from gcia.notify import push_alert
    push_alert(args.title, args.message, sound=args.sound)
    return 0


def cmd_patrol(args):
    from gcia.patrol import one_patrol, patrol_loop
    if args.once:
        one_patrol(sound=args.sound)
        return 0
    print(f"GCIA patrol started — audit + alert every {args.interval}h (Ctrl-C to stop)")
    patrol_loop(interval_hours=args.interval, sound=args.sound)
    return 0


def cmd_remote(args):
    from gcia.remote import grant, revoke, peers, remote_audit, remote_scan
    if args.action == "grant":
        a = grant(args.name, args.pubkey)
        print(f"Granted {args.name} (key {a['key_id'][:16]}…): {','.join(a['allowed'])}")
        print("Peer can now SSH in and run only GCIA commands.")
        return 0
    if args.action == "revoke":
        revoke(args.name)
        print(f"Revoked {args.name}")
        return 0
    if args.action == "list":
        ps = peers()
        if not ps:
            print("No peers granted.")
        for name, info in ps.items():
            print(f"  {name}: {info['key_id'][:16]}… allowed={','.join(info['allowed'])}")
        return 0
    if args.action == "audit":
        out = remote_audit(args.user, args.host, args.port, args.key)
        print(out)
        return 0
    if args.action == "scan":
        out = remote_scan(args.user, args.host, args.target, args.port, args.key)
        print(out)
        return 0
    print("Unknown action")
    return 1


def cmd_agent(args):
    from gcia.agent import handle
    return handle(args.original)


def cmd_laptop(args):
    from gcia.laptop import ssh_keypair, start_sshd
    priv, pub = ssh_keypair()
    ok, msg = start_sshd(args.port)
    print("# GCIA Laptop Link")
    print(f"Key: {pub}")
    if ok:
        print(msg)
        print(f"On laptop: ssh -p {args.port} $(whoami)@<device-ip>")
    else:
        print(msg)
    return 0 if ok else 1


def build_parser():
    p = argparse.ArgumentParser(prog="gcia", description="GCIA — ethical investigation CLI")
    p.add_argument("-V", "--version", action="version", version=f"gcia {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("recon", help="sweep local network for live hosts")
    r.add_argument("--ip", default=None)
    r.add_argument("--prefix", type=int, default=24)
    r.add_argument("--scan", action="store_true", help="also port-scan each host")
    r.set_defaults(func=cmd_recon)

    s = sub.add_parser("scan", help="port-scan one host")
    s.add_argument("host")
    s.add_argument("--ports", default=None)
    s.set_defaults(func=cmd_scan)

    a = sub.add_parser("audit", help="device security posture")
    a.set_defaults(func=cmd_audit)

    v = sub.add_parser("vault", help="AES-256-GCM encrypt/decrypt (quantum-resilient)")
    v.add_argument("--keygen", metavar="PATH")
    v.add_argument("--key", default=str(Path.home() / ".gcia" / "vault.key"))
    v.add_argument("--encrypt", metavar="FILE")
    v.add_argument("--decrypt", metavar="FILE")
    v.set_defaults(func=cmd_vault)

    b = sub.add_parser("brief", help="GCIAu policy briefing + checklist")
    b.add_argument("--theme", default="device", choices=["phishing", "deepfake", "device", "network", "data"])
    b.add_argument("--output", default=None)
    b.add_argument("--checklist", action="store_true")
    b.set_defaults(func=cmd_brief)

    cl = sub.add_parser("contact-log", help="encrypted mind-layer evidence journal (GCIA)")
    cla = cl.add_subparsers(dest="action", required=True)
    cl_add = cla.add_parser("add", help="append an encrypted entry")
    cl_add.add_argument("--text", required=True)
    cl_add.add_argument("--mode", default="awake", choices=["awake", "dream", "hypnagogic", "meditation", "other"])
    cl_add.add_argument("--mood", default="calm", choices=["calm", "neutral", "focused", "anxious", "overwhelmed", "euphoric", "other"])
    cl_add.add_argument("--sleep", type=float, default=None, help="hours slept (0-24)")
    cl_add.add_argument("--stress", type=int, default=None, help="stress 1-10")
    cl_add.add_argument("--context", default="")
    cl_add.add_argument("--label", default="speculative", choices=["speculative", "insight", "dream", "distress", "memory", "other"])
    cl_add.add_argument("--tags", default=None, help="comma-separated tags")
    cl_add.set_defaults(func=cmd_contact_log)
    cl_list = cla.add_parser("list", help="decrypt and show recent entries")
    cl_list.add_argument("--limit", type=int, default=10)
    cl_list.set_defaults(func=cmd_contact_log)
    cl_stats = cla.add_parser("stats", help="journal statistics")
    cl_stats.set_defaults(func=cmd_contact_log)
    cl_exp = cla.add_parser("export", help="export plaintext journal")
    cl_exp.add_argument("--output", required=True)
    cl_exp.set_defaults(func=cmd_contact_log)
    cl_drop = cla.add_parser("drop", help="remove one entry by id")
    cl_drop.add_argument("id")
    cl_drop.set_defaults(func=cmd_contact_log)

    gu = sub.add_parser("guard", help="mindguard predictive care scan (GCIAu)")
    gu.add_argument("--limit", type=int, default=30)
    gu.set_defaults(func=cmd_guard)

    dk = sub.add_parser("deck", help="GCI Command Deck web UI (GCIA + GCIAu)")
    dk.add_argument("--host", default="127.0.0.1")
    dk.add_argument("--port", type=int, default=8890)
    dk.add_argument("--token", default=None, help="required when exposing on LAN")
    dk.set_defaults(func=cmd_deck)

    al = sub.add_parser("alert", help="push a notification to this phone")
    al.add_argument("--title", default="GCIA")
    al.add_argument("--message", required=True)
    al.add_argument("--sound", action="store_true", help="also speak the alert")
    al.set_defaults(func=cmd_alert)

    pt = sub.add_parser("patrol", help="periodic audit + phone alerts")
    pt.add_argument("--interval", type=float, default=2, help="hours between patrols")
    pt.add_argument("--once", action="store_true", help="run one audit then exit")
    pt.add_argument("--sound", action="store_true")
    pt.set_defaults(func=cmd_patrol)

    r = sub.add_parser("remote", help="auth-granted remote modes (Wardencliffe Towers)")
    ra = r.add_subparsers(dest="action", required=True)
    rg = ra.add_parser("grant", help="authorize a peer (laptop) key")
    rg.add_argument("name")
    rg.add_argument("pubkey", help="path to the peer's .pub file")
    rg.set_defaults(func=cmd_remote)
    rr = ra.add_parser("revoke", help="remove a peer")
    rr.add_argument("name")
    rr.set_defaults(func=cmd_remote)
    rl = ra.add_parser("list", help="list granted peers")
    rl.set_defaults(func=cmd_remote)
    rra = ra.add_parser("audit", help="run remote audit on a granted peer")
    rra.add_argument("user")
    rra.add_argument("host")
    rra.add_argument("--port", type=int, default=2222)
    rra.add_argument("--key", default=None)
    rra.set_defaults(func=cmd_remote)
    rrs = ra.add_parser("scan", help="run remote scan via a granted peer")
    rrs.add_argument("user")
    rrs.add_argument("host")
    rrs.add_argument("target")
    rrs.add_argument("--port", type=int, default=2222)
    rrs.add_argument("--key", default=None)
    rrs.set_defaults(func=cmd_remote)

    ag = sub.add_parser("agent", help="SSH forced-command handler (internal)")
    ag.add_argument("original", nargs="*", default=None)
    ag.set_defaults(func=cmd_agent)

    l = sub.add_parser("laptop", help="link this device to your laptop via SSH")
    l.add_argument("--port", type=int, default=2222)
    l.set_defaults(func=cmd_laptop)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        print(f"gcia error: {e}", file=sys.stderr)
        return 1


def gciau_main(argv=None):
    """Regulatory executor branch — same CLI, headings tagged GCIAu."""
    return main(argv)


if __name__ == "__main__":
    sys.exit(main())
