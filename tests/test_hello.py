"""The phone checks in (battery-saving backup requests, 2026-11-23): signatures like the phone app
(HomeCheckTest.kt), a real UDP exchange, forged and replayed messages refused."""
import json
import socket
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phonebackup import hello  # noqa: E402

SECRET = "ab" * 32
V2_KEY, V2_PROOF, V2_REPLY = "19ec958b817beff3", "ea42f687f2fe45f527cd926b7a057666", "86ba11ac404608302c89f9333ca1e997"


def cfg():
    return {"pc_id": "pc-1", "companion_phones": [{"phone_id": "ph-1", "secret": SECRET, "name": "Pixel 10 Pro"}]}


def msg(n="0123456789abcdef", t=None, proof=None):
    t = int(time.time()) if t is None else t
    p = proof or hello.hello_proof(SECRET, "ph-1", "pc-1", n, t, "auto", 2, 1)
    return json.dumps({"v": 1, "ph": "ph-1", "pc": "pc-1", "n": n, "t": t, "m": "auto", "w": 2, "b": 1,
                       "av": "0.9.9.0", "p": p}).encode()


def msg2(n="0123456789abcdef", t=None, h=0, secret=SECRET, proof=None):
    t = int(time.time()) if t is None else t
    k = hello.hello_key(secret, n)
    p = proof or hello.hello_proof2(secret, k, n, t, "auto", 2, 1, h)
    return json.dumps({"v": 2, "k": k, "n": n, "t": t, "m": "auto", "w": 2, "b": 1, "h": h, "p": p}).encode()


class HelloTest(unittest.TestCase):
    def test_v2_vectors_like_the_phone(self):
        # same values in HomeCheckTest.kt
        k = hello.hello_key(SECRET, "0123456789abcdef")
        self.assertEqual(k, V2_KEY)
        self.assertEqual(hello.hello_proof2(SECRET, k, "0123456789abcdef", 1800000000, "auto", 2, 1, 0), V2_PROOF)
        self.assertEqual(hello.reply_proof2(SECRET, "0123456789abcdef", True), V2_REPLY)

    def test_v2_anonymous_any_wifi(self):
        # user test 2026-11-24 (office Wi-Fi): no phone id, no computer id in the message
        raw = msg2(h=0)
        self.assertNotIn(b"ph-1", raw)
        self.assertNotIn(b"pc-1", raw)
        self.assertNotEqual(json.loads(msg2(n="4" * 16))["k"], json.loads(msg2(n="5" * 16))["k"])  # not trackable
        seen = set()
        entry, m = hello.check(cfg(), raw, seen)
        self.assertEqual(entry["name"], "Pixel 10 Pro")
        self.assertFalse(hello.Hello(entry, m, "198.51.100.75").trusted)
        self.assertEqual(hello.check(cfg(), raw, seen), (None, None))                         # replayed
        self.assertEqual(hello.check(cfg(), msg2(n="6" * 16, secret="cd" * 32), set()), (None, None))  # other key
        self.assertEqual(hello.check(cfg(), msg2(n="7" * 16, proof="0" * 32), set()), (None, None))  # forged
        e, m = hello.check(cfg(), msg2(n="8" * 16, h=1), set())
        self.assertTrue(hello.Hello(e, m, "192.0.2.9").trusted)
        ans = json.loads(hello.answer(cfg(), e, m, True))
        self.assertEqual(ans, {"v": 2, "n": "8" * 16, "want": True, "p": hello.reply_proof2(SECRET, "8" * 16, True)})

    def test_vectors_like_the_phone(self):
        self.assertEqual(hello.hello_proof(SECRET, "ph-1", "pc-1", "0123456789abcdef", 1800000000, "auto", 2, 1),
                         "f53339d7cd879a086c776924a6c11522")
        self.assertEqual(hello.reply_proof(SECRET, "ph-1", "pc-1", "0123456789abcdef", True),
                         "58073239339028e121e5ef469568d82a")

    def test_check_accepts_once_and_refuses_forgeries(self):
        seen = set()
        entry, m = hello.check(cfg(), msg(), seen)
        self.assertEqual(entry["name"], "Pixel 10 Pro")
        self.assertEqual(hello.check(cfg(), msg(), seen), (None, None))                       # replayed
        self.assertEqual(hello.check(cfg(), msg(n="1" * 16, proof="0" * 32), set()), (None, None))   # forged
        self.assertEqual(hello.check(cfg(), msg(n="2" * 16, t=int(time.time()) - 3600), set()), (None, None))  # old

    def test_udp_round_trip(self):
        got = []
        lst = hello.Listener(cfg(), lambda h: got.append(h) or True, port=0)
        # a free port for the test
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.bind(("127.0.0.1", 0))
        lst.port = probe.getsockname()[1]
        probe.close()
        lst.start()
        try:
            for _ in range(50):
                if lst.sock is not None:
                    break
                time.sleep(0.02)
            c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            c.settimeout(3)
            c.sendto(msg(n="3" * 16), ("127.0.0.1", lst.port))
            data, _a = c.recvfrom(4096)
            c.close()
        finally:
            lst.stop.set()
            lst.join(3)
        ans = json.loads(data)
        self.assertTrue(ans["want"])
        self.assertEqual(ans["p"], hello.reply_proof(SECRET, "ph-1", "pc-1", "3" * 16, True))
        self.assertEqual((got[0].name, got[0].homes, got[0].unrestricted, got[0].mode), ("Pixel 10 Pro", 2, True, "auto"))


if __name__ == "__main__":
    unittest.main()
