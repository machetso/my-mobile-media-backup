package io.github.machetso.mediabackup

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import org.json.JSONObject
import java.io.BufferedInputStream
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.security.MessageDigest
import java.security.SecureRandom
import kotlin.concurrent.thread

/**
 * "Backup requests from the computer" (user request 2026-11-17, OFF unless the user switches it on):
 * while the phone is in the Wi-Fi, a paired computer can ask for a backup. The phone then shows a
 * notification "<computer> wants to back up this phone" – backup mode only starts when the user
 * taps "Allow". Nothing is shared before that: this service only receives the request.
 *
 * Announced anonymously like backup mode (Announce: random name, tokens per paired computer that
 * change every 10 minutes) as _phonebkpask._tcp, port 47825 if free.
 *
 *   POST /ask {"pc": <computer id>, "n": <nonce, 16 hex>, "e": <expiry, unix s>,
 *              "p": HMAC-SHA256(secret, "fmb-ask:<pc>:<n>:<e>")[:16] as hex}
 *   → 200 {"state": "asked" | "running"}  /  403 for anything not from a paired computer
 *
 * Same format in phonebackup/presence.py.
 */
class AskService : Service() {
    companion object {
        const val SERVICE_TYPE = "_phonebkpask._tcp"
        const val PORT = 47825
        private const val PREFS = "settings"
        private const val KEY = "ask_enabled"
        private const val KEY_AUTO = "auto_backup"
        private const val CHANNEL_ON = "ask_listen"
        private const val CHANNEL_ASK = "ask_request"
        const val ASK_NOTIFICATION = 3
        const val CABLE_NOTIFICATION = 4
        const val PLUG_OUT_MS = 3_000L               // out at least this long = really unplugged
        const val QUIET_AFTER_SWITCH_MS = 15_000L    // ADB on/off re-connects USB: not a new plug-in
        private const val MAX_AHEAD_S = 600L        // a request is valid for at most 10 minutes

        // ON by default (user request 2026-11-17); the user can switch it off in the app
        fun enabled(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY, true)

        fun setEnabled(ctx: Context, on: Boolean) {
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY, on).apply()
            if (on) startIfEnabled(ctx) else ctx.stopService(Intent(ctx, AskService::class.java))
        }

        /** "Automatic backup": the computer may start backup mode without the "Allow" tap. */
        fun autoEnabled(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY_AUTO, false)

        fun setAuto(ctx: Context, on: Boolean) {
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY_AUTO, on).apply()
            if (on) setEnabled(ctx, true)                  // automatic needs the listener
            else ctx.stopService(Intent(ctx, AskService::class.java)).also { startIfEnabled(ctx) }   // new TXT
        }

        fun startIfEnabled(ctx: Context) {
            if (enabled(ctx) && Identity.computers(ctx).isNotEmpty())
                runCatching { ctx.startForegroundService(Intent(ctx, AskService::class.java)) }
        }

        /** The proof a paired computer sends (also used by the unit test). */
        fun proof(secret: String, pc: String, nonce: String, expiry: Long, auto: Boolean = false) =
            Connect.hmacHex(secret, "fmb-ask:$pc:$nonce:$expiry" + (if (auto) ":auto" else ""), 16)
    }

    private var socket: ServerSocket? = null
    private var nsdListener: NsdManager.RegistrationListener? = null
    private var window = -1L
    private val seen = LinkedHashSet<String>()      // nonces already used (no replay)
    private var lastAsk = 0L

    // ---- cable plugged in (user request 2026-11-17): with "Automatic backup" on, the phone switches
    // the fast connection (ADB) on by itself – the computer then starts the backup over the cable.
    // Only a USB connection to a computer counts (a wall charger does not). Not after a short USB
    // re-connect (switching ADB on/off makes the phone re-connect): the cable must have been out
    // for a few seconds, and nothing right after the app switched ADB itself.
    private var usbIn: Boolean? = null
    private var usbOutSince = 0L
    private val usbReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            val connected = i.getBooleanExtra("connected", false)
            val now = System.currentTimeMillis()
            if (isInitialStickyBroadcast) { usbIn = connected; return }
            if (!connected) {
                if (usbIn != false) usbOutSince = now
                usbIn = false
                return
            }
            val wasOut = usbIn == false && now - usbOutSince >= PLUG_OUT_MS
            usbIn = true
            if (wasOut && now - UsbDebug.lastSwitchAt >= QUIET_AFTER_SWITCH_MS) cablePluggedIn()
        }
    }

    private fun cablePluggedIn() {
        if (!autoEnabled(this) || !UsbDebug.canSwitch(this)) return
        UsbDebug.Guard.restore(this)
        if (UsbDebug.Guard.engaged) return                 // fast connection is on already
        if (UsbDebug.switchOnAdb(this) != null) return
        startBackupMode()                                  // the guard (cable rule) runs there
        val n = Notification.Builder(this, CHANNEL_ON)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle(tr("Fast connection on"))
            .setContentText(tr("USB cable plugged in – automatic backup over the cable."))
            .setTimeoutAfter(60_000L)
            .build()
        getSystemService(NotificationManager::class.java).notify(CABLE_NOTIFICATION, n)
    }
    private val main = Handler(Looper.getMainLooper())
    private val tick = object : Runnable {
        override fun run() {
            announce()
            main.postDelayed(this, 15_000)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        I18n.load(this)
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL_ON, tr("Waiting for backup requests"),
            NotificationManager.IMPORTANCE_MIN))
        nm.createNotificationChannel(NotificationChannel(CHANNEL_ASK, tr("Backup requests"),
            NotificationManager.IMPORTANCE_HIGH))
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = Notification.Builder(this, CHANNEL_ON)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle(tr("Backup requests on"))
            .setContentText(tr("Your computer can ask for a backup – nothing starts without your “Allow”."))
            .setContentIntent(open)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 34) startForeground(2, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        else startForeground(2, n)
        val s = runCatching { ServerSocket().apply { reuseAddress = true; bind(InetSocketAddress(PORT)) } }
            .getOrElse { ServerSocket(0) }
        socket = s
        thread(name = "ask-listener", isDaemon = true) { serve(s) }
        main.post(tick)
        val filter = IntentFilter("android.hardware.usb.action.USB_STATE")
        runCatching {
            if (Build.VERSION.SDK_INT >= 33) registerReceiver(usbReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
            else registerReceiver(usbReceiver, filter)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!enabled(this)) stopSelf()
        else main.post { unannounce(); announce() }     // "automatic backup" switched: new TXT
        return START_STICKY
    }

    private fun announce() {
        val s = socket ?: return
        val w = Announce.window()
        if (w == window) return
        unannounce()
        window = w
        val info = NsdServiceInfo().apply {
            val rnd = ByteArray(4).also { SecureRandom().nextBytes(it) }
            serviceName = "FMBASK-${Announce.hex(rnd)}"
            serviceType = SERVICE_TYPE
            port = s.localPort
            setAttribute("v", "1")
            if (autoEnabled(this@AskService)) setAttribute("a", "1")     // automatic backup allowed
            setAttribute("t", Identity.computers(this@AskService).take(16)
                .joinToString(".") { Announce.hex(Announce.token(it.secret, w)) })
        }
        val l = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(i: NsdServiceInfo) {}
            override fun onRegistrationFailed(i: NsdServiceInfo, code: Int) {}
            override fun onServiceUnregistered(i: NsdServiceInfo) {}
            override fun onUnregistrationFailed(i: NsdServiceInfo, code: Int) {}
        }
        runCatching {
            (getSystemService(Context.NSD_SERVICE) as NsdManager).registerService(info, NsdManager.PROTOCOL_DNS_SD, l)
            nsdListener = l
        }
    }

    private fun unannounce() {
        nsdListener?.let { l -> runCatching { (getSystemService(Context.NSD_SERVICE) as NsdManager).unregisterService(l) } }
        nsdListener = null
        window = -1L
    }

    private fun serve(s: ServerSocket) {
        while (!s.isClosed) {
            val c = runCatching { s.accept() }.getOrNull() ?: continue
            thread(isDaemon = true) { runCatching { handle(c) }; runCatching { c.close() } }
        }
    }

    private fun handle(c: Socket) {
        c.soTimeout = 10_000
        val req = Request.read(BufferedInputStream(c.getInputStream())) ?: return
        val out = c.getOutputStream()
        if (req.method != "POST" || req.path != "/ask") { Response.json(out, 404, "{}", false); return }
        val auto = runCatching { JSONObject(String(req.body, Charsets.UTF_8)).optBoolean("auto") }.getOrDefault(false)
        val pc = check(req.body, auto)
        if (pc == null) { Response.json(out, 403, "{}", false); return }
        val state = when {
            BackupService.server != null -> "running"
            auto && !autoEnabled(this) -> "not_auto"       // no surprise notification
            auto && startBackupMode() -> "started"
            else -> { main.post { ask(pc) }; "asked" }
        }
        Response.json(out, 200, JSONObject().put("state", state).toString(), false)
    }

    /** Automatic backup: backup mode on without a tap. Android only allows this from the
     *  background when the app may run unrestricted (battery: "Unrestricted") – otherwise the
     *  phone falls back to the "Allow backup?" notification. */
    private fun startBackupMode(): Boolean = try {
        startForegroundService(Intent(this, BackupService::class.java))
        true
    } catch (e: Exception) {
        false
    }

    /** The paired computer that sent a valid request, or null. */
    private fun check(body: ByteArray, auto: Boolean): Identity.Computer? {
        val o = runCatching { JSONObject(String(body, Charsets.UTF_8)) }.getOrNull() ?: return null
        val pcId = o.optString("pc")
        val nonce = o.optString("n")
        val expiry = o.optLong("e")
        val proof = o.optString("p")
        val now = System.currentTimeMillis() / 1000
        if (!Regex("[0-9a-f]{16}").matches(nonce) || expiry < now || expiry > now + MAX_AHEAD_S) return null
        val pc = Identity.computers(this).firstOrNull { it.id == pcId } ?: return null
        val mine = proof(pc.secret, pcId, nonce, expiry, auto)     // "auto" is part of the proof
        if (!MessageDigest.isEqual(mine.toByteArray(), proof.toByteArray())) return null
        synchronized(seen) {
            if (!seen.add(nonce)) return null
            while (seen.size > 200) seen.remove(seen.first())
        }
        return pc
    }

    private fun ask(pc: Identity.Computer) {
        val now = System.currentTimeMillis()
        if (now - lastAsk < 20_000) return             // one notification is enough
        lastAsk = now
        val allow = PendingIntent.getForegroundService(this, 1, Intent(this, BackupService::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val open = PendingIntent.getActivity(this, 2, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = Notification.Builder(this, CHANNEL_ASK)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle(tr("Allow backup?"))
            .setContentText(tr("“%s” wants to back up the photos and videos of this phone.", pc.name))
            .setContentIntent(open)
            .addAction(Notification.Action.Builder(null, tr("Allow"), allow).build())
            .setAutoCancel(true)
            .setTimeoutAfter(5 * 60_000L)
            .build()
        getSystemService(NotificationManager::class.java).notify(ASK_NOTIFICATION, n)
    }

    override fun onDestroy() {
        runCatching { unregisterReceiver(usbReceiver) }
        main.removeCallbacksAndMessages(null)
        unannounce()
        runCatching { socket?.close() }
        socket = null
        super.onDestroy()
    }
}
