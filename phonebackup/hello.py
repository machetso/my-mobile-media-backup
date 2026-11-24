"""The phone checks in (battery-saving backup requests, user request 2026-11-23).

Nothing listens on the phone any more. When Android wakes the phone app (home Wi-Fi joined,
charging, every 30 minutes) it sends a short signed UDP message to this computer (broadcast in the
Wi-Fi and to the last address). Only a paired phone can sign it; only this computer – it knows the
pairing key – can sign the answer. The answer says whether a backup is wanted now; the phone then
opens backup mode ("Allow without asking") or asks its user ("Ask me").

    phone → computer, UDP port 47826:
      {"v":1, "ph": phone id, "pc": computer id, "n": nonce (16 hex), "t": unix s, "m": "ask"|"auto",
       "w": number of home Wi-Fis, "b": 1 = battery unrestricted, "av": app version,
       "p": HMAC-SHA256(secret, "fmb-hello:<ph>:<pc>:<n>:<t>:<m>:<w>:<b>")[:16] hex}
    computer → phone:
      {"pc", "n", "want": true|false, "p": HMAC-SHA256(secret, "fmb-hello-ok:<ph>:<pc>:<n>:<want>")[:16] hex}

Version 2 (user request 2026-11-24: the computer must see the phone in ANY Wi-Fi, e.g. the office,
not only in a trusted one): the phone checks in everywhere, so the message must not identify it –
no phone id, no computer id, no app version. Only a computer that knows a pairing key recognises it:

    phone → computer, UDP port 47826:
      {"v":2, "k": HMAC-SHA256(secret, "fmb-hello-id:<n>")[:8] hex (new with every nonce),
       "n": nonce (16 hex), "t": unix s, "m": "ask"|"auto", "w": number of trusted Wi-Fis,
       "b": 1 = battery unrestricted, "h": 1 = the phone is in one of its trusted Wi-Fis,
       "p": HMAC-SHA256(secret, "fmb-hello2:<k>:<n>:<t>:<m>:<w>:<b>:<h>")[:16] hex}
    computer → phone:
      {"v":2, "n", "want": true|false, "p": HMAC-SHA256(secret, "fmb-hello-ok2:<n>:<want>")[:16] hex}

Outside a trusted Wi-Fi the phone never opens backup mode by itself: a wanted backup is asked with
"Allow backup?". Version 1 is still understood (older phone apps).

Same format in the phone app (HomeCheck.kt). No Qt here.
"""

import hmac
import json
import socket
import threading
import time

from . import companion

PORT = 47826
MAX_SKEW_S = 600          # the phone's clock may differ this much


def hello_proof(secret, ph, pc, n, t, m, w, b):
    return companion._hmac(secret, f"fmb-hello:{ph}:{pc}:{n}:{int(t)}:{m}:{int(w)}:{int(b)}")[:16].hex()


def reply_proof(secret, ph, pc, n, want):
    return companion._hmac(secret, f"fmb-hello-ok:{ph}:{pc}:{n}:{'true' if want else 'false'}")[:16].hex()


def hello_key(secret, n):
    return companion._hmac(secret, f"fmb-hello-id:{n}")[:8].hex()


def hello_proof2(secret, k, n, t, m, w, b, h):
    return companion._hmac(secret, f"fmb-hello2:{k}:{n}:{int(t)}:{m}:{int(w)}:{int(b)}:{int(h)}")[:16].hex()


def reply_proof2(secret, n, want):
    return companion._hmac(secret, f"fmb-hello-ok2:{n}:{'true' if want else 'false'}")[:16].hex()


class Hello:
    """{"entry": paired phone, "mode", "homes", "unrestricted", "app_version", "address", "time"}."""

    def __init__(self, entry, msg, address):
        self.entry = entry
        self.mode = msg.get("m", "")
        self.homes = int(msg.get("w") or 0)
        self.unrestricted = bool(msg.get("b"))
        self.app_version = str(msg.get("av") or "")
        self.trusted = msg.get("v") == 1 or bool(msg.get("h"))   # in one of the phone's trusted Wi-Fis
        self.address = address
        self.time = time.time()

    @property
    def name(self):
        return self.entry.get("name") or ""


def check(cfg, data, seen, now=None):
    """A valid check-in of a paired phone → (entry, message), else (None, None). `seen`: nonces used."""
    now = time.time() if now is None else now
    try:
        msg = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, None
    if not isinstance(msg, dict) or msg.get("v") not in (1, 2):
        return None, None
    n, t = str(msg.get("n", "")), msg.get("t")
    if len(n) != 16 or not isinstance(t, int) or abs(now - t) > MAX_SKEW_S or n in seen:
        return None, None
    if msg["v"] == 2:
        k = str(msg.get("k", ""))
        for entry in companion.phones(cfg):
            sec = entry.get("secret")
            if not sec or not hmac.compare_digest(hello_key(sec, n), k):
                continue
            want = hello_proof2(sec, k, n, t, msg.get("m", ""), msg.get("w", 0), msg.get("b", 0), msg.get("h", 0))
            if hmac.compare_digest(want, str(msg.get("p", ""))):
                seen.add(n)
                return entry, msg
        return None, None
    pc_id, _name = companion.pc_identity(cfg)
    if msg.get("pc") != pc_id:
        return None, None
    for entry in companion.phones(cfg):
        if entry.get("phone_id") != msg.get("ph") or not entry.get("secret"):
            continue
        want = hello_proof(entry["secret"], msg["ph"], pc_id, n, t, msg.get("m", ""), msg.get("w", 0), msg.get("b", 0))
        if hmac.compare_digest(want, str(msg.get("p", ""))):
            seen.add(n)
            return entry, msg
    return None, None


def answer(cfg, entry, msg, want):
    if msg.get("v") == 2:
        return json.dumps({"v": 2, "n": msg["n"], "want": bool(want),
                           "p": reply_proof2(entry["secret"], msg["n"], want)}).encode()
    pc_id, _name = companion.pc_identity(cfg)
    return json.dumps({"pc": pc_id, "n": msg["n"], "want": bool(want),
                       "p": reply_proof(entry["secret"], msg["ph"], pc_id, msg["n"], want)}).encode()


class Listener(threading.Thread):
    """The UDP listener. decide(Hello) -> bool (called in this thread): is a backup wanted now?"""

    def __init__(self, cfg, decide, port=PORT):
        super().__init__(daemon=True, name="phone-hello")
        self.cfg, self.decide, self.port = cfg, decide, port
        self.stop = threading.Event()
        self.seen = set()
        self.sock = None

    def run(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", self.port))
            s.settimeout(1.0)
        except OSError:
            return                                # port taken (another copy of the program)
        self.sock = s
        while not self.stop.is_set():
            try:
                data, addr = s.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            entry, msg = check(self.cfg, data, self.seen)
            if entry is None:
                continue
            if len(self.seen) > 500:
                self.seen = set(list(self.seen)[-200:])
            try:
                want = bool(self.decide(Hello(entry, msg, addr[0])))
            except Exception:  # noqa: BLE001 - never leave the phone without an answer
                want = False
            try:
                s.sendto(answer(self.cfg, entry, msg, want), addr)
            except OSError:
                pass
        s.close()
