import json
import time
import unittest
import urllib.request
from unittest import mock

from phonebackup import companion, config


class CompanionTest(unittest.TestCase):
    def test_pairing_code(self):
        c = companion.pairing_code("tok", "ab" * 32)
        self.assertEqual(len(c), 6)
        self.assertTrue(c.isdigit())
        self.assertEqual(c, companion.pairing_code("tok", "ab" * 32))
        self.assertNotEqual(c, companion.pairing_code("tok2", "ab" * 32))

    def test_setup_server_pair_flow(self):
        saved = config.save
        config.save = lambda cfg: None
        try:
            got = []
            srv = companion.SetupServer({"pc_id": "x"}, got.append, port=0)
            srv.ip = "127.0.0.1"
            srv.start()
            try:
                page = urllib.request.urlopen(srv.page_url).read().decode()
                self.assertIn("intent://pair?", page)
                self.assertIn("package=" + companion.APP_PACKAGE, page)

                def post(d):
                    req = urllib.request.Request(srv.base + "/pair", json.dumps(d).encode(),
                                                 {"Content-Type": "application/json"})
                    try:
                        return urllib.request.urlopen(req).status
                    except urllib.error.HTTPError as e:
                        return e.code

                nonce = "0f" * 16
                self.assertEqual(post({"token": "wrong", "fingerprint": "a" * 64, "port": 1, "nonce": nonce}), 403)
                self.assertEqual(post({"token": srv.token, "fingerprint": "zz", "port": 1, "nonce": nonce}), 400)
                self.assertEqual(post({"token": srv.token, "fingerprint": "a" * 64, "port": 1, "nonce": "x"}), 400)
                revealed = []
                with mock.patch.object(companion.SetupServer, "reveal", lambda s, r: revealed.append(r)):
                    self.assertEqual(post({"token": srv.token, "fingerprint": "a" * 64, "port": 47823,
                                           "nonce": nonce, "model": "Pixel"}), 200)
                    for _ in range(50):
                        if revealed:
                            break
                        time.sleep(0.02)
                self.assertEqual(len(got), 1)
                self.assertEqual(revealed, got)                 # the key goes out right after
                self.assertEqual(got[0].address, "127.0.0.1:47823")
                self.assertEqual(got[0].code, companion.pairing_code_v2(srv.key, "a" * 64, nonce))
                # the link only carries the commitment, never the key itself
                self.assertEqual(srv.token, companion.token_for(srv.key))
                self.assertNotIn(srv.key, page)
                self.assertNotIn(srv.key, srv.intent_url())
                # unknown token in the URL: no page, no app
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(srv.base + "/s/other")
            finally:
                srv.stop()
        finally:
            config.save = saved


if __name__ == "__main__":
    unittest.main()


class CommitRevealTest(unittest.TestCase):
    """The key only goes to the phone over TLS pinned to the fingerprint it sent; claim uses it."""

    def test_reveal_and_claim_send_the_key_only_pinned(self):
        calls = []

        class FakeClient:
            def __init__(self, address, fingerprint, secret=None, timeout=0):
                self.fp = fingerprint

            def request(self, method, path, body=None):
                calls.append((self.fp, path, dict(body)))
                return {"secret": "s" * 40, "phone_id": "p"} if path == "/claim" else {"ok": True}

            def close(self):
                pass

        with mock.patch.object(companion, "local_ips", lambda: ["127.0.0.1"]), \
                mock.patch.object(companion, "Client", FakeClient), \
                mock.patch.object(companion, "save_phone", lambda cfg, e: None):
            srv = companion.SetupServer({"pc_id": "x"}, lambda r: None, port=0)
            req = companion.PairRequest(srv.token, "c" * 64, "10.0.0.5:1", "p", "Pixel", "Google", "16")
            self.assertTrue(srv.reveal(req))
            entry = srv.claim(req)
        self.assertEqual([c[1] for c in calls], ["/reveal", "/claim"])
        for fp, _path, body in calls:
            self.assertEqual(fp, "c" * 64)
            self.assertEqual(body, {"token": srv.token, "key": srv.key})
        self.assertEqual(entry["secret"], "s" * 40)

    def test_codes_depend_on_every_part(self):
        k, fp, n = "1" * 64, "a" * 64, "2" * 32
        c = companion.pairing_code_v2(k, fp, n)
        self.assertNotEqual(c, companion.pairing_code_v2("3" * 64, fp, n))
        self.assertNotEqual(c, companion.pairing_code_v2(k, "b" * 64, n))
        self.assertNotEqual(c, companion.pairing_code_v2(k, fp, "4" * 32))


class WiredWayTest(unittest.TestCase):
    """User test 2026-11-24 (office): laptop on cable + Wi-Fi in the phone's network – the phone app
    connection goes over the cable interface."""
    IFACES = [("lo", "127.0.0.1/8"), ("wlan0", "10.20.31.78/23"), ("eth1", "10.20.31.153/23"),
              ("tailscale0", "100.114.200.107/32")]

    def test_cable_interface_in_the_phones_network(self):
        wired = lambda d: d.startswith("eth")                                       # noqa: E731
        with mock.patch.object(companion.sys, "platform", "linux"):
            self.assertEqual(companion.wired_device_for("10.20.31.75", self.IFACES, wired), "eth1")
            self.assertEqual(companion.wired_device_for("10.20.30.9", self.IFACES, wired), "eth1")
            self.assertIsNone(companion.wired_device_for("192.168.178.73", self.IFACES, wired))   # other network
            self.assertIsNone(companion.wired_device_for("10.20.31.75", self.IFACES, lambda d: False))  # Wi-Fi only
            self.assertIsNone(companion.wired_device_for("adb-XYZ", self.IFACES, wired))
        with mock.patch.object(companion.sys, "platform", "win32"):
            self.assertIsNone(companion.wired_device_for("10.20.31.75", self.IFACES, wired))

    def test_parse_ip_addr(self):
        text = ("1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever\n"
                "3: wlan0    inet 10.20.31.78/23 brd 10.20.31.255 scope global dynamic\n")
        self.assertEqual(companion._interfaces_v4(text), [("lo", "127.0.0.1/8"), ("wlan0", "10.20.31.78/23")])

    @unittest.skipUnless(hasattr(companion.socket, "SO_BINDTODEVICE"), "Linux only")
    def test_falls_back_when_cable_way_fails(self):
        companion._WIRED_CACHE.clear()
        class Usual:
            def __init__(self, a):
                self.a = a

            def settimeout(self, t):
                pass
        with mock.patch.object(companion, "wired_device_for", lambda ip: "enx-test"), \
                mock.patch.object(companion.socket, "create_connection", lambda a, t: Usual(a)):
            self.assertEqual(companion.connect_best(("127.0.0.1", 9), 1).a, ("127.0.0.1", 9))
        self.assertIsNone(companion._WIRED_CACHE["127.0.0.1"][1])                    # remembered for a minute
        companion._WIRED_CACHE.clear()


class SilentPhoneTest(unittest.TestCase):
    """User test 2026-11-24: phone app announced, a VPN on the phone drops the connection – the
    program says why instead of "connecting" for ever."""

    def _source(self, answers):
        companion._WIRED_CACHE.clear()

        def silent(a, timeout):
            raise TimeoutError("timed out")
        entry = {"fingerprint": "00" * 32, "secret": "ab" * 32, "name": "Pixel 10 Pro"}
        with mock.patch.object(companion, "connect_best", silent), \
                mock.patch.object(companion, "phone_answers", lambda ip: answers):
            with self.assertRaises(companion.Unreachable) as cm:
                companion.CompanionSource(entry, "192.0.2.75:47823")
        return cm.exception

    def test_vpn_hint_when_the_phone_itself_answers(self):
        e = self._source(True)
        self.assertTrue(e.vpn)
        self.assertIn("VPN", str(e))

    def test_plain_hint_when_nothing_answers(self):
        e = self._source(False)
        self.assertFalse(e.vpn)
        self.assertIn("same Wi-Fi", str(e))

    def test_connect_waits_at_most_connect_timeout(self):
        seen = {}

        class Sock:
            def settimeout(self, t):
                seen["read"] = t

        def fake(a, t):
            seen["connect"] = t
            return Sock()
        companion._WIRED_CACHE.clear()
        with mock.patch.object(companion, "wired_device_for", lambda ip: None), \
                mock.patch.object(companion.socket, "create_connection", fake):
            companion.connect_best(("192.0.2.75", 47823), 900)
        self.assertEqual(seen, {"connect": companion.CONNECT_TIMEOUT, "read": 900})
        companion._WIRED_CACHE.clear()
