package io.github.machetso.mediabackup

import org.junit.Assert.assertEquals
import org.junit.Test

/** Same value as phonebackup/presence.py (computer side, "Ask the phone for a backup"). */
class AskTokenTest {
    @Test fun askProof() =
        assertEquals("30881616b4c50988c169a867065a8b32",
            AskService.proof("ab".repeat(32), "pc-1", "0123456789abcdef", 1800000000L))

    @Test fun autoProof() =
        assertEquals("ff3bde18241c2f8ad70ad819c4fe19ef",
            AskService.proof("ab".repeat(32), "pc-1", "0123456789abcdef", 1800000000L, auto = true))

    @Test fun newProof() =
        assertEquals(NEW_PROOF,
            AskService.newProof("ab".repeat(32), "pc-1", "0123456789abcdef", 1800000000L, 1790000000L,
                listOf("DCIM/Camera", "Pictures/Screenshots"), "no_drive"))

    companion object { const val NEW_PROOF = "4ec99f908b3b1e63783a0e9b71026e2c" }
}
