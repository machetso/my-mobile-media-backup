package io.github.machetso.mediabackup

import android.content.Context
import java.io.File
import java.security.MessageDigest

/**
 * What the computer's backup holds already (user request 2026-11-23): "not backed up yet" is
 * counted against the backup's FILE LIST, not against the date of the last backup.
 *
 * The computer sends the list once (and again only when it changed, "k" = version): for each
 * backed-up file (phone path, size) 8 bytes of SHA-256("<path>\u0000<size>"), sorted – the same as
 * phonebackup/knownlist.py on the computer. Kept in the app's own storage, so the phone can count
 * again later without the computer. Without a list the phone counts by date (as before).
 */
object KnownList {
    private const val FILE = "known.bin"
    private const val PREFS = "known_list"

    @Volatile var pc: String = ""            // the computer the list belongs to
        private set
    @Volatile var version: String = ""
        private set
    @Volatile private var digests: LongArray? = null

    fun digest(rel: String, size: Long): Long {
        val h = MessageDigest.getInstance("SHA-256")
            .digest("${rel.trim('/')}\u0000$size".toByteArray(Charsets.UTF_8))
        var v = 0L
        for (i in 0 until 8) v = (v shl 8) or (h[i].toLong() and 0xff)
        return v
    }

    fun versionOf(blob: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(blob).take(8).joinToString("") { "%02x".format(it) }

    /** 8 bytes each, big endian; sorted again here (never trusts the order). */
    fun parse(blob: ByteArray): LongArray? {
        if (blob.size % 8 != 0) return null
        val out = LongArray(blob.size / 8)
        for (i in out.indices) {
            var v = 0L
            for (j in 0 until 8) v = (v shl 8) or (blob[i * 8 + j].toLong() and 0xff)
            out[i] = v
        }
        out.sort()
        return out
    }

    fun contains(list: LongArray, rel: String, size: Long) = list.binarySearch(digest(rel, size)) >= 0

    /** The version the phone has for computer [forPc] ("" = none). */
    fun versionFor(ctx: Context, forPc: String): String {
        load(ctx)
        return if (pc == forPc) version else ""
    }

    /** The list for computer [forPc], or null (then: count by date). */
    fun listFor(ctx: Context, forPc: String): LongArray? {
        load(ctx)
        return if (pc == forPc) digests else null
    }

    /** The computer sent its list: checked against its version, kept. False = not valid. */
    fun set(ctx: Context, forPc: String, k: String, blob: ByteArray): Boolean {
        if (versionOf(blob) != k) return false
        val list = parse(blob) ?: return false
        File(ctx.filesDir, FILE).writeBytes(blob)
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("pc", forPc).putString("k", k).apply()
        synchronized(this) { pc = forPc; version = k; digests = list }
        return true
    }

    @Synchronized
    private fun load(ctx: Context) {
        if (digests != null) return
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val k = p.getString("k", null) ?: return
        val blob = runCatching { File(ctx.filesDir, FILE).readBytes() }.getOrNull() ?: return
        if (versionOf(blob) != k) return
        digests = parse(blob) ?: return
        pc = p.getString("pc", "") ?: ""
        version = k
    }
}
