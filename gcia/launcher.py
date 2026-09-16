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
    if args.action == "rotate":
        from gcia.contactlog import rotate_key
        r = rotate_key()
        print(f"Rotated: {r['entries']} entries re-encrypted with a fresh key.")
        print(f"Backup kept: {', '.join(r['backup'] or [])}")
        return 0
    if args.action == "backup":
        from gcia.contactlog import backup
        pair = backup()
        print("Backup written:" if pair else "Nothing to back up yet.")
        for p in pair or []:
            print(f"  {p}")
        return 0
    print(_GALACTIC_NOTE)
    return 0


def cmd_telegram(args):
    from gcia.notify import set_telegram, clear_telegram, telegram_alert, telegram_config
    if args.action == "set":
        p = set_telegram(args.token, args.chat_id)
        print(f"Telegram alert config saved: {p} (mode 0600)")
        return 0
    if args.action == "clear":
        print("Cleared" if clear_telegram() else "no config")
        return 0
    if args.action == "test":
        cfg = telegram_config()
        if not cfg.get("chat_id"):
            print("Not configured. Run: gcia telegram set <token> <chat_id>")
            return 1
        ok = telegram_alert("GCIA test", "Telegram alert channel is online.")
        print("sent" if ok else "failed")
        return 0 if ok else 1
    print("use: gcia telegram set <token> <chat_id> | clear | test")
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


def cmd_bvh(args):
    from gcia import bvh
    if args.action == "rules":
        for r in bvh.RULES:
            print(f"{r['id']:8s} {r['verdict']:6s} {r['registry']:12s} {r['why']}")
        return 0
    if args.action == "preview":
        cmd = " ".join(args.command)
        v = bvh.preview(cmd)
        print(f"[{v['verdict'].upper()}] {v['id']} {v['registry']} — {v['why']}")
        return 0 if v["verdict"] == "allow" else 2
    if args.action == "run":
        cmd = " ".join(args.command)
        r = bvh.run(cmd, approve=args.approve, force=args.force)
        print(f"[{r.get('verdict','?').upper()}] {r.get('rule','')} {r.get('registry','')} rc={r.get('rc')}")
        print(r.get("output", r.get("why", "")))
        return 0 if r.get("ok") else 1
    if args.action == "journal":
        for e in bvh.journal(limit=args.limit):
            print(f"{e.get('ts','')[:19]}  {e.get('verdict',''):16s} {e.get('cmd','')[:60]}  rc={e.get('rc')}")
        return 0
    if args.action == "anomaly":
        a = bvh.scan_anomalies()
        print(f"# BVH Anomaly Scan — status: {a['status']} ({a['scanned']} actions)")
        for f in a["findings"]:
            print(f"[{f['level'].upper()}] {f['registry']} {f['signal']}: {f['detail']}")
            print(f"    -> {f['action']}")
        return 0
    return 1


def cmd_registry(args):
    from gcia import registry
    if args.action == "list":
        for r in registry.list_registry():
            print(f"{r['id']:20s} {r['domain']}")
        return 0
    if args.action == "get":
        e = registry.get_entry(args.id)
        if not e:
            print(f"not found: {args.id}")
            return 1
        print(f"{e['id']}: {e['domain']}")
        return 0
    if args.action == "search":
        for r in registry.search(args.text):
            print(f"{r['id']:20s} {r['domain']}")
        return 0
    if args.action == "count":
        print(f"{registry.count()} registered domains (00-99 + {registry.INFINITY})")
        return 0
    return 1


def cmd_legal(args):
    from gcia import legal
    if args.action == "authorize":
        r = legal.authorize(args.client, args.scope, operator=args.operator,
                            date_start=args.start, date_end=args.end)
        print(f"Authorization written: {r['path']}")
        print(f"Attestation SHA-256: {r['hash']}")
        return 0
    if args.action in ("agree", "nda", "consent"):
        r = getattr(legal, args.action)(args.client, operator=args.operator)
        print(f"{args.action}: {r['path']}")
        print(f"sha256: {r['hash']}")
        return 0
    if args.action == "engagements":
        for e in legal.engagements(limit=20):
            print(f"{e.get('ts','')[:19]}  {e.get('kind',''):9s} {e.get('client','')}  {e.get('hash','')[:16]}…")
        return 0
    if args.action == "manifest":
        m = legal.manifest()
        print(f"Evidence manifest: {m['path']}")
        print(f"Chain head: {m['head']} ({m['count']} records)")
        return 0
    print("use: gcia legal authorize|agree|nda|consent|engagements|manifest")
    return 1


def cmd_report(args):
    from gcia.report import generate_report
    r = generate_report(args.client, contact=args.contact, fee=args.fee, out=args.output,
                        pro_bono=args.pro_bono, auth=args.auth)
    if r.get("auth"):
        print(f"Linked authorization: {r['auth']['path']} (attestation {str(r['auth'].get('attestation'))[:16]}…)")
    print(f"Report attestation: {str(r.get('attestation'))[:16]}… | file SHA-256: {r['hash'][:16]}…")
    print(f"Report written: {r['path']}")
    print(f"Client: {r['client']} | suggested fee: ${r['fee']}")
    print(f"BVH status: {r['bvh_status']} | Mindguard: {r['guard_status']}")
    return 0


def cmd_fleet(args):
    from gcia import fleet
    if args.action == "roster":
        for r in fleet.roster():
            print(f"{r['rank'].upper():8s} {r['name']:16s} {r['mission']}")
        return 0
    if args.action == "run":
        r = fleet.run_role(args.role, args=args.args or None, approve=args.approve)
        if not r["ok"]:
            print(f"[{r['role']}] FAILED: {r.get('error', '')}")
            return 1
        print(r.get("output", "") or f"{r['role']} ok")
        return 0
    if args.action == "brief":
        b = fleet.fleet_brief(args.task)
        print(f"# Mission: {args.task}")
        print(f"plan: {', '.join(b['plan'].get('roles', []))} — {b['plan'].get('note','')}")
        for r in b["results"]:
            print(f"[{r['role']}] {'ok' if r['ok'] else 'FAILED'}")
        print("\n" + b["report"])
        print(f"\nmission saved: {b['mission']}")
        return 0
    if args.action == "status":
        s = fleet.fleet_status()
        for k, v in s.items():
            print(f"{k}: {'ONLINE' if v else 'offline'}")
        return 0
    return 1


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
    cl_rot = cla.add_parser("rotate", help="re-encrypt under a fresh key (old material backed up)")
    cl_rot.set_defaults(func=cmd_contact_log)
    cl_bk = cla.add_parser("backup", help="copy encrypted journal + key to ~/.gcia/backups")
    cl_bk.set_defaults(func=cmd_contact_log)

    tg = sub.add_parser("telegram", help="configure off-device alert channel (GCIAu)")
    tga = tg.add_subparsers(dest="action", required=True)
    tgs = tga.add_parser("set", help="save bot token + chat id")
    tgs.add_argument("token")
    tgs.add_argument("chat_id")
    tgs.set_defaults(func=cmd_telegram)
    tgc = tga.add_parser("clear", help="remove saved telegram config")
    tgc.set_defaults(func=cmd_telegram)
    tgt = tga.add_parser("test", help="send a test alert")
    tgt.set_defaults(func=cmd_telegram)

    gu = sub.add_parser("guard", help="mindguard predictive care scan (GCIAu)")
    gu.add_argument("--limit", type=int, default=30)
    gu.set_defaults(func=cmd_guard)

    bh = sub.add_parser("bvh", help="behavior verification harness — make ML behave")
    bha = bh.add_subparsers(dest="action", required=True)
    bh_rules = bha.add_parser("rules", help="list verification rules")
    bh_rules.set_defaults(func=cmd_bvh)
    bh_prev = bha.add_parser("preview", help="sandboxed preview: evaluate without executing")
    bh_prev.add_argument("command", nargs="+")
    bh_prev.set_defaults(func=cmd_bvh)
    bh_run = bha.add_parser("run", help="check, execute (with approval), verify, journal")
    bh_run.add_argument("command", nargs="+")
    bh_run.add_argument("--approve", action="store_true", help="approve a mutating action (Human Authorization)")
    bh_run.add_argument("--force", action="store_true", help="override a deny (operator override)")
    bh_run.set_defaults(func=cmd_bvh)
    bh_j = bha.add_parser("journal", help="show recent verified actions")
    bh_j.add_argument("--limit", type=int, default=20)
    bh_j.set_defaults(func=cmd_bvh)
    bh_an = bha.add_parser("anomaly", help="predictive anomaly scan over the journals")
    bh_an.set_defaults(func=cmd_bvh)

    rg = sub.add_parser("registry", help="§MDH-ATA digital governance registry")
    rga = rg.add_subparsers(dest="action", required=True)
    rg_list = rga.add_parser("list", help="list all domains")
    rg_list.set_defaults(func=cmd_registry)
    rg_get = rga.add_parser("get", help="show one entry by ID (e.g. 07 or -\u221e)")
    rg_get.add_argument("id")
    rg_get.set_defaults(func=cmd_registry)
    rg_sea = rga.add_parser("search", help="search domains by keyword")
    rg_sea.add_argument("text")
    rg_sea.set_defaults(func=cmd_registry)
    rg_cnt = rga.add_parser("count", help="number of registered domains")
    rg_cnt.set_defaults(func=cmd_registry)

    lg = sub.add_parser("legal", help="judicial protection: authorization, agreements, evidence chain")
    lga = lg.add_subparsers(dest="action", required=True)
    lg_auth = lga.add_parser("authorize", help="generate signed written-consent authorization")
    lg_auth.add_argument("client")
    lg_auth.add_argument("--scope", default="", help="exact assets / IP range authorized")
    lg_auth.add_argument("--operator", default="GCI Operator")
    lg_auth.add_argument("--start", default=None)
    lg_auth.add_argument("--end", default=None)
    lg_auth.set_defaults(func=cmd_legal)
    for nm, help_txt in (("agree", "services agreement with liability cap"),
                         ("nda", "mutual non-disclosure agreement"),
                         ("consent", "personal-data processing consent")):
        sp = lga.add_parser(nm, help=help_txt)
        sp.add_argument("client")
        sp.add_argument("--operator", default="GCI Operator")
        sp.set_defaults(func=cmd_legal)
    lg_eng = lga.add_parser("engagements", help="list engagement ledger")
    lg_eng.set_defaults(func=cmd_legal)
    lg_man = lga.add_parser("manifest", help="hash-chain evidence manifest (reports + paperwork)")
    lg_man.set_defaults(func=cmd_legal)

    rp = sub.add_parser("report", help="generate a sellable client security report")
    rp.add_argument("client")
    rp.add_argument("--contact", default="")
    rp.add_argument("--fee", type=int, default=79, help="total line-item fee shown")
    rp.add_argument("--output", default=None, help="output html path")
    rp.add_argument("--pro-bono", action="store_true",
                    help="civilization-safeguard free mode (GCIAu Charter §7), fee $0")
    rp.add_argument("--auth", default=None,
                    help="authorization ref: 'auto' (latest for client), 'latest', hash, or file path")
    rp.set_defaults(func=cmd_report)

    fl = sub.add_parser("fleet", help="principal coder + specialist captain/pilot bots")
    fla = fl.add_subparsers(dest="action", required=True)
    fl_ro = fla.add_parser("roster", help="list all specialists")
    fl_ro.set_defaults(func=cmd_fleet)
    fl_run = fla.add_parser("run", help="execute one specialist through the BVH gate")
    fl_run.add_argument("role")
    fl_run.add_argument("args", nargs="*", default=None)
    fl_run.add_argument("--approve", action="store_true",
                        help="approve mutating actions (Human Authorization §MDH-ATA-57)")
    fl_run.set_defaults(func=cmd_fleet)
    fl_br = fla.add_parser("brief", help="run a mission: principal assigns, pilots execute")
    fl_br.add_argument("task")
    fl_br.set_defaults(func=cmd_fleet)
    fl_st = fla.add_parser("status", help="fleet health: deck, llm, telegram, sshd")
    fl_st.set_defaults(func=cmd_fleet)

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
