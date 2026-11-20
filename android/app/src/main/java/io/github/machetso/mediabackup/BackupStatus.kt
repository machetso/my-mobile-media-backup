package io.github.machetso.mediabackup

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import org.json.JSONObject

/**
 * One-click backup from the phone (user request 2026-11-20): what the paired computer told the
 * phone about its backup of it, so the phone can show "23 photos and 4 videos not backed up yet"
 * and a "Back up now" button that is only usable when a backup can really start.
 *
 * The computer sends it with every "what is new?" question (AskService POST /new, while the phone
 * is only nearby) and while it is connected (Server POST /status, every few seconds):
 *   since   = start of its last complete backup of this phone (unix s)
 *   folders = the phone folders that backup takes
 *   ready   = "" a backup can start · "no_backup" no backup of this phone on that computer yet ·
 *             "no_drive" its backup drive is not connected · "busy" the computer is busy
 * The phone counts the new photos and videos itself (MediaIndex.countNew) – also later, without
 * the computer. Saved, so it is still known after a restart.
 */
object BackupStatus {
    private const val PREFS = "backup_status"
    const val FRESH_MS = 10 * 60_000L          // older news from the computer: "not found"
    const val WANT_MS = 5 * 60_000L            // "Back up now" waits this long for the computer

    data class Info(val pc: String, val at: Long, val since: Long, val folders: List<String>, val ready: String)

    var info by mutableStateOf<Info?>(null)
    var photos by mutableStateOf(-1)           // -1 = not counted yet
    var videos by mutableStateOf(-1)
    var bytes by mutableStateOf(0L)            // their size together
    var wantAt by mutableStateOf(0L)           // the user tapped "Back up now"

    fun wanted(now: Long = System.currentTimeMillis()) = wantAt > 0 && now - wantAt < WANT_MS

    fun load(ctx: Context) {
        if (info != null) return
        val s = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("info", null) ?: return
        info = runCatching {
            val o = JSONObject(s)
            val f = o.getJSONArray("folders")
            Info(o.getString("pc"), o.getLong("at"), o.getLong("since"), (0 until f.length()).map { f.getString(it) },
                o.optString("ready"))
        }.getOrNull()
    }

    /** The computer told its news: remember it and count. */
    fun update(ctx: Context, pc: String, since: Long, folders: List<String>, ready: String): MediaIndex.NewMedia {
        val i = Info(pc, System.currentTimeMillis(), since, folders, ready)
        info = i
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("info", JSONObject()
            .put("pc", pc).put("at", i.at).put("since", since).put("folders", JSONArray(folders))
            .put("ready", ready).toString()).apply()
        return count(ctx)
    }

    /** Count again (app opened, every half minute on the screen) from the last news. */
    fun count(ctx: Context): MediaIndex.NewMedia {
        val none = MediaIndex.NewMedia(-1, -1, 0)
        val i = info ?: return none
        if (!MediaIndex.hasFullAccess(ctx)) return none
        val c = runCatching { MediaIndex(ctx).countNew(i.since, i.folders) }.getOrDefault(none)
        photos = c.photos
        videos = c.videos
        bytes = c.bytes
        return c
    }

    /** "1.5 GB" / "321 MB" – not more detailed (user request 2026-11-20). */
    fun sizeText(bytes: Long): String {
        val mb = bytes / (1024.0 * 1024.0)
        return when {
            mb >= 1024 -> String.format(I18n.locale, "%.1f GB", mb / 1024)
            mb >= 1 -> String.format(I18n.locale, "%d MB", Math.round(mb))
            else -> tr("under 1 MB")
        }
    }

    /** Parse the computer's fields from a request body. */
    fun fromJson(o: JSONObject): Triple<Long, List<String>, String>? {
        val f = o.optJSONArray("f") ?: return null
        if (f.length() > 100) return null
        return Triple(o.optLong("s"), (0 until f.length()).map { f.optString(it) }, o.optString("r"))
    }
}
