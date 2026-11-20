package io.github.machetso.mediabackup

import org.junit.Assert.assertEquals
import org.junit.Test

/** Same values as phonebackup/wake.py (computer side, "Connect phone" QR code). */
class ConnectTokenTest {
    private val secret = "ab".repeat(32)

    @Test fun connectToken() =
        assertEquals("3edbd42c", Connect.token(secret, "0123abcd"))

    @Test fun matchFindsTheRightComputer() {
        val pcs = listOf("A" to "11".repeat(32), "B" to secret)
        assertEquals("B", Connect.match(pcs, "0123abcd", listOf("00000000", Connect.token(secret, "0123abcd"))))
        assertEquals(null, Connect.match(pcs, "0123abcd", listOf("00000000")))
    }

    @Test fun hereProof() =
        assertEquals("8b712f5ad5b7178a521ff0a5dc00862e",
            Connect.hmacHex(secret, "fmb-here:0123456789abcdef:192.168.1.7:47823", 16))
}
