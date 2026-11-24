package io.github.machetso.mediabackup

import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.os.PowerManager
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.security.MessageDigest
import java.security.SecureRandom
import kotlin.concurrent.thread

/**
 * Battery-saving backup requests (user request 2026-11-23): nothing runs all the time. Android wakes
 * the app when the phone joins a Wi-Fi, when it is charging, and every 30 minutes; the app then looks
 * whether it is in one of the user's home Wi-Fi networks (HomeWifi) and asks its paired computer(s)
 * with a short signed UDP message whether a backup is wanted:
 *
 *   phone → computer (broadcast in the Wi-Fi + the computer's last address), port 47826:
 *     {"v":1, "ph": phone id, "pc": computer id, "n": nonce (16 hex), "t": unix s, "m": "ask"|"auto",
 *      "w": number of home Wi-Fis, "b": 1 = battery unrestricted, "av": app version,
 *      "p": HMAC-SHA256(secret, "fmb-hello:<ph>:<pc>:<n>:<t>:<m>:<w>:<b>")[:16] hex}
 *   computer → phone (only a computer that knows the pairing key can answer):
 *     {"pc", "n", "want": true|false, "p": HMAC-SHA256(secret, "fmb-hello-ok:<ph>:<pc>:<n>:<want>")[:16] hex}
 *
 * "Allow without asking": backup mode starts; "Ask me": the "Allow backup?" notification; "Never":
 * nothing is scheduled at all. Same format in phonebackup/hello.py.
 *
 * Version 2 (user request 2026-11-24: the computer must see the phone in ANY Wi-Fi, e.g. the office):
 * the phone checks in in every Wi-Fi, so the message carries nothing that identifies it:
 *   {"v":2, "k": HMAC(secret, "fmb-hello-id:<n>")[:8] hex (new with every nonce), "n", "t", "m", "w",
 *    "b", "h": 1 = in a trusted Wi-Fi, "p": HMAC(secret, "fmb-hello2:<k>:<n>:<t>:<m>:<w>:<b>:<h>")[:16]}
 *   answer {"v":2, "n", "want", "p": HMAC(secret, "fmb-hello-ok2:<n>:<want>")[:16]}
 * Outside a trusted Wi-Fi backup mode never starts by itself – a wanted backup is asked ("Allow backup?").
 */
object HomeCheck {
    const val PORT = 47826
    private const val JOB_NOW = 4101           // after "joined a Wi-Fi"
    private const val JOB_PERIODIC = 4102      // every 30 minutes
    private const val JOB_CHARGING = 4103      // charging
    private const val PREFS = "home_check"
    const val EVERY_MS = 30 * 60_000L

    fun helloProof(secret: String, ph: String, pc: String, n: String, t: Long, m: String, w: Int, b: Int) =
        Connect.hmacHex(secret, "fmb-hello:$ph:$pc:$n:$t:$m:$w:$b", 16)

    fun replyProof(secret: String, ph: String, pc: String, n: String, want: Boolean) =
        Connect.hmacHex(secret, "fmb-hello-ok:$ph:$pc:$n:$want", 16)

    fun helloKey(secret: String, n: String) = Connect.hmacHex(secret, "fmb-hello-id:$n", 8)

    fun helloProof2(secret: String, k: String, n: String, t: Long, m: String, w: Int, b: Int, h: Int) =
        Connect.hmacHex(secret, "fmb-hello2:$k:$n:$t:$m:$w:$b:$h", 16)

    fun replyProof2(secret: String, n: String, want: Boolean) = Connect.hmacHex(secret, "fmb-hello-ok2:$n:$want", 16)

    // any Wi-Fi (2026-11-24): a trusted Wi-Fi is no longer needed to check in – it only decides
    // whether backup mode may start without asking
    private fun wanted(ctx: Context) = AskService.enabled(ctx) && Identity.computers(ctx).isNotEmpty()

    /** (Re-)arm the triggers – or remove them when backup requests are off / nothing to check. */
    fun schedule(ctx: Context) {
        val js = ctx.getSystemService(JobScheduler::class.java) ?: return
        val cm = ctx.getSystemService(ConnectivityManager::class.java)
        val pi = wifiIntent(ctx)
        runCatching { cm?.unregisterNetworkCallback(pi) }
        // the cable needs no Wi-Fi (user 2026-11-23): plugged in → USB debugging on, with "Allow without
        // asking" and a paired computer – the charging trigger also without a trusted Wi-Fi
        val cable = AskService.enabled(ctx) && Identity.computers(ctx).isNotEmpty()
        if (cable) { if (js.getPendingJob(JOB_CHARGING) == null) chargingJob(ctx, 0) } else js.cancel(JOB_CHARGING)
        if (!wanted(ctx)) {
            listOf(JOB_NOW, JOB_PERIODIC).forEach { js.cancel(it) }
            return
        }
        // 1. joined a Wi-Fi: Android sends the intent (the app does not run meanwhile)
        runCatching {
            cm?.registerNetworkCallback(NetworkRequest.Builder()
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build(), pi)
        }
        val svc = ComponentName(ctx, HomeJob::class.java)
        // 2. every 30 minutes (Android bundles it with other work)
        if (js.getPendingJob(JOB_PERIODIC) == null)
            js.schedule(JobInfo.Builder(JOB_PERIODIC, svc).setPeriodic(EVERY_MS)
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED).setPersisted(true).build())
    }

    private fun chargingJob(ctx: Context, delayMs: Long) {
        val js = ctx.getSystemService(JobScheduler::class.java) ?: return
        js.schedule(JobInfo.Builder(JOB_CHARGING, ComponentName(ctx, HomeJob::class.java))
            .setRequiresCharging(true).setMinimumLatency(delayMs).setPersisted(true).build())
    }

    /** "Joined a Wi-Fi": a check soon (needs the network). */
    fun soon(ctx: Context) {
        if (!wanted(ctx)) return
        val js = ctx.getSystemService(JobScheduler::class.java) ?: return
        js.schedule(JobInfo.Builder(JOB_NOW, ComponentName(ctx, HomeJob::class.java))
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setOverrideDeadline(60_000L).build())
    }

    private fun wifiIntent(ctx: Context): PendingIntent = PendingIntent.getBroadcast(ctx, 41,
        Intent(ctx, HomeReceiver::class.java).setAction("io.github.machetso.mediabackup.WIFI"),
        PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)   // Android adds the network

    fun batteryUnrestricted(ctx: Context) =
        ctx.getSystemService(PowerManager::class.java)?.isIgnoringBatteryOptimizations(ctx.packageName) == true

    /** The last check: (time ms, what happened) – shown in the app (user 2026-11-23: "nothing happens"). */
    fun last(ctx: Context): Pair<Long, String>? {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val t = p.getLong("last_at", 0L)
        return if (t == 0L) null else t to p.getString("last_text", "").orEmpty()
    }

    fun remember(ctx: Context, why: String, text: String) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putLong("last_at", System.currentTimeMillis()).putString("last_text", text).putString("last_why", why).apply()
        android.util.Log.i("MediaBackup", "check ($why): $text")
    }

    fun reason(jobId: Int) = when (jobId) {
        JOB_NOW -> tr("Wi-Fi joined")
        JOB_CHARGING -> tr("charging")
        else -> tr("regular check")
    }

    /** The check itself (in a job, off the main thread). Returns what happened (for the log). */
    fun run(ctx: Context, jobId: Int): String {
        I18n.load(ctx)
        if (jobId == JOB_CHARGING && !(AskService.enabled(ctx) && Identity.computers(ctx).isNotEmpty())) return tr("backup requests are off")
        if (jobId == JOB_CHARGING) {
            // armed again at once: every plug-in counts (user 2026-11-23: "ADB on by plugging the cable
            // in"). While it stays plugged in the job comes back every minute or two – a new plug-in
            // is one after a pause of more than 5 minutes (the cable was out)
            chargingJob(ctx, 60_000L)
            val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val now = System.currentTimeMillis()
            val newPlug = now - p.getLong("charging_seen", 0L) > 5 * 60_000L
            p.edit().putLong("charging_seen", now).apply()
            if (!newPlug) return tr("still charging")
            // plugged into a computer (data, not a wall charger) with "Allow without asking" and a
            // paired computer: USB debugging on – the computer then backs up over the cable; the
            // guard switches it off after the backup / 5 minutes after the cable is unplugged
            if (Identity.computers(ctx).isNotEmpty() && AskService.autoEnabled(ctx) &&
                UsbDebug.cableIn(ctx) && UsbDebug.canSwitch(ctx)) {
                UsbDebug.Guard.restore(ctx)
                if (!UsbDebug.Guard.engaged && UsbDebug.switchOnAdb(ctx) == null)
                    return tr("plugged into a computer: USB debugging switched on")
            }
        }
        if (!wanted(ctx)) return tr("backup requests are off")
        if (BackupService.server != null) return tr("backup mode is on already")
        if (HomeWifi.wifiNetwork(ctx) == null) return tr("not in a Wi-Fi")
        val home = HomeWifi.current(ctx)                 // null: a Wi-Fi that is not trusted (office, …)
        val seen = HomeWifi.seen(ctx)
        val pcs = Identity.computers(ctx)
        val mode = if (AskService.autoEnabled(ctx)) "auto" else "ask"
        val answer = hello(ctx, pcs, mode, home != null)
            ?: return tr("no computer answered (is the program running on the computer?)")
        val (pc, want) = answer
        if (home != null && seen != null) HomeWifi.learnBssid(ctx, home, seen.bssid)   // proved: this access point is home
        if (!want) return tr("%s answered: no backup needed now", pc.name)
        if (mode == "auto" && home != null) {
            if (AskService.startBackupMode(ctx)) return tr("%s answered: backup mode started", pc.name)
        }
        AskService.ask(ctx, pc)                // "Ask me" (or a start from the background was not allowed)
        return tr("%s answered: asked you (“Allow backup?”)", pc.name)
    }

    /** Ask every paired computer; the first VALID answer: (computer, wants a backup). */
    fun hello(ctx: Context, pcs: List<Identity.Computer>, mode: String, trusted: Boolean): Pair<Identity.Computer, Boolean>? {
        val h = if (trusted) 1 else 0
        val w = HomeWifi.list(ctx).size
        val b = if (batteryUnrestricted(ctx)) 1 else 0
        val t = System.currentTimeMillis() / 1000
        val prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val sock = runCatching { DatagramSocket().apply { broadcast = true; soTimeout = 1000 } }.getOrNull() ?: return null
        runCatching { HomeWifi.wifiNetwork(ctx)?.bindSocket(sock) }       // out over the Wi-Fi itself
        val directed = HomeWifi.seen(ctx)?.subnet?.let { HomeWifi.broadcastOf(it) }
        try {
            val nonces = HashMap<String, Identity.Computer>()
            for (pc in pcs) {
                val n = ByteArray(8).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it) }
                nonces[n] = pc
                val k = helloKey(pc.secret, n)          // nothing that identifies the phone (any Wi-Fi)
                val msg = JSONObject().put("v", 2).put("k", k).put("n", n).put("t", t)
                    .put("m", mode).put("w", w).put("b", b).put("h", h)
                    .put("p", helloProof2(pc.secret, k, n, t, mode, w, b, h)).toString().toByteArray()
                val targets = listOfNotNull(runCatching { InetAddress.getByName("255.255.255.255") }.getOrNull(),
                    directed?.let { runCatching { InetAddress.getByName(it) }.getOrNull() },
                    prefs.getString("ip_" + pc.id, null)?.let { runCatching { InetAddress.getByName(it) }.getOrNull() })
                for (a in targets) runCatching { sock.send(DatagramPacket(msg, msg.size, a, PORT)) }
            }
            val buf = ByteArray(2048)
            val until = System.currentTimeMillis() + 3000
            while (System.currentTimeMillis() < until) {
                val pkt = DatagramPacket(buf, buf.size)
                try { sock.receive(pkt) } catch (e: SocketTimeoutException) { continue }
                val o = runCatching { JSONObject(String(pkt.data, 0, pkt.length, Charsets.UTF_8)) }.getOrNull() ?: continue
                val pc = nonces[o.optString("n")] ?: continue
                val want = o.optBoolean("want")
                val mine = replyProof2(pc.secret, o.optString("n"), want)
                if (!MessageDigest.isEqual(mine.toByteArray(), o.optString("p").toByteArray())) continue
                prefs.edit().putString("ip_" + pc.id, pkt.address.hostAddress).putLong("last_ok", System.currentTimeMillis()).apply()
                return pc to want
            }
        } finally {
            sock.close()
        }
        return null
    }
}

/** Android's "joined a Wi-Fi" intent (and app update / reboot): arm a check. */
class HomeReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED -> HomeCheck.schedule(context)
            else -> HomeCheck.soon(context)
        }
    }
}

/** The jobs (Wi-Fi joined, every 30 minutes, charging): one short check each. */
class HomeJob : JobService() {
    override fun onStartJob(params: JobParameters): Boolean {
        thread(name = "home-check", isDaemon = true) {
            val text = runCatching { HomeCheck.run(applicationContext, params.jobId) }
                .getOrElse { "error: ${it.javaClass.simpleName}: ${it.message}" }
            HomeCheck.remember(applicationContext, HomeCheck.reason(params.jobId), text)
            jobFinished(params, false)
        }
        return true
    }

    override fun onStopJob(params: JobParameters): Boolean = false
}
