package io.github.machetso.mediabackup

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Same values as phonebackup/hello.py; home Wi-Fi matching (battery-saving requests, 2026-11-23). */
class HomeCheckTest {
    private val secret = "ab".repeat(32)

    @Test fun helloProof() = assertEquals("f53339d7cd879a086c776924a6c11522",
        HomeCheck.helloProof(secret, "ph-1", "pc-1", "0123456789abcdef", 1800000000L, "auto", 2, 1))

    @Test fun replyProof() = assertEquals("58073239339028e121e5ef469568d82a",
        HomeCheck.replyProof(secret, "ph-1", "pc-1", "0123456789abcdef", true))

    // check-in version 2 (any Wi-Fi, 2026-11-24) – same values in tests/test_hello.py
    @Test fun helloV2() {
        val k = HomeCheck.helloKey(secret, "0123456789abcdef")
        assertEquals("19ec958b817beff3", k)
        assertEquals("ea42f687f2fe45f527cd926b7a057666",
            HomeCheck.helloProof2(secret, k, "0123456789abcdef", 1800000000L, "auto", 2, 1, 0))
        assertEquals("86ba11ac404608302c89f9333ca1e997", HomeCheck.replyProof2(secret, "0123456789abcdef", true))
    }

    @Test fun networkRange() {
        assertEquals("192.168.178.0", HomeWifi.networkOf(byteArrayOf(192.toByte(), 168.toByte(), 178.toByte(), 73), 24))
        assertEquals("10.0.0.0", HomeWifi.networkOf(byteArrayOf(10, 0, 3, 7), 16))
    }

    @Test fun broadcastAddress() {
        assertEquals("192.168.178.255", HomeWifi.broadcastOf("192.168.178.0/24"))
        assertEquals("10.0.255.255", HomeWifi.broadcastOf("10.0.0.0/16"))
        assertNull(HomeWifi.broadcastOf("nonsense"))
    }

    @Test fun matching() {
        val home = HomeWifi.Net("FRITZ!Box 7590", "192.168.178.1", "192.168.178.0/24", setOf("aa:bb:cc:dd:ee:ff"))
        val nets = listOf(home)
        // background (no permission): router + range
        assertEquals(home, HomeWifi.match(nets, HomeWifi.Seen("", "02:00:00:00:00:00", "192.168.178.1", "192.168.178.0/24")))
        // another router address or range: not home
        assertNull(HomeWifi.match(nets, HomeWifi.Seen("", "", "192.168.0.1", "192.168.0.0/24")))
        // access point visible: a foreign one with another name is not home
        assertNull(HomeWifi.match(nets, HomeWifi.Seen("Cafe", "11:22:33:44:55:66", "192.168.178.1", "192.168.178.0/24")))
        // known access point, or the same name (a second access point of the home Wi-Fi)
        assertEquals(home, HomeWifi.match(nets, HomeWifi.Seen("", "aa:bb:cc:dd:ee:ff", "192.168.178.1", "192.168.178.0/24")))
        assertEquals(home, HomeWifi.match(nets, HomeWifi.Seen("FRITZ!Box 7590", "11:22:33:44:55:66", "192.168.178.1", "192.168.178.0/24")))
    }
}
