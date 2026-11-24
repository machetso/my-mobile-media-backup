package io.github.machetso.mediabackup

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Same values as phonebackup/knownlist.py and presence.known_proof (computer side). */
class KnownListTest {
    private val blob = "db15a664763a65264d184e19b0ea6d10".chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    @Test fun digestLikeTheComputer() {
        assertEquals(5555276012610809104L, KnownList.digest("DCIM/Camera/PXL_1.jpg", 1234))
        assertEquals(-2660037054481930970L, KnownList.digest("/DCIM/Camera/VID_2.mp4/", 99))
    }

    @Test fun versionLikeTheComputer() = assertEquals("534edaef8823e080", KnownList.versionOf(blob))

    @Test fun parseAndContains() {
        val list = KnownList.parse(blob)!!
        assertArrayEquals(longArrayOf(-2660037054481930970L, 5555276012610809104L), list)
        assertTrue(KnownList.contains(list, "DCIM/Camera/PXL_1.jpg", 1234))
        assertFalse(KnownList.contains(list, "DCIM/Camera/PXL_1.jpg", 1235))
        assertEquals(null, KnownList.parse(ByteArray(7)))
    }

    @Test fun knownProof() = assertEquals("13e8803734aef850ae9a38667344c77c",
        AskService.knownProof("ab".repeat(32), "pc1", "0123456789abcdef", 1800000000L, "534edaef8823e080"))
}
