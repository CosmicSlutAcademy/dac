"""Network investigation tools — scan the user's own network (permission-gated)."""

import ipaddress
import socket
import subprocess
import concurrent.futures


def local_ips():
    """Return plausible private IPv4s for this host (from all interfaces)."""
    ips = set()
    try:
        out = subprocess.run(
            ["ip", "-4", "addr"], capture_output=True, text=True, timeout=10
        ).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                ip = line.split()[1].split("/")[0]
                if ipaddress.ip_address(ip).is_private:
                    ips.add(ip)
    except Exception:
        pass
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
            s.close()
        except Exception:
            pass
    return sorted(ips)


def ping_host(ip, timeout=1):
    try:
        r = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            capture_output=True, timeout=timeout + 2,
        )
        return r.returncode == 0
    except Exception:
        return False


def sweep(ip, prefix=24, timeout=1):
    """Return live hosts in the same /24 (or given prefix) as ip."""
    net = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
    hosts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        futs = {ex.submit(ping_host, str(h), timeout): str(h) for h in net.hosts()}
        for fut in concurrent.futures.as_completed(futs):
            if fut.result():
                hosts.append(futs[fut])
    return sorted(hosts, key=lambda x: int(ipaddress.ip_address(x)))


def scan_ports(host, ports=None, timeout=0.5):
    """TCP connect scan of common ports. Only scan hosts you own/have permission for."""
    if ports is None:
        ports = [22, 53, 80, 443, 445, 8022, 8080, 8443, 9090, 2222]
    open_ports = []
    def _one(p):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            return p if s.connect_ex((host, p)) == 0 else None
        finally:
            s.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        for result in ex.map(_one, ports):
            if result:
                open_ports.append(result)
    return sorted(open_ports)


def reverse_lookup(ip, timeout=3):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""
