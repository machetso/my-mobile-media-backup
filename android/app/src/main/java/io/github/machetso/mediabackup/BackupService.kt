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
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/** Shared state for the screen. */
object AppState {
    var running by mutableStateOf(false)
    var port by mutableStateOf(0)
    var status by mutableStateOf("")
    var pairedChanged by mutableStateOf(0)
    var pairings by mutableStateOf(0)        // +1 for every new pairing (closes the pairing card)
    var idleLeft by mutableStateOf("")       // "4:12" until backup mode switches off unused
    var onCable by mutableStateOf(false)     // USB cable in: no timeout (user request 2026-11-17)
}

/**
 * "Backup mode": runs the read-only server while the computer copies, keeps Wi-Fi and CPU awake,
 * announces the phone anonymously (mDNS _phonebkp._tcp + Bluetooth LE, see Announce) and runs the
 * USB-debugging guard (see UsbDebug). Stops by itself when the computer
 * says the backup is done, or after 5 minutes without any request from the computer (user
 * request 2026-11-04; during a backup the computer's "still here" every 30 s counts as use).
 */
class BackupService : Service() {
    companion object {
        const val SERVICE_TYPE = "_phonebkp._tcp"
        private const val CHANNEL = "backup"
        const val IDLE_MS = 5 * 60_000L
        @Volatile var server: Server? = null
            private set

        fun start(ctx: Context) {
            ctx.startForegroundService(Intent(ctx, BackupService::class.java))
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, BackupService::class.java))
        }
    }

    private var wake: PowerManager.WakeLock? = null
    private var finished = false               // the computer said the backup is done
    private var wifiLock: WifiManager.WifiLock? = null
    private val main = Handler(Looper.getMainLooper())
    private val idleCheck = object : Runnable {
        override fun run() {
            val s = server ?: return
            // on the USB cable: backup mode stays on (no timeout while the cable is in, user 2026-11-17)
            if (UsbDebug.Guard.cableHolds(this@BackupService)) s.keepAlive()
            if (System.currentTimeMillis() - s.lastActivity > IDLE_MS) {
                stopSelf()
                return
            }
            main.postDelayed(this, 5_000)
        }
    }
    // every second: debugging guard (UsbDebug) + anonymous announcement (new token every 10 min)
    private val tick = object : Runnable {
        override fun run() {
            UsbDebug.Guard.tick(this@BackupService)?.let { AppState.status = it; notify(it) }
            server?.let {
                Announce.refresh(this@BackupService, it.port)
                val left = IDLE_MS - (System.currentTimeMillis() - it.lastActivity)
                AppState.onCable = UsbDebug.Guard.cableHolds(this@BackupService)
                AppState.idleLeft = if (left > 0 && !AppState.onCable) "%d:%02d".format(left / 60_000, left / 1000 % 60) else ""
            }
            main.postDelayed(this, 1000)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    // Started again (e.g. the computer opened the app over the cable): if the server had to take a
    // random port because another app held the usual one (an OLD copy of this app, user 2026-11-17),
    // move to the usual port now if it is free – the computer reaches the app over the cable there.
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val old = server
        if (old != null && old.port != Server.PREFERRED_PORT) {
            val srv = Server(this) { ev -> main.post { onServerEvent(ev) } }
            try {
                srv.start()
                if (srv.port == Server.PREFERRED_PORT) {
                    old.stop()
                    server = srv
                    AppState.port = srv.port
                    Announce.refresh(this, srv.port)
                } else {
                    srv.stop()
                }
            } catch (_: Exception) {
                runCatching { srv.stop() }
            }
        }
        return super.onStartCommand(intent, flags, startId)
    }

    // USB cable plugged in during a Wi-Fi backup: switch to the cable (UsbDebug.Guard.cablePlugged)
    private val power = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) = checkCable()
    }

    private fun checkCable() {
        val b = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return
        if (b.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) != BatteryManager.BATTERY_PLUGGED_USB) return
        if (UsbDebug.Guard.cablePlugged(this)) {
            val t = tr("USB cable plugged in – the backup continues over the faster cable.")
            AppState.status = t
            notify(t)
        }
    }

    override fun onCreate() {
        super.onCreate()
        I18n.load(this)                      // notification texts (also without the activity)
        val nm = getSystemService(NotificationManager::class.java)
        nm.cancel(AskService.ASK_NOTIFICATION)        // "Allow backup?" answered
        nm.createNotificationChannel(NotificationChannel(CHANNEL, tr("Backup mode"), NotificationManager.IMPORTANCE_LOW))
        val n = notification(tr("Waiting for the computer – photos and videos are shared read-only."))
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(1, n)
        }
        wake = (getSystemService(POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "phonebackup:server").apply { acquire(4 * 3600_000L) }
        @Suppress("DEPRECATION")
        wifiLock = (applicationContext.getSystemService(WIFI_SERVICE) as WifiManager)
            .createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "phonebackup:wifi").apply { acquire() }

        val srv = Server(this) { ev -> main.post { onServerEvent(ev) } }
        try {
            srv.start()
        } catch (e: Exception) {
            AppState.status = tr("Could not start: %s", e.message ?: "")
            stopSelf()
            return
        }
        server = srv
        AppState.running = true
        AppState.port = srv.port
        AppState.status = tr("Waiting for the computer …")
        Announce.refresh(this, srv.port)
        main.postDelayed(idleCheck, 5_000)
        main.postDelayed(tick, 1000)
        registerReceiver(power, IntentFilter(Intent.ACTION_POWER_CONNECTED))
        guardCheck = object : Runnable {           // the cable may already be in when the backup starts
            override fun run() { checkCable(); main.postDelayed(this, 10_000) }
        }.also { main.postDelayed(it, 10_000) }
    }

    private var guardCheck: Runnable? = null

    private fun onServerEvent(ev: String) {
        if (ev == "DONE") {
            finished = true
            AppState.status = tr("Backup finished – backup mode switched off.")
            stopSelf()
            return
        }
        if (ev == "PAIR_REQUEST") {
            val t = tr("%s wants to pair over the USB cable – open the app to confirm.", CablePairing.pendingName ?: tr("A computer"))
            AppState.status = t
            notify(t)
            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return
        }
        if (ev == "PAIR_CODE") return            // the app screen picks the code up itself
        if (ev.startsWith("PAIRED\n")) {
            AppState.pairedChanged++
            AppState.pairings++
            AskService.startIfEnabled(this)        // first computer paired: listener on (default)
            Announce.stop(this)                    // announce the new computer's token too
            val t = tr("Paired with %s", ev.substringAfter('\n'))
            AppState.status = t
            notify(t)
            return
        }
        AppState.status = ev
        notify(ev)
    }

    private fun notify(text: String) =
        getSystemService(NotificationManager::class.java).notify(1, notification(text))

    private fun notification(text: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle(tr("Backup mode on"))
            .setContentText(text)
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        main.removeCallbacksAndMessages(null)
        runCatching { unregisterReceiver(power) }
        Announce.stop(this)
        if (UsbDebug.Guard.engaged) UsbDebug.switchOff(this)     // backup mode ends → debugging off
        server?.stop()
        server = null
        runCatching { wifiLock?.release() }
        runCatching { if (wake?.isHeld == true) wake?.release() }
        AppState.running = false
        AppState.port = 0
        if (!finished) AppState.status = tr("Backup mode is off.")
        super.onDestroy()
    }
}
