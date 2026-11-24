package io.github.machetso.mediabackup

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build

/**
 * "When your computer wants a backup" (user request 2026-11-17; battery-saving since 2026-11-23):
 * the settings ("Ask me" / "Allow without asking" / "Never") and the "Allow backup?" question.
 * Nothing listens all the time any more – HomeCheck asks the paired computer when Android wakes the
 * app (home Wi-Fi joined, charging, every 30 minutes).
 *
 * The request formats (/ask, /new, /known) of the old listener are kept for their proofs (unit
 * tests, Server.kt).
 */
object AskService {
    private const val PREFS = "settings"
    private const val KEY = "ask_enabled"
    private const val KEY_AUTO = "auto_backup"       // "Allow without asking"
    private const val CHANNEL_ASK = "ask_request"
    const val ASK_NOTIFICATION = 3
    const val EXTRA_ASK = "ask_from"             // the app opened from "Allow backup?": who asks

    // ON by default (user request 2026-11-17); the user can switch it off in the app
    fun enabled(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY, true)

    fun setEnabled(ctx: Context, on: Boolean) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY, on).apply()
        HomeCheck.schedule(ctx)
    }

    /** "Allow without asking": the paired computer may open backup mode without the "Allow" tap. */
    fun autoEnabled(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY_AUTO, false)

    fun setAuto(ctx: Context, on: Boolean) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY_AUTO, on).apply()
        if (on) setEnabled(ctx, true) else HomeCheck.schedule(ctx)
    }

    /** The checks armed (app start, pairing, update, reboot). */
    fun startIfEnabled(ctx: Context) = HomeCheck.schedule(ctx)

    /** The proof a paired computer sends (also used by the unit test). */
    fun proof(secret: String, pc: String, nonce: String, expiry: Long, auto: Boolean = false) =
        Connect.hmacHex(secret, "fmb-ask:$pc:$nonce:$expiry" + (if (auto) ":auto" else ""), 16)

    /** Proof of the backup's file list (POST /known, 2026-11-23). */
    fun knownProof(secret: String, pc: String, nonce: String, expiry: Long, k: String) =
        Connect.hmacHex(secret, "fmb-known:$pc:$nonce:$expiry:$k", 16)

    /** Proof of a "what is new?" question (POST /new). */
    fun newProof(secret: String, pc: String, nonce: String, expiry: Long, since: Long, folders: List<String>,
                 ready: String = "") =
        Connect.hmacHex(secret, "fmb-new:$pc:$nonce:$expiry:$since:" + folders.joinToString("|") + ":$ready", 16)

    /** Backup mode on without a tap. Android only allows this from the background when the app may
     *  run unrestricted (battery: "Unrestricted") – otherwise false (then: the question). */
    fun startBackupMode(ctx: Context): Boolean = try {
        ctx.startForegroundService(Intent(ctx, BackupService::class.java))
        true
    } catch (e: Exception) {
        false
    }

    private var lastAsk = 0L

    /** "Allow backup?": in the open app (with a short vibration), else as a notification. */
    fun ask(ctx: Context, pc: Identity.Computer) {
        val now = System.currentTimeMillis()
        if (now - lastAsk < 20_000) return             // one question is enough
        lastAsk = now
        MainActivity.open?.let { activity ->
            activity.runOnUiThread { activity.showAsk(pc.name) }
            buzz(ctx)
            return
        }
        val nm = ctx.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL_ASK, tr("Backup requests"),
            NotificationManager.IMPORTANCE_HIGH))
        val allow = PendingIntent.getForegroundService(ctx, 1, Intent(ctx, BackupService::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        // a tap on the notification itself opens the app WITH the question – the "Allow" button of
        // the notification is hidden while it is collapsed (user 2026-11-19: "I cannot allow a backup")
        val open = PendingIntent.getActivity(ctx, 2, Intent(ctx, MainActivity::class.java)
            .putExtra(EXTRA_ASK, pc.name).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = Notification.Builder(ctx, CHANNEL_ASK)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle(tr("Allow backup?"))
            .setContentText(tr("“%s” wants to back up the photos and videos of this phone.", pc.name))
            .setContentIntent(open)
            .addAction(Notification.Action.Builder(null, tr("Allow"), allow).build())
            .setAutoCancel(true)
            .setTimeoutAfter(5 * 60_000L)
            .build()
        nm.notify(ASK_NOTIFICATION, n)
    }

    /** A short vibration: the computer asks while the app is open (the notification has its own). */
    private fun buzz(ctx: Context) = runCatching {
        val effect = android.os.VibrationEffect.createOneShot(180, android.os.VibrationEffect.DEFAULT_AMPLITUDE)
        if (Build.VERSION.SDK_INT >= 31)
            ctx.getSystemService(android.os.VibratorManager::class.java).defaultVibrator.vibrate(effect)
        else @Suppress("DEPRECATION") ctx.getSystemService(android.os.Vibrator::class.java).vibrate(effect)
    }
}
