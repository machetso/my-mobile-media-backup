package io.github.machetso.mediabackup

import android.content.Context
import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import android.net.wifi.WifiInfo
import android.net.wifi.WifiManager
import org.json.JSONArray
import org.json.JSONObject
import java.net.Inet4Address

/**
 * The user's home Wi-Fi networks (user request 2026-11-23): only there the phone checks whether
 * its paired computer wants a backup. Several can be listed.
 *
 * A Wi-Fi is added while the phone is connected to it ("Trust the current Wi-Fi"): its name and the access
 * point (BSSID) need the location permission – asked once, only while the app is open. Stored as
 * well: the router's address and the network range. In the background (no location permission
 * there) a network counts as home when router address AND network range match – and nothing
 * happens before the paired computer has proved itself with the pairing key (HomeCheck), so a
 * foreign Wi-Fi with the same name gets nothing.
 */
object HomeWifi {
    private const val PREFS = "home_wifi"
    private const val KEY = "nets"

    data class Net(val name: String, val gateway: String, val subnet: String, val bssids: Set<String>) {
        fun json(): JSONObject = JSONObject().put("name", name).put("gw", gateway).put("net", subnet)
            .put("bssid", JSONArray(bssids.toList()))

        companion object {
            // "Wi-Fi (router 192.168.…)" of the first build = no name (no addresses shown, 2026-11-23)
            fun of(o: JSONObject) = Net(o.optString("name").takeUnless { it.startsWith("Wi-Fi (router ") } ?: "",
                o.optString("gw"), o.optString("net"),
                o.optJSONArray("bssid")?.let { a -> (0 until a.length()).map { a.getString(it) }.toSet() } ?: emptySet())
        }
    }

    /** What the phone sees of the Wi-Fi it is connected to right now (null = not in a Wi-Fi). */
    data class Seen(val name: String, val bssid: String, val gateway: String, val subnet: String)

    fun list(ctx: Context): List<Net> = runCatching {
        val a = JSONArray(ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, "[]"))
        (0 until a.length()).map { Net.of(a.getJSONObject(it)) }
    }.getOrDefault(emptyList())

    private fun save(ctx: Context, nets: List<Net>) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY, JSONArray(nets.map { it.json() }).toString()).apply()
    }

    fun remove(ctx: Context, net: Net) = save(ctx, list(ctx).filter { it != net })

    /** "Trust the current Wi-Fi": the current one (with name and BSSID if the location permission is given).
     *  Returns the stored entry or null (not in a Wi-Fi). An entry with the same router + range is
     *  replaced (name / access points updated). */
    fun addCurrent(ctx: Context): Net? {
        val s = seen(ctx) ?: return null
        val old = list(ctx)
        val same = old.firstOrNull { it.gateway == s.gateway && it.subnet == s.subnet }
        val name = s.name.ifEmpty { same?.name ?: "" }       // never the router's address (user 2026-11-23)
        val bssids = (same?.bssids ?: emptySet()) + listOfNotNull(s.bssid.takeIf { validBssid(it) })
        val net = Net(name, s.gateway, s.subnet, bssids)
        save(ctx, old.filter { it !== same } + net)
        return net
    }

    /** A new access point of a home network (mesh, second router) – only after the paired computer
     *  answered there (HomeCheck), never by itself. */
    fun learnBssid(ctx: Context, net: Net, bssid: String) {
        if (!validBssid(bssid) || bssid in net.bssids) return
        save(ctx, list(ctx).map { if (it == net) it.copy(bssids = it.bssids + bssid) else it })
    }

    /** The home network the phone is in now, or null. */
    fun current(ctx: Context): Net? {
        val s = seen(ctx) ?: return null
        return match(list(ctx), s)
    }

    /** Matching (also used by the unit test): router address AND network range; when the phone can
     *  see the access point (permission given), a known access point or the same name as well. */
    fun match(nets: List<Net>, s: Seen): Net? = nets.firstOrNull { n ->
        n.gateway.isNotEmpty() && n.gateway == s.gateway && n.subnet == s.subnet &&
            (!validBssid(s.bssid) || n.bssids.isEmpty() || s.bssid in n.bssids || (s.name.isNotEmpty() && s.name == n.name))
    }

    fun validBssid(b: String) = b.isNotEmpty() && b != "02:00:00:00:00:00" && b != "00:00:00:00:00:00"

    /** The Wi-Fi the phone is connected to (router, range; name/BSSID when allowed), or null. */
    fun seen(ctx: Context): Seen? {
        val cm = ctx.getSystemService(ConnectivityManager::class.java) ?: return null
        val net: Network = cm.allNetworks.firstOrNull { n ->
            cm.getNetworkCapabilities(n)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
        } ?: return null
        val lp: LinkProperties = cm.getLinkProperties(net) ?: return null
        val v4 = lp.linkAddresses.firstOrNull { it.address is Inet4Address } ?: return null
        val gw = lp.routes.firstOrNull { it.isDefaultRoute && it.gateway is Inet4Address }?.gateway?.hostAddress ?: ""
        val subnet = networkOf(v4.address.address, v4.prefixLength) + "/" + v4.prefixLength
        // the name and access point: Android 12+ hides them in the network's own info – the Wi-Fi
        // manager or a query WITH location info shows them (permission + Location on); 2026-11-23
        var name = ""
        var bssid = ""
        val infos = listOfNotNull(
            @Suppress("DEPRECATION") ctx.applicationContext.getSystemService(WifiManager::class.java)?.connectionInfo,
            locatedInfo(cm),
            cm.getNetworkCapabilities(net)?.transportInfo as? WifiInfo)
        for (info in infos) {
            val n = info.ssid.orEmpty().removeSurrounding("\"").takeIf { it != "<unknown ssid>" } ?: ""
            val b = info.bssid.orEmpty().lowercase()
            if (name.isEmpty() && n.isNotEmpty()) name = n
            if (!validBssid(bssid) && validBssid(b)) bssid = b
            if (name.isNotEmpty() && validBssid(bssid)) break
        }
        return Seen(name, bssid, gw, subnet)
    }

    /** The Wi-Fi network itself (the check-in is sent over it, not over mobile data / a VPN). */
    fun wifiNetwork(ctx: Context): Network? {
        val cm = ctx.getSystemService(ConnectivityManager::class.java) ?: return null
        return cm.allNetworks.firstOrNull { n ->
            cm.getNetworkCapabilities(n)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
        }
    }

    /** "192.168.178.0/24" → "192.168.178.255": the broadcast address of the network (2026-11-23:
     *  255.255.255.255 alone did not reliably leave the phone over the Wi-Fi). */
    fun broadcastOf(subnet: String): String? {
        val (net, p) = subnet.split("/").takeIf { it.size == 2 } ?: return null
        val prefix = p.toIntOrNull() ?: return null
        val parts = net.split(".").mapNotNull { it.toIntOrNull() }
        if (parts.size != 4 || prefix !in 1..30) return null
        val ip = parts.fold(0L) { acc, b -> (acc shl 8) or b.toLong() }
        val bc = ip or ((1L shl (32 - prefix)) - 1)
        return "${bc shr 24 and 0xff}.${bc shr 16 and 0xff}.${bc shr 8 and 0xff}.${bc and 0xff}"
    }

    /** The Wi-Fi info with name and access point (Android 12+: a callback that asks for location
     *  info; answers at once for the current network). Null when not possible. */
    private fun locatedInfo(cm: ConnectivityManager): WifiInfo? {
        if (android.os.Build.VERSION.SDK_INT < 31) return null
        val got = java.util.concurrent.atomic.AtomicReference<WifiInfo?>(null)
        val latch = java.util.concurrent.CountDownLatch(1)
        val cb = object : ConnectivityManager.NetworkCallback(FLAG_INCLUDE_LOCATION_INFO) {
            override fun onCapabilitiesChanged(n: Network, caps: NetworkCapabilities) {
                (caps.transportInfo as? WifiInfo)?.let { got.set(it); latch.countDown() }
            }
        }
        val ht = android.os.HandlerThread("wifi-name").apply { start() }      // never the caller's thread
        return try {
            cm.registerNetworkCallback(android.net.NetworkRequest.Builder()
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build(), cb, android.os.Handler(ht.looper))
            latch.await(800, java.util.concurrent.TimeUnit.MILLISECONDS)
            got.get()
        } catch (e: Exception) {
            null
        } finally {
            runCatching { cm.unregisterNetworkCallback(cb) }
            ht.quitSafely()
        }
    }

    /** A stored Wi-Fi without its real name gets it when the phone is in it and can read it. */
    fun fixNames(ctx: Context) {
        val s = seen(ctx) ?: return
        if (s.name.isEmpty()) return
        val nets = list(ctx)
        val hit = match(nets, s) ?: return
        if (hit.name == s.name) return
        save(ctx, nets.map { if (it == hit) it.copy(name = s.name) else it })
    }

    fun networkOf(addr: ByteArray, prefix: Int): String {
        val ip = addr.fold(0L) { acc, b -> (acc shl 8) or (b.toLong() and 0xff) }
        val mask = if (prefix == 0) 0L else (0xffffffffL shl (32 - prefix)) and 0xffffffffL
        val n = ip and mask
        return "${n shr 24 and 0xff}.${n shr 16 and 0xff}.${n shr 8 and 0xff}.${n and 0xff}"
    }
}
