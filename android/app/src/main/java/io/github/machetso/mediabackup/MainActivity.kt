package io.github.machetso.mediabackup

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Checkbox
import androidx.compose.foundation.selection.selectable
import androidx.compose.ui.semantics.Role
import androidx.compose.material3.ButtonDefaults
import androidx.compose.ui.graphics.Color
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import java.util.Locale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.concurrent.thread

class MainActivity : ComponentActivity() {
    private var hasAccess by mutableStateOf(false)
    private var hasNetwork by mutableStateOf(false)
    private var vpnOn by mutableStateOf(false)          // a VPN blocks the computer (2026-11-20)
    private var pairCode by mutableStateOf<String?>(null)
    private var pairInfo by mutableStateOf("")
    private var pairReady by mutableStateOf(false)    // code shown: waiting for the user's tap
    private var canSwitchUsb by mutableStateOf(false)
    private var connectInfo by mutableStateOf("")
    private var askOn by mutableStateOf(false)
    private var askFrom by mutableStateOf("")        // "Allow backup?" tapped: the computer that asks
    private var autoOn by mutableStateOf(false)
    private var selfOn by mutableStateOf(false)

    /** Automatic backup must start backup mode from the background: Android allows that only for
     *  apps the user lets run unrestricted (battery). Asks once; without it the phone shows
     *  "Allow backup?" instead. */
    /** What is missing for "Back up now" – null when it can start (user request 2026-11-20: the
     *  button is grey then and a tap says what is missing, also which setting on the computer). */
    private fun missingForBackup(paired: Boolean, now: Long): String? {
        val info = BackupStatus.info
        val fresh = info != null && now - info.at < BackupStatus.FRESH_MS
        val cable = UsbDebug.cableIn(this) && canSwitchUsb
        return when {
            !hasAccess -> tr("Allow access to photos and videos first (“Allow access” on this screen).")
            !paired -> tr("Pair this phone with your computer first: in the computer program click " +
                "“Connect phone…” and scan the QR code.")
            !fresh && !cable -> tr("Your computer was not found. Open “My Mobile Media Backup” on the computer – " +
                "this phone must be in the same Wi-Fi, or plug in the USB cable.") +
                (if (vpnOn) " " + tr("A VPN is on: exclude this app from the VPN.") else "")
            fresh && info!!.ready == "no_backup" -> tr("Your computer has no backup of this phone yet: in the " +
                "computer program click “New backup…” and back up this phone once.")
            fresh && info!!.ready == "no_drive" -> tr("The backup drive is not connected to the computer: plug it " +
                "in. Or choose another one in the computer program: Manage backups → choose this backup under " +
                "“Your backups” → tab “Backup drives”.")
            fresh && info!!.ready == "busy" -> tr("Your computer is busy with another job – try again in a moment.")
            BackupStatus.photos == 0 && BackupStatus.videos == 0 -> tr("Everything is backed up.")
            else -> null
        }
    }

    /** "23 photos and 4 videos not backed up yet" + "Back up now" (user request 2026-11-20). */
    @Composable
    private fun BackupNowPanel(paired: Boolean) {
        var now by remember { mutableStateOf(System.currentTimeMillis()) }
        var why by remember { mutableStateOf("") }
        androidx.compose.runtime.LaunchedEffect(Unit) {
            BackupStatus.load(this@MainActivity)
            while (true) {                          // count again every half minute
                thread { BackupStatus.count(this@MainActivity) }
                now = System.currentTimeMillis()
                kotlinx.coroutines.delay(30_000)
            }
        }
        val p = BackupStatus.photos
        val v = BackupStatus.videos
        val missing = missingForBackup(paired, now)
        Panel(tr("Backup"), Lcars.GOLD) {
            run {
                Text(when {
                    p < 0 -> tr("Not known yet – your computer has not looked at this phone yet.")
                    p == 0 && v == 0 -> tr("Everything is backed up.")
                    else -> tr("%s and %s (%s) not backed up yet.", trp("%d photo", "%d photos", p, p),
                        trp("%d video", "%d videos", v, v), BackupStatus.sizeText(BackupStatus.bytes))
                }, fontWeight = FontWeight.SemiBold)
                val ready = missing == null
                Button(onClick = {
                    if (!ready) { why = missing ?: ""; return@Button }
                    why = ""
                    BackupStatus.wantAt = System.currentTimeMillis()
                    if (canSwitchUsb && !UsbDebug.Guard.engaged) UsbDebug.switchOnAdb(this@MainActivity)
                    BackupService.start(this@MainActivity)
                    UsbDebug.Guard.tick(this@MainActivity)
                }, colors = if (ready) ButtonDefaults.buttonColors(containerColor = Glow.ON, contentColor = Color.White)
                            else ButtonDefaults.buttonColors(containerColor = Color(0xFF555555), contentColor = Color(0xFFBBBBBB))) {
                    Text(label(tr("Back up now")))
                }
                if (BackupStatus.wanted(now) && !AppState.isCopying(now))
                    Text(tr("Waiting for your computer – the backup starts by itself."),
                        style = MaterialTheme.typography.bodySmall)
                if (why.isNotEmpty() && !ready) Text(why, style = MaterialTheme.typography.bodySmall)
            }
        }
    }

    /** Is a VPN on (any network with the VPN transport)? */
    private fun vpnActive(): Boolean = runCatching {
        val cm = getSystemService(android.net.ConnectivityManager::class.java)
        cm.allNetworks.any {
            cm.getNetworkCapabilities(it)?.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN) == true
        }
    }.getOrDefault(false)

    private fun askUnrestricted() {
        val pm = getSystemService(android.os.PowerManager::class.java)
        if (pm.isIgnoringBatteryOptimizations(packageName)) return
        runCatching {
            startActivity(Intent(android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                android.net.Uri.parse("package:$packageName")))
        }
    }

    private val askMedia = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        refresh()
    }

    private fun refresh() {
        hasAccess = MediaIndex.hasFullAccess(this)
        hasNetwork = MediaIndex.hasLocalNetwork(this)
        vpnOn = vpnActive()
        canSwitchUsb = UsbDebug.canSwitch(this)
        askOn = AskService.enabled(this)
        autoOn = AskService.autoEnabled(this)
        selfOn = AskService.selfEnabled(this)
        AskService.startIfEnabled(this)          // e.g. after the app was updated or stopped
        UsbDebug.Guard.tick(this)?.let { AppState.status = it }   // saved countdown (after update/kill)
        if (hasNetwork) waitingPair?.let { startPairing(it) }
    }

    private fun askAll() {
        val list = MediaIndex.PERMISSIONS.toMutableList()
        if (MediaIndex.needsLocalNetwork()) list += MediaIndex.LOCAL_NETWORK
        if (Build.VERSION.SDK_INT >= 31) list += Manifest.permission.BLUETOOTH_ADVERTISE   // only to be found
        askMedia.launch(list.toTypedArray())
    }
    private val askNotify = registerForActivityResult(ActivityResultContracts.RequestPermission()) {}

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        I18n.load(this)
        Look.load(this)
        refresh()
        if (!hasAccess || !hasNetwork) askAll()
        else if (Build.VERSION.SDK_INT >= 33) askNotify.launch(Manifest.permission.POST_NOTIFICATIONS)
        handle(intent)
        // no taps through an overlay of another app (tapjacking): "Allow fast connection (ADB)",
        // "Pair" … only count when this window is fully visible
        window.decorView.filterTouchesWhenObscured = true
        setContent {
            // right-to-left languages (Hebrew) mirror the layout; I18n.choice is state → redraws at once
            CompositionLocalProvider(LocalLayoutDirection provides
                if (I18n.current.rtl) LayoutDirection.Rtl else LayoutDirection.Ltr) {
                AppTheme {
                    Surface(Modifier.fillMaxSize()) { Screen() }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    private var waitingPair: Pairing.Pending? = null
    private var seenPairings = AppState.pairings     // a new pairing closes the pairing card

    private fun handle(intent: Intent?) {
        intent?.getStringExtra(AskService.EXTRA_ASK)?.let { pc ->
            setIntent(Intent())
            askFrom = pc
            return
        }
        // the computer opened the app over the cable (pairing over USB / setup): start backup mode
        if (intent?.data?.scheme == "phonebackup" && intent.data?.host == "cable") {
            setIntent(Intent())
            BackupService.start(this)
            return
        }
        val data = intent?.data
        // "Connect phone" QR code of a paired computer: backup mode on, then tell the computer
        data?.let { Connect.parse(this, it) }?.let { (req, err) ->
            setIntent(Intent())
            if (req == null) { connectInfo = err; return }
            connectInfo = tr("Connecting to %s …", req.pc.name)
            BackupService.start(this)
            thread {
                var tries = 0
                while (BackupService.server?.port.let { it == null || it == 0 } && tries++ < 50) Thread.sleep(100)
                val e = Connect.tellComputer(this, req, BackupService.server?.port ?: 0)
                runOnUiThread {
                    connectInfo = e?.let { tr("%s – the computer may still find the phone in the Wi-Fi.", it) }
                        ?: tr("Connected to %s – start the backup on the computer.", req.pc.name)
                }
            }
            return
        }
        val p = data?.let { Pairing.parse(it) }
        if (p == null) {
            if (data?.scheme == "phonebackup" && data.host == "pair") {
                setIntent(Intent())
                pairCode = null
                val t = data.getQueryParameter("t").orEmpty()
                connectInfo = if (t.isNotEmpty() && !Regex("[0-9a-f]{64}").matches(t))
                    tr("This computer program is too old for the app. Update “My Mobile Media Backup” on the computer, then try again.")
                else tr("Pairing link refused: the computer must be in your local network.")
            }
            return
        }
        setIntent(Intent())          // do not pair again on rotation
        pairCode = ""                // card shows "waiting for the computer's code" until revealed
        pairReady = false
        if (!MediaIndex.hasLocalNetwork(this)) {
            waitingPair = p
            pairInfo = tr("Allow access to the local network first (button below).")
            return
        }
        startPairing(p)
    }

    private fun startPairing(p: Pairing.Pending) {
        waitingPair = null
        pairInfo = tr("Connecting to %s …", p.pcName)
        BackupService.start(this)
        thread {
            var tries = 0
            while (BackupService.server?.port.let { it == null || it == 0 } && tries++ < 50) Thread.sleep(100)
            var err = Pairing.announce(this, p, BackupService.server?.port ?: 0)
            if (err == null) {
                runOnUiThread { pairInfo = tr("Waiting for the code from %s …", p.pcName) }
                // the computer now hands over its key over the encrypted connection (/reveal)
                val until = System.currentTimeMillis() + 40_000
                while (p.code == null && Pairing.pending === p && System.currentTimeMillis() < until) Thread.sleep(200)
                if (p.code == null && Pairing.pending === p) {
                    err = tr("The computer did not send its code. Update the program on the computer, then try again.")
                }
            }
            runOnUiThread {
                if (Pairing.pending !== p) return@runOnUiThread          // cancelled meanwhile
                pairCode = p.code ?: ""
                pairInfo = err ?: tr("Does “%s” show exactly the same code?", p.pcName)
                pairReady = err == null
            }
        }
    }

    @Composable
    private fun Screen() {
        val running = AppState.running
        @Suppress("UNUSED_VARIABLE") val changed = AppState.pairedChanged
        val computers = Identity.computers(this)
        if (AppState.pairings != seenPairings) { seenPairings = AppState.pairings; pairCode = null }

        Column(
            Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Header("My Mobile Media Backup") { LanguageGlobe() }
            if (askFrom.isNotEmpty() && running) askFrom = ""
            if (askFrom.isNotEmpty()) {
                // the computer's backup request, answered right here (user 2026-11-19)
                Panel(tr("Allow backup?"), Lcars.GOLD) {
                    run {
                        Text(tr("“%s” wants to back up the photos and videos of this phone.", askFrom),
                            fontWeight = FontWeight.SemiBold)
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Button(enabled = hasAccess && hasNetwork, onClick = {
                                BackupService.start(this@MainActivity)
                                getSystemService(android.app.NotificationManager::class.java)
                                    .cancel(AskService.ASK_NOTIFICATION)
                                askFrom = ""
                            }) { Text(label(tr("Allow"))) }
                            TextButton(onClick = {
                                getSystemService(android.app.NotificationManager::class.java)
                                    .cancel(AskService.ASK_NOTIFICATION)
                                askFrom = ""
                            }) { Text(label(tr("Not now"))) }
                        }
                    }
                }
            }
            // short and without technical details (user request 2026-11-20)
            Text(tr("The phone part of the app: it makes backups easier. It only reads your photos and " +
                "videos – it never changes or deletes anything."),
                style = MaterialTheme.typography.bodyMedium)

            BackupNowPanel(computers.isNotEmpty())

            if (!hasAccess) {
                Panel(tr("Access to photos and videos needed"), Lcars.GOLD) {
                    run {
                        Text(tr("Choose “Allow all” – with “Select photos” only the chosen ones could be backed up."))
                        Button(onClick = { askAll() }) { Text(label(tr("Allow access"))) }
                    }
                }
            }
            // a VPN app (e.g. WireGuard with "all traffic") on: Android lets this app receive
            // connections only through the VPN – the computer in the Wi-Fi gets no answer
            // (found 2026-11-20 with a tunnel to the home router while in another Wi-Fi)
            if (vpnOn && computers.isNotEmpty()) {
                Panel(tr("A VPN is on"), Lcars.GOLD) {
                    run {
                        Text(tr("Your computer may not reach this app. In your VPN app, exclude " +
                            "“My Mobile Media Backup” from the VPN (split tunnelling) – or use the USB cable."))
                    }
                }
            }
            if (!hasNetwork) {
                Panel(tr("Access to the local network needed"), Lcars.GOLD) {
                    run {
                        Text(tr("Without it the computer cannot reach the phone (Android asks for " +
                            "“devices in the local network” / “Nearby devices”)."))
                        Button(onClick = { askAll() }) { Text(label(tr("Allow network access"))) }
                    }
                }
            }

            CablePairing.pendingName?.let { name ->
                Panel(tr("Pair over the USB cable"), Lcars.ORANGE) {
                    run {
                        Text(tr("“%s” wants to back up this phone. Only confirm if this phone is " +
                            "connected to that computer with a cable right now and the computer " +
                            "shows exactly this code:", name))
                        Text(CablePairing.pendingCode.chunked(3).joinToString(" "), fontSize = 32.sp,
                            fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = { CablePairing.answer(true) }) { Text(label(tr("Pair"))) }
                            OutlinedButton(onClick = { CablePairing.answer(false) }) { Text(label(tr("Refuse"))) }
                        }
                    }
                }
            }

            pairCode?.let { code ->
                Panel(tr("Pairing"), Lcars.ORANGE) {
                    run {
                        if (code.isNotEmpty()) {
                            Text(code.chunked(3).joinToString(" "), fontSize = 40.sp,
                                fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                        }
                        Text(pairInfo)
                        if (pairReady) {
                            Text(tr("Only tap “Pair” if you started the pairing yourself and the " +
                                "computer shows exactly this code."), style = MaterialTheme.typography.bodySmall)
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(onClick = {
                                    if (Pairing.confirm()) {
                                        pairInfo = tr("Confirmed – now confirm the same code on the computer.")
                                        pairReady = false
                                    }
                                }) { Text(label(tr("Same code – Pair"))) }
                                OutlinedButton(onClick = { Pairing.cancel(); pairCode = null; pairReady = false }) {
                                    Text(label(tr("Cancel")))
                                }
                            }
                        } else {
                            TextButton(onClick = { Pairing.cancel(); pairCode = null }) { Text(label(tr("Cancel"))) }
                        }
                    }
                }
            }

            // ONE switch "Allow backup" (user request 2026-11-20, the second switch removed the same
            // day): on = the fastest way – USB debugging + Wireless debugging, where the app may
            // switch them – AND backup mode (the app's read-only server: the Wi-Fi way and the
            // computer's line to the app during every backup). Plain words, "Connection established",
            // a countdown; "Disconnect" switches everything off.
            run {
                @Suppress("UNUSED_VARIABLE") val guardText = UsbDebug.Guard.text   // redraw on changes
                val fastOn = UsbDebug.Guard.engaged
                val on = fastOn || running
                // countdown and "Connection established" refresh every second while it is on
                var now by remember { mutableStateOf(System.currentTimeMillis()) }
                androidx.compose.runtime.LaunchedEffect(on, AppState.copyingAt) {
                    while (fastOn || running) { now = System.currentTimeMillis(); kotlinx.coroutines.delay(1_000) }
                    now = System.currentTimeMillis()
                }
                val connected = UsbDebug.connectedOverCable(this@MainActivity) ||
                    (running && now - AppState.contactAt < 30_000)
                Panel(tr("Allow connection to the computer"), Lcars.BLUE, titleSize = 18) {
                    run {
                        Text(tr("The phone connects to your computer by itself, the fastest way possible. " +
                            "The connection switches off by itself after the backup, and 5 minutes after the cable is unplugged."),
                            style = MaterialTheme.typography.bodyMedium)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            GreenSwitch(checked = on,
                                enabled = on || (hasAccess && (canSwitchUsb || (hasNetwork && computers.isNotEmpty()))),
                                onCheckedChange = { want ->
                                    if (want) {
                                        if (canSwitchUsb) UsbDebug.switchOnAdb(this@MainActivity)?.let {
                                            android.widget.Toast.makeText(this@MainActivity, it,
                                                android.widget.Toast.LENGTH_LONG).show()
                                        }
                                        BackupService.start(this@MainActivity)          // runs the guard too
                                    } else {
                                        if (canSwitchUsb) UsbDebug.switchOff(this@MainActivity)
                                        BackupService.stop(this@MainActivity)
                                    }
                                    UsbDebug.Guard.tick(this@MainActivity)
                                })
                            Column(Modifier.padding(start = 10.dp).weight(1f)) {
                                Text(tr("Allow backup"), fontWeight = FontWeight.SemiBold)
                                if (on) Text(if (connected) tr("Connection established") else tr("Not connected"),
                                    color = if (connected) Glow.GREEN_BRIGHT else Lcars.DIM,
                                    style = MaterialTheme.typography.bodySmall)
                            }
                            // a backup is running: the icon's arrow with the moving light (2026-11-19)
                            if (AppState.isCopying(now)) BackupArrow(Modifier.padding(start = 10.dp))
                        }
                        val left = when {
                            fastOn -> UsbDebug.Guard.plainStatus(this@MainActivity)
                            running && AppState.onCable -> tr("Stays on while the cable is plugged in.")
                            running && AppState.idleLeft.isNotEmpty() ->
                                tr("Switches off in %s if not used.", AppState.idleLeft)
                            else -> ""
                        }
                        if (left.isNotEmpty()) Text(left, fontWeight = FontWeight.SemiBold)
                        if (AppState.status.isNotEmpty()) Text(AppState.status, style = MaterialTheme.typography.bodySmall)
                        if (connectInfo.isNotEmpty()) Text(connectInfo, fontWeight = FontWeight.SemiBold)
                        if (computers.isEmpty()) Text(tr("Not paired yet: on the computer click " +
                            "“Connect phone…” and scan the QR code."), style = MaterialTheme.typography.bodySmall)
                        DisconnectButton(tr("Disconnect"), active = on) {
                            if (canSwitchUsb) UsbDebug.switchOff(this@MainActivity)
                            BackupService.stop(this@MainActivity)
                            UsbDebug.Guard.tick(this@MainActivity)
                        }
                    }
                }
            }

            if (computers.isNotEmpty()) {
                val mode = if (!askOn) "never" else if (autoOn) "auto" else "ask"
                Panel(tr("When your computer wants a backup"), Lcars.LILAC, spacing = 2) {
                    run {
                        // only the options, no explaining texts (user request 2026-11-20)
                        listOf(
                            "ask" to tr("Ask me"),
                            "auto" to tr("Allow without asking"),
                            "never" to tr("Never"),
                        ).forEach { (key, label) ->
                            Row(Modifier.fillMaxWidth().selectable(selected = mode == key, role = Role.RadioButton,
                                onClick = {
                                    AskService.setEnabled(this@MainActivity, key != "never")
                                    AskService.setAuto(this@MainActivity, key == "auto")
                                    askOn = AskService.enabled(this@MainActivity)
                                    autoOn = AskService.autoEnabled(this@MainActivity)
                                    selfOn = AskService.selfEnabled(this@MainActivity)
                                    if (key == "auto") askUnrestricted()
                                }).padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                                RadioButton(selected = mode == key, onClick = null)
                                Text(label, Modifier.padding(start = 8.dp))
                            }
                            // the old "Start automatically" = "Allow without asking" + this box
                            if (key == "auto" && mode == "auto")
                                Row(Modifier.fillMaxWidth().padding(start = 40.dp).selectable(selected = selfOn,
                                    role = Role.Checkbox, onClick = {
                                        AskService.setSelf(this@MainActivity, !selfOn)
                                        selfOn = AskService.selfEnabled(this@MainActivity)
                                    }).padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Checkbox(checked = selfOn, onCheckedChange = null)
                                    Text(tr("Also start by itself"), Modifier.padding(start = 8.dp))
                                }
                        }
                        // with "Never" the phone does not announce itself in the Wi-Fi (user 2026-11-20:
                        // "the computer does not recognize my nearby phone" – the cause was "Never")
                        if (mode == "never") Text(tr("Your computer cannot find this phone nearby."),
                            fontWeight = FontWeight.SemiBold)
                    }
                }
                Panel(tr("Paired computers"), Lcars.MAUVE, card = false, spacing = 0) {
                computers.forEach { pc ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(pc.name, Modifier.weight(1f))
                        TextButton(onClick = {
                            Identity.removeComputer(this@MainActivity, pc.id)
                            AppState.pairedChanged++
                        }) { Text(label(tr("Remove"))) }
                    }
                }
                }
            }
            Spacer(Modifier.padding(8.dp))
            Footer()
            Text(tr("Version %s", BuildConfigInfo.versionName(this@MainActivity)), style = MaterialTheme.typography.bodySmall)
        }
    }

    /** The globe top right: System (phone language if there is a dictionary, else English) or any
     *  dictionary – as on the computer (user request 2026-11-19). */
    @Composable
    private fun LanguageGlobe() {
        var open by remember { mutableStateOf(false) }
        val phone = Locale.getDefault().getDisplayLanguage(Locale.getDefault()) +
            if (I18n.phoneLanguage == null) " → English" else ""
        val choices = listOf(I18n.SYSTEM to tr("System (%s)", phone)) +
            I18n.languages.map { it.code to (if (it.code == "tlh") "${it.name} (${tr("Klingon")})" else it.name) }
        Box {
            Globe { open = true }
            DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                choices.forEach { (code, name) ->
                    DropdownMenuItem(text = { Text((if (code == I18n.choice) "● " else "   ") + name) }, onClick = {
                        open = false
                        I18n.choose(this@MainActivity, code)
                    })
                }
            }
        }
    }
}
