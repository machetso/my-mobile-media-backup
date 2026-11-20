"""Is a known phone near? (user request 2026-11-17) No Qt here.

Three ways, all only DETECT the phone – nothing is copied and nothing is switched on:

1. Same Wi-Fi: whenever a phone is connected over Wi-Fi (Wireless debugging or the phone app) its
   address and hardware (MAC) address are remembered (cfg["presence_wifi"]). Later a single UDP
   packet to that address makes the computer ask the network "who has it?" (ARP); if the phone with
   the same hardware address answers, it is in the Wi-Fi – also with the screen off.
2. Bluetooth: a phone that is paired with this computer over Bluetooth (system settings) and has the
   name of a known phone is asked for its name (Linux: `hcitool name`, no connection is made). It
   only answers when it is in range (about 10 m).
3. Phone app "Backup requests from the computer" (switched on in the app): the app announces itself
   anonymously in the Wi-Fi (_phonebkpask._tcp, tokens like backup mode). The computer can then ask
   for a backup (send_ask); the phone shows "Allow backup?".

A found phone: {"name", "how": "wifi"|"bluetooth"|"app", "entry": paired phone entry or None,
                "ask": "ip:port" when the phone app can be asked,
                "auto": the app allows a backup without asking (one click on the computer),
                "self": the app allows automatic backups (the computer starts them by itself)}.

The phone app also answers "how many photos and videos are new since the last backup?"
(ask_new, user request 2026-11-20) – only a number, no file names.
"""

import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

from . import companion, config

ASK_TYPE = "_phonebkpask._tcp"
ASK_PORT = 47825
_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0


def _run(args, timeout=10):
    return subprocess.run(args, capture_output=True, timeout=timeout, creationflags=_NO_WINDOW)


# =========================================================================== 1. same Wi-Fi

def mac_of(ip):
    """Hardware address of `ip` in the computer's neighbour table ('' if unknown / not answering)."""
    if not ip:
        return ""
    try:
        if sys.platform.startswith("linux"):
            out = _run(["ip", "neigh", "show", ip], timeout=5).stdout.decode("utf-8", "replace")
            m = re.search(r"lladdr\s+([0-9a-f:]{17})\s+(\w+)", out, re.I)
            if m and m.group(2).upper() in ("REACHABLE", "DELAY", "PROBE", "STALE", "PERMANENT"):
                return m.group(1).lower()
            return ""
        out = _run(["arp", "-a", ip], timeout=5).stdout.decode("utf-8", "replace")
        m = re.search(r"([0-9a-f]{2}([-:])(?:[0-9a-f]{2}\2){4}[0-9a-f]{2})", out, re.I)
        return m.group(1).replace("-", ":").lower() if m else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _poke(ip):
    """One small UDP packet: the computer must find the phone's hardware address (ARP) for it."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(b"\0", (ip, 9))
    except OSError:
        pass


def remember_wifi(cfg, name, address):
    """Called while a phone is connected over Wi-Fi ('ip:port' or 'ip')."""
    ip = str(address or "").rsplit(":", 1)[0] if address and address.count(":") == 1 else str(address or "")
    try:
        socket.inet_aton(ip)
    except OSError:
        return False
    mac = mac_of(ip)
    if not mac:
        return False
    lst = [e for e in cfg.get("presence_wifi", []) if e.get("mac") != mac and e.get("name") != name]
    lst.append({"name": name, "ip": ip, "mac": mac})
    if lst != cfg.get("presence_wifi"):
        cfg["presence_wifi"] = lst
        config.save(cfg)
    return True


def _reachable(ip, mac):
    """Linux: the neighbour entry must be fresh (the phone answered just now)."""
    if sys.platform.startswith("linux"):
        try:
            out = _run(["ip", "neigh", "show", ip], timeout=5).stdout.decode("utf-8", "replace")
        except (OSError, subprocess.SubprocessError):
            return False
        m = re.search(r"lladdr\s+([0-9a-f:]{17})\s+(\w+)", out, re.I)
        return bool(m) and m.group(1).lower() == mac and m.group(2).upper() in ("REACHABLE", "DELAY")
    return mac_of(ip) == mac


def check_wifi(cfg, wait=1.5):
    """Remembered phones that answer in the Wi-Fi right now: [name]."""
    entries = list(cfg.get("presence_wifi", []))
    if not entries:
        return []
    for e in entries:
        _poke(e["ip"])
    time.sleep(wait)
    found = []
    for e in entries:
        for _ in range(2):
            if _reachable(e["ip"], e["mac"]):
                found.append(e["name"])
                break
            _poke(e["ip"])
            time.sleep(wait)
    return found


# =========================================================================== 2. Bluetooth

# ---- Windows (user request 2026-11-20: the same functions as on Linux) – Windows' own interfaces
_WIN_PAIRED = r"""
Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | ForEach-Object { $_.InstanceId + [char]9 + $_.FriendlyName }
"""
_WIN_NEAR = r"""
$null = [Windows.Devices.Bluetooth.BluetoothDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
$null = [Windows.Devices.Bluetooth.Rfcomm.RfcommDeviceServicesResult,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
$d = AwaitOp ([Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync([uint64]$env:PB_ADDR)) ([Windows.Devices.Bluetooth.BluetoothDevice])
if ($d -eq $null) { 'NONE'; exit 0 }
$r = AwaitOp ($d.GetRfcommServicesAsync([Windows.Devices.Bluetooth.BluetoothCacheMode]::Uncached)) ([Windows.Devices.Bluetooth.Rfcomm.RfcommDeviceServicesResult])
'ERROR ' + [string]$r.Error + ' ' + $r.Services.Count
"""


def _win_paired_bluetooth(text=None):
    """[(address 'AA:BB:…', name)] from Windows' device list ("BTHENUM\\DEV_A0B1C2D3E4F5…")."""
    if text is None:
        from . import winps
        try:
            _code, text = winps.run(_WIN_PAIRED, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return []
    out = []
    for ln in text.splitlines():
        inst, _tab, name = ln.strip().partition("\t")
        m = re.search(r"DEV_([0-9A-F]{12})", inst, re.I)
        if m and name.strip():
            a = m.group(1).upper()
            addr = ":".join(a[i:i + 2] for i in range(0, 12, 2))
            if all(addr != x for x, _n in out):
                out.append((addr, name.strip()))
    return out


def _win_bluetooth_near(addr):
    """The phone answers a service query that is not taken from the cache – only when it is in range
    with Bluetooth on (like Linux's name request). No connection to an app is made."""
    from . import winps
    try:
        _code, out = winps.run(_WIN_NEAR, {"PB_ADDR": int(addr.replace(":", ""), 16)}, timeout=30)
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    return out.splitlines()[-1].startswith("ERROR Success") if out else False


def paired_bluetooth():
    """[(address, name)] of the devices paired with this computer over Bluetooth (Linux, Windows)."""
    if sys.platform.startswith("win"):
        return _win_paired_bluetooth()
    if not sys.platform.startswith("linux") or not companion.shutil_which("bluetoothctl"):
        return []
    try:
        out = _run(["bluetoothctl", "devices", "Paired"], timeout=5).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return []
    return re.findall(r"^Device\s+([0-9A-F:]{17})\s+(.+?)\s*$", out, re.M | re.I)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").casefold())


def bluetooth_candidates(names, paired=None):
    """{phone name: bluetooth address} for paired Bluetooth devices whose name contains the name of
    a known phone ("Pixel 10 Pro" matches "Sam's Pixel 10 Pro")."""
    out = {}
    for addr, bt_name in (paired_bluetooth() if paired is None else paired):
        for n in names:
            if _norm(n) and _norm(n) in _norm(bt_name):
                out.setdefault(n, addr)
    return out


def bluetooth_near(addr):
    """True if the device answers a name request (in range, Bluetooth on). No connection is made."""
    if sys.platform.startswith("win"):
        return _win_bluetooth_near(addr)
    if not companion.shutil_which("hcitool"):
        return False
    try:
        r = _run(["hcitool", "name", addr], timeout=12)
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(r.stdout.strip())


def check_bluetooth(names):
    return [n for n, addr in bluetooth_candidates(names).items() if bluetooth_near(addr)]


def bluetooth_possible():
    if sys.platform.startswith("win"):
        return True
    return sys.platform.startswith("linux") and bool(companion.shutil_which("hcitool"))


# =========================================================================== 3. phone app asks

def ask_proof(secret, pc_id, nonce, expiry, auto=False):
    msg = f"fmb-ask:{pc_id}:{nonce}:{expiry}" + (":auto" if auto else "")
    return companion._hmac(secret, msg)[:16].hex()


def check_app(cfg):
    """Paired phones whose app waits for backup requests:
    [(entry, 'ip:port', allowed without asking, also starts by itself)]."""
    entries = companion.phones(cfg)
    if not entries:
        return []
    found = []
    for txt, addr in companion.discover(service_type=ASK_TYPE):
        try:
            tokens = [bytes.fromhex(t) for t in txt.get("t", "").split(".") if t]
        except ValueError:
            continue
        hit = companion.match_token(entries, tokens)
        if hit and all(hit is not f[0] for f in found):
            allow = txt.get("a") == "1"
            # app before 0.9.9.0 (v=1): "Automatic backup" meant both
            by_itself = txt.get("s") == "1" if txt.get("v", "1") != "1" else allow
            found.append((hit, addr, allow, by_itself))
    return found


def new_proof(secret, pc_id, nonce, expiry, since, folders, ready=""):
    msg = f"fmb-new:{pc_id}:{nonce}:{expiry}:{int(since)}:" + "|".join(folders) + f":{ready}"
    return companion._hmac(secret, msg)[:16].hex()


def ask_new(cfg, entry, address, since, folders, ready="", timeout=6):
    """How many photos and videos came onto the phone (into `folders`) after `since` (unix s)?
    ready = can this computer start a backup of it ("" yes, "no_backup", "no_drive", "busy") – the
    phone shows it at its "Back up now" button (user request 2026-11-20).
    Returns (photos, videos, bytes), or None when the phone cannot tell (no access / old app / no answer)."""
    pc_id, _name = companion.pc_identity(cfg)
    nonce = secrets.token_hex(8)
    expiry = int(time.time()) + 300
    folders = [str(f).strip("/") for f in folders if str(f).strip("/")]
    body = json.dumps({"pc": pc_id, "n": nonce, "e": expiry, "s": int(since), "f": folders, "r": ready,
                       "p": new_proof(entry["secret"], pc_id, nonce, expiry, since, folders, ready)}).encode()
    req = urllib.request.Request(f"http://{address}/new", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as r:
            ans = json.loads(r.read(4096).decode("utf-8") or "{}")
    except (OSError, ValueError):
        return None
    return counts_of(ans)


def counts_of(ans):
    """(photos, videos, bytes) from the phone app's answer, or None (unknown / no access).
    bytes is None for a phone app that does not send the size."""
    p, v, b = ans.get("photos"), ans.get("videos"), ans.get("bytes")
    if isinstance(p, int) and isinstance(v, int) and p >= 0 and v >= 0:
        return p, v, (b if isinstance(b, int) and b >= 0 else None)
    return None


def send_ask(cfg, entry, address, timeout=8, auto=False):
    """Ask the phone for a backup: 'asked' (the phone shows "Allow backup?"), 'running' (backup
    mode is already on); auto=True (automatic backup): 'started' (backup mode switched on without a
    tap) or 'not_auto' (automatic backup is off on the phone – nothing shown there).
    Raises OSError / ValueError if the phone does not accept it."""
    pc_id, _name = companion.pc_identity(cfg)
    nonce = secrets.token_hex(8)
    expiry = int(time.time()) + 300
    body = json.dumps({"pc": pc_id, "n": nonce, "e": expiry, "auto": bool(auto),
                       "p": ask_proof(entry["secret"], pc_id, nonce, expiry, auto)}).encode()
    req = urllib.request.Request(f"http://{address}/ask", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # local network: no proxy
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read(4096).decode("utf-8") or "{}").get("state", "asked")


# =========================================================================== automatic backup

AUTO_EVERY_S = 3600       # at most one automatic backup per phone and hour (user choice 2026-11-17)


def auto_phones(cfg):
    """Phones whose app allows automatic backup (seen in its announcement): {name: last seen}."""
    return dict(cfg.get("auto_phones") or {})


def note_auto(cfg, name, on):
    lst = auto_phones(cfg)
    if on and name not in lst:
        lst[name] = int(time.time())
    elif not on and name in lst:
        lst.pop(name)
    else:
        return
    cfg["auto_phones"] = lst
    config.save(cfg)


def auto_due(cfg, name, now=None):
    """May an automatic backup of this phone start now? (last automatic try at least an hour ago)"""
    now = time.time() if now is None else now
    return now - float((cfg.get("auto_last") or {}).get(name, 0)) >= AUTO_EVERY_S


def auto_started(cfg, name, now=None):
    cfg.setdefault("auto_last", {})[name] = int(time.time() if now is None else now)
    config.save(cfg)


# =========================================================================== all together

def known_names(cfg):
    """Names of the phones this computer knows (backups, paired phone app, remembered Wi-Fi)."""
    names = []
    for e in (cfg.get("phones") or {}).values():
        for n in (e.get("model"), e.get("phone")):
            if n and n not in names:
                names.append(n)
    for p in companion.phones(cfg):
        if p.get("name") and p["name"] not in names:
            names.append(p["name"])
    for e in cfg.get("presence_wifi", []):
        if e.get("name") and e["name"] not in names:
            names.append(e["name"])
    return names


def scan(cfg, bluetooth=True):
    """Every way at once (takes a few seconds – run it in a thread). [found phone], app first."""
    found = []

    def add(name, how, entry=None, ask=None, auto=False, by_itself=False):
        for f in found:
            if _norm(f["name"]) == _norm(name):
                if ask and not f.get("ask"):
                    f.update(how=how, entry=entry, ask=ask, auto=auto, self=by_itself)
                return
        found.append({"name": name, "how": how, "entry": entry, "ask": ask, "auto": auto, "self": by_itself})

    for entry, addr, auto, by_itself in check_app(cfg):
        add(entry.get("name") or "Phone", "app", entry, addr, auto, by_itself)
    for name in check_wifi(cfg):
        entry = next((p for p in companion.phones(cfg) if _norm(p.get("name")) == _norm(name)), None)
        ask = None
        if entry:                                  # mDNS blocked? the app may still listen
            ip = next((e["ip"] for e in cfg.get("presence_wifi", []) if e["name"] == name), None)
            if ip and companion._port_open(f"{ip}:{ASK_PORT}", timeout=0.8):
                ask = f"{ip}:{ASK_PORT}"
        on = bool(entry) and name in auto_phones(cfg)
        add(name, "wifi", entry, ask, on, on)
    if bluetooth and os.environ.get("PHONEBACKUP_NO_BLUETOOTH") is None:
        for name in check_bluetooth(known_names(cfg)):
            add(name, "bluetooth")
    return found


KEEP_S = 200        # a phone missing from the searches stays shown this long (about 3 searches)


def keep_seen(seen, found, now=None, keep=KEEP_S):
    """Steady "phone is nearby" line (user report 2026-11-20: it vanished and came back while the
    phone lay next to the computer – Wi-Fi/Bluetooth searches miss a phone now and then).
    seen: {norm name: (last seen, entry)} – updated in place. Returns the phones to show: the ones
    found now, plus the ones found within `keep` seconds (their last result)."""
    now = time.time() if now is None else now
    for f in found:
        seen[_norm(f["name"])] = (now, f)
    for k in [k for k, (t, _) in seen.items() if now - t > keep]:
        seen.pop(k)
    names = {_norm(f["name"]) for f in found}
    return list(found) + [f for k, (t, f) in seen.items() if k not in names]

