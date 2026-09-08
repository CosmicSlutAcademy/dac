"""Price/API monitor — poll public JSON endpoints, alert on threshold moves."""
import json
import time

from dac.config import CONFIG_DIR, load_config
from dac.core.executor import run_cmd

MONITORS_FILE = CONFIG_DIR / "monitors.json"

PRESETS = {
    "BTC": ("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", "bitcoin.usd"),
    "ETH": ("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", "ethereum.usd"),
    "SOL": ("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", "solana.usd"),
    "GOLD": ("https://api.gold-api.com/price/XAU", "price"),
    "SILVER": ("https://api.gold-api.com/price/XAG", "price"),
}


def load_monitors():
    if MONITORS_FILE.exists():
        try:
            return json.load(open(MONITORS_FILE))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_monitors(monitors):
    MONITORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MONITORS_FILE, "w") as f:
        json.dump(monitors, f, indent=2)


def get_json(url, timeout=30):
    """Fetch JSON from a public API (GET). Returns parsed object."""
    import urllib.request
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_value(data, path):
    """Extract value by dot path: 'bitcoin.usd', 'data[0].price'."""
    value = data
    for part in path.split("."):
        if "[" in part and part.endswith("]"):
            key, idx = part.split("[")
            value = value[key][int(idx.rstrip("]"))]
        else:
            value = value[part]
    return float(value)


def pct_change(old, new):
    if not old:
        return None, None
    delta = (new - old) / old * 100
    direction = "UP" if delta > 0 else "DOWN"
    return abs(delta), direction


def alert(title, content):
    from dac.assistant import notify
    notify(title, content, notif_id="dac_monitor")
    print(f"  ⚠ {title}: {content}")


def run_monitor(mon, cfg=None):
    """Run one monitor. Returns (changed_bool, row_str) and updates its state."""
    url, path = mon["url"], mon["path"]
    name = mon["name"]
    interval = int(mon.get("interval", 300))

    # Respect per-monitor interval
    last_run = mon.get("last_run", 0)
    if time.time() - last_run < interval:
        return False, None

    try:
        data = get_json(url)
        price = extract_value(data, path)
    except Exception as e:
        print(f"  {name}: fetch error: {e}")
        return False, None

    mon["last_run"] = int(time.time())
    mon["last_price"] = price
    old = mon.get("prev_price")
    if old is None:
        mon["prev_price"] = price
        row = f"{name}: ${price:,.2f} (baseline)"
        print(f"  {row}")
        return False, row

    abs_delta, direction = pct_change(old, price)
    row = f"{name}: ${price:,.2f} ({old:,.2f} → {price:,.2f})"
    threshold = float(mon.get("threshold", 5.0))
    print(f"  {row}")
    if abs_delta is not None and abs_delta >= threshold:
        alert(f"{name} moved {direction} {abs_delta:.1f}%",
              row)
        return True, row
    return False, row


def run_all(cfg=None, names=None):
    monitors = load_monitors()
    if not monitors:
        print("No monitors configured. Add one: dac monitor --add BTC")
        return []
    changed = []
    for mon in monitors:
        if names and mon["name"] not in names:
            continue
        try:
            is_change, row = run_monitor(mon, cfg)
            if is_change:
                changed.append(mon["name"])
        except Exception as e:
            print(f"  {mon['name']}: {e}")
    save_monitors(monitors)
    return changed


def add_monitor(name, url=None, path=None, threshold=5.0, interval=300):
    if name.upper() in PRESETS and not url:
        url, path = PRESETS[name.upper()]
    if not url or not path:
        raise ValueError("Need --url and --path for custom monitor (or use a preset name like BTC)")
    monitors = load_monitors()
    monitors = [m for m in monitors if m["name"] != name]
    monitors.append({
        "name": name, "url": url, "path": path,
        "threshold": float(threshold), "interval": int(interval),
        "prev_price": None, "last_run": 0,
    })
    save_monitors(monitors)
    return name


def remove_monitor(name):
    monitors = load_monitors()
    kept = [m for m in monitors if m["name"] != name]
    save_monitors(kept)
    return len(monitors) - len(kept)


def list_monitors():
    monitors = load_monitors()
    if not monitors:
        print("No monitors.")
        return
    for m in monitors:
        price = m.get("last_price")
        p = f"${price:,.2f}" if price else "—"
        print(f"  {m['name']:8s} {p:14s} threshold {m.get('threshold')}%  every {m.get('interval')}s")


def main(argv):
    import argparse
    p = argparse.ArgumentParser(prog="dac monitor", description="Price/API monitor")
    p.add_argument("name", nargs="?", help="Monitor to run once (default: all)")
    p.add_argument("--add", metavar="NAME", help="Add monitor (preset: BTC/ETH/SOL/GOLD/SILVER)")
    p.add_argument("--url", help="JSON endpoint for --add")
    p.add_argument("--path", help="Dot path to value, e.g. bitcoin.usd")
    p.add_argument("--threshold", type=float, default=5.0, help="Alert threshold %")
    p.add_argument("--interval", type=int, default=300, help="Poll interval seconds")
    p.add_argument("--list", action="store_true")
    p.add_argument("--remove", metavar="NAME")
    args = p.parse_args(argv)

    if args.list:
        list_monitors()
        return 0
    if args.remove:
        removed = remove_monitor(args.remove)
        print(f"Removed {removed} monitor(s)" if removed else f"No monitor named {args.remove}")
        return 0
    if args.add:
        add_monitor(args.add, args.url, args.path, args.threshold, args.interval)
        print(f"Added monitor: {args.add}")
        list_monitors()
        return 0

    names = [args.name] if args.name else None
    run_all(names=names)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
