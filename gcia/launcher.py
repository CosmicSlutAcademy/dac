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
