package io.github.machetso.mediabackup

import android.content.Context
import android.net.Uri
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * The computer's "Connect phone" QR code (user request 2026-11-10; short since 2026-11-20 so the
 * camera reads it at once):  m3b://c/<ip:port>/<nonce 8 hex>/<token>.<token>…
 * One token per phone paired with that computer = HMAC(secret, "m3b-c:<nonce>")[:4] – the phone
 * finds the paired computer whose token matches. The computer's little server accepts the answer
 * only once and only for 5 minutes. Then backup mode starts and the phone tells the computer where
 * it is: POST http://<a>/here {n, port, proof}, proof = HMAC(secret, "fmb-here:<nonce>:<phone ip>:<port>")[:16].
 * The computer then connects over TLS pinned to this phone's key, as always. Same format in
 * phonebackup/wake.py.
 */
object Connect {
    data class Request(val pc: Identity.Computer, val address: String, val nonce: String)

    internal fun hmacHex(secret: String, msg: String, len: Int): String =
        Mac.getInstance("HmacSHA256").run {
            init(SecretKeySpec(secret.toByteArray(Charsets.UTF_8), "HmacSHA256"))
            doFinal(msg.toByteArray(Charsets.UTF_8))
        }.copyOf(len).joinToString("") { "%02x".format(it) }

    /** null = not a connect link; else (request or null, error text). */
    fun parse(ctx: Context, uri: Uri): Pair<Request?, String>? {
        if (uri.scheme != "m3b" || uri.host != "c") return null
        val parts = uri.pathSegments
        if (parts.size != 3) return null to tr("This QR code is not valid.")
        val (addr, nonce, tokenList) = parts
        if (!Pairing.isLocalComputer(addr) || !Regex("[0-9a-f]{8}").matches(nonce))
            return null to tr("This QR code is not valid.")
        val computers = Identity.computers(ctx)
        if (computers.isEmpty())
            return null to tr("This computer is not paired with this phone. Pair it first (on the computer: “Phone app over Wi-Fi…” or the USB cable).")
        val pc = match(computers.map { it to it.secret }, nonce, tokenList.split("."))
            ?: return null to tr("This QR code is not for this phone.")
        return Request(pc, addr, nonce) to ""
    }

    /** The paired computer whose token is in the QR code (constant-time compare), or null. */
    internal fun <T> match(computers: List<Pair<T, String>>, nonce: String, tokens: List<String>): T? =
        computers.firstOrNull { (_, secret) ->
            val mine = token(secret, nonce).toByteArray()
            tokens.any { java.security.MessageDigest.isEqual(it.toByteArray(), mine) }
        }?.first

    internal fun token(secret: String, nonce: String) = hmacHex(secret, "m3b-c:$nonce", 4)

    /** After backup mode started: tell the computer where the phone is (runs in a thread). */
    fun tellComputer(ctx: Context, r: Request, port: Int): String? {
        val ip = Announce.wifiAddress(ctx)?.hostAddress ?: return tr("No Wi-Fi connection.")
        val proof = hmacHex(r.pc.secret, "fmb-here:${r.nonce}:$ip:$port", 16)
        val body = JSONObject().put("n", r.nonce).put("port", port).put("proof", proof).toString().toByteArray()
        return try {
            val c = URL("http://${r.address}/here").openConnection() as HttpURLConnection
            c.requestMethod = "POST"
            c.connectTimeout = 8000
            c.readTimeout = 10000
            c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body) }
            val code = c.responseCode
            c.disconnect()
            if (code == 200) null else tr("The computer answered %d.", code)
        } catch (e: Exception) {
            tr("Could not reach the computer (%s): %s", r.address, e.message ?: "")
        }
    }
}
