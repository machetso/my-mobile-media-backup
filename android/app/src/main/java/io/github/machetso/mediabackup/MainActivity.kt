package io.github.machetso.mediabackup

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
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
    private var pairCode by mutableStateOf<String?>(null)
    private var pairInfo by mutableStateOf("")
    private var pairReady by mutableStateOf(false)    // code shown: waiting for the user's tap
    private var canSwitchUsb by mutableStateOf(false)
    private var usbInfo by mutableStateOf("")
    private var usbOnInfo by mutableStateOf("")      // "… is on" – shown only while the guard runs
    private var connectInfo by mutableStateOf("")
    private var askOn by mutableStateOf(false)
    private var autoOn by mutableStateOf(false)

    /** Automatic backup must start backup mode from the background: Android allows that only for
     *  apps the user lets run unrestricted (battery). Asks once; without it the phone shows
     *  "Allow backup?" instead. */
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
        canSwitchUsb = UsbDebug.canSwitch(this)
        askOn = AskService.enabled(this)
        autoOn = AskService.autoEnabled(this)
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
                MaterialTheme(colorScheme = if (isSystemInDarkTheme()) darkColorScheme() else lightColorScheme()) {
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
                usbInfo = if (t.isNotEmpty() && !Regex("[0-9a-f]{64}").matches(t))
                    tr("This computer program is too old for the app. Update “My Smartphone Media Backup” on the computer, then try again.")
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
            Text("My Media Backup", fontSize = 26.sp, fontWeight = FontWeight.Bold)
            Text(tr("Lets your computer back up the photos and videos of this phone. " +
                "The app can only READ photos and videos – it cannot delete or change anything. " +
                "If the computer set it up, it can also switch USB debugging on for a backup over the cable."),
                style = MaterialTheme.typography.bodyMedium)

            if (!hasAccess) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(tr("Access to photos and videos needed"), fontWeight = FontWeight.SemiBold)
                        Text(tr("Choose “Allow all” – with “Select photos” only the chosen ones could be backed up."))
                        Button(onClick = { askAll() }) { Text(tr("Allow access")) }
                    }
                }
            }
            if (!hasNetwork) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(tr("Access to the local network needed"), fontWeight = FontWeight.SemiBold)
                        Text(tr("Without it the computer cannot reach the phone (Android asks for " +
                            "“devices in the local network” / “Nearby devices”)."))
                        Button(onClick = { askAll() }) { Text(tr("Allow network access")) }
                    }
                }
            }

            CablePairing.pendingName?.let { name ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(tr("Pair over the USB cable"), fontWeight = FontWeight.SemiBold)
                        Text(tr("“%s” wants to back up this phone. Only confirm if this phone is " +
                            "connected to that computer with a cable right now and the computer " +
                            "shows exactly this code:", name))
                        Text(CablePairing.pendingCode.chunked(3).joinToString(" "), fontSize = 32.sp,
                            fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = { CablePairing.answer(true) }) { Text(tr("Pair")) }
                            OutlinedButton(onClick = { CablePairing.answer(false) }) { Text(tr("Refuse")) }
                        }
                    }
                }
            }

            pairCode?.let { code ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(tr("Pairing"), fontWeight = FontWeight.SemiBold)
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
                                }) { Text(tr("Same code – Pair")) }
                                OutlinedButton(onClick = { Pairing.cancel(); pairCode = null; pairReady = false }) {
                                    Text(tr("Cancel"))
                                }
                            }
                        } else {
                            TextButton(onClick = { Pairing.cancel(); pairCode = null }) { Text(tr("Cancel")) }
                        }
                    }
                }
            }

            if (canSwitchUsb) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        // one button for cable AND Wi-Fi ADB + "standard connection" (user request 2026-11-17)
                        Text(tr("Enable fastest connection"), fontWeight = FontWeight.SemiBold, fontSize = 18.sp)
                        Text(tr("“Allow fast connection (ADB)” switches on USB debugging and Wireless debugging. The computer " +
                            "uses the fastest: the USB cable if it is plugged in, otherwise the Wi-Fi. While " +
                            "the cable stays plugged in, it stays on; it switches off by itself after the " +
                            "backup and 5 minutes after the cable is unplugged."),
                            style = MaterialTheme.typography.bodyMedium)
                        // the button of the connection that is on shows it, in the desktop's colours
                        // (user request 2026-11-17): fast = light green, standard = dark green
                        val fastOn = UsbDebug.Guard.text.isNotEmpty()
                        val fastColors = ButtonDefaults.buttonColors(containerColor = Color(0xFFA8E6A1),
                            contentColor = Color(0xFF0D3B17))
                        val standardColors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1B5E20),
                            contentColor = Color.White)
                        Button(colors = if (fastOn) fastColors else ButtonDefaults.buttonColors(), onClick = {
                            val err = UsbDebug.switchOnAdb(this@MainActivity)
                            android.widget.Toast.makeText(this@MainActivity,
                                err ?: tr("Fast connection (ADB) is on."), android.widget.Toast.LENGTH_SHORT).show()
                            usbInfo = err ?: ""
                            usbOnInfo = if (err == null) tr("ADB is on – plug in the USB cable, or start the " +
                                "backup on the computer over the Wi-Fi.") else ""
                            if (err == null) BackupService.start(this@MainActivity)   // runs the guard
                        }) { Text(if (fastOn) tr("Fast connection") else tr("Allow fast connection (ADB)")) }
                        Text(tr("Standard connection: ADB off, the phone is reached over the USB cable with " +
                            "“File transfer” – slower, but works without ADB."),
                            style = MaterialTheme.typography.bodySmall)
                        Button(colors = if (fastOn) ButtonDefaults.buttonColors() else standardColors, onClick = {
                            usbOnInfo = ""
                            usbInfo = UsbDebug.switchOff(this@MainActivity) ?: tr("ADB is off.")
                            android.widget.Toast.makeText(this@MainActivity, tr("ADB is off."),
                                android.widget.Toast.LENGTH_SHORT).show()
                            // Android lets only the user choose "File transfer": open the USB settings
                            if (!openUsbSettings()) usbInfo += " " + tr("Now choose “File transfer” in the " +
                                "USB notification (pull down the notifications, tap “USB”).")
                            else usbInfo += " " + tr("Choose “File transfer” here.")
                        }) { Text(if (fastOn) tr("Enable standard connection") else tr("Standard connection")) }
                        if (usbInfo.isNotEmpty()) Text(usbInfo, style = MaterialTheme.typography.bodySmall)
                        // "is on" only while it really is on: the guard switches it off after 5 minutes
                        // without a backup (fix 2026-11-10: the text stayed after the switch-off)
                        if (usbOnInfo.isNotEmpty() && UsbDebug.Guard.text.isNotEmpty())
                            Text(usbOnInfo, style = MaterialTheme.typography.bodySmall)
                        if (UsbDebug.Guard.text.isNotEmpty()) Text(UsbDebug.Guard.text, fontWeight = FontWeight.SemiBold)
                    }
                }
            }

            // Simpler for everyone (user request 2026-11-17): what is happening now = ONE status line;
            // the two switches "Backup requests" + "Automatic backup" = ONE choice with three answers.
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(if (running) tr("Your computer can read photos and videos right now.")
                             else tr("Closed – your computer cannot read anything right now."),
                            Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                        if (running)
                            TextButton(onClick = { BackupService.stop(this@MainActivity) }) { Text(tr("Switch off")) }
                        else
                            TextButton(enabled = hasAccess && hasNetwork && computers.isNotEmpty(),
                                onClick = { BackupService.start(this@MainActivity) }) { Text(tr("Open now")) }
                    }
                    if (AppState.status.isNotEmpty()) Text(AppState.status, style = MaterialTheme.typography.bodySmall)
                    if (connectInfo.isNotEmpty()) Text(connectInfo, fontWeight = FontWeight.SemiBold)
                    if (running) Text(
                        if (AppState.onCable) tr("Stays open while the USB cable is plugged in; closes 5 minutes after " +
                            "it is unplugged.")
                        else if (AppState.idleLeft.isNotEmpty()) tr("Closes by itself after the backup, or after 5 " +
                            "minutes without use (in %s).", AppState.idleLeft)
                        else tr("Closes by itself after the backup, or after 5 minutes without use."),
                        style = MaterialTheme.typography.bodySmall)
                    if (computers.isEmpty()) Text(tr("Not paired yet: on the computer click " +
                        "“Set up phone app…” and scan the QR code."), style = MaterialTheme.typography.bodySmall)
                }
            }

            if (computers.isNotEmpty()) {
                val mode = if (!askOn) "never" else if (autoOn) "auto" else "ask"
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(tr("When your computer wants a backup"), fontWeight = FontWeight.SemiBold)
                        listOf(
                            Triple("ask", tr("Ask me"), tr("The phone shows “Allow backup?” – nothing starts without your tap.")),
                            Triple("auto", tr("Start automatically"), tr("No question: when the computer finds the phone " +
                                "at home or you plug in the USB cable, the newest photos and videos are backed up – at " +
                                "most once per hour, over the fastest connection.")),
                            Triple("never", tr("Never"), tr("The computer cannot ask. Start backups yourself here in the app.")),
                        ).forEach { (key, label, help) ->
                            Row(Modifier.fillMaxWidth().selectable(selected = mode == key, role = Role.RadioButton,
                                onClick = {
                                    AskService.setEnabled(this@MainActivity, key != "never")
                                    AskService.setAuto(this@MainActivity, key == "auto")
                                    askOn = AskService.enabled(this@MainActivity)
                                    autoOn = AskService.autoEnabled(this@MainActivity)
                                    if (key == "auto") askUnrestricted()
                                }).padding(vertical = 4.dp), verticalAlignment = Alignment.Top) {
                                RadioButton(selected = mode == key, onClick = null)
                                Column(Modifier.padding(start = 8.dp)) {
                                    Text(label)
                                    Text(help, style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                        if (mode != "never") Text(tr("Uses a little battery and shows a permanent notification."),
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
                Text(tr("Paired computers"), fontWeight = FontWeight.SemiBold)
                computers.forEach { pc ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(pc.name, Modifier.weight(1f))
                        TextButton(onClick = {
                            Identity.removeComputer(this@MainActivity, pc.id)
                            AppState.pairedChanged++
                        }) { Text(tr("Remove")) }
                    }
                }
            }
            Spacer(Modifier.padding(8.dp))
            LanguageRow()
            Text(tr("Version %s", BuildConfigInfo.versionName(this@MainActivity)), style = MaterialTheme.typography.bodySmall)
        }
    }

    /** Android's USB settings ("File transfer" etc.) – there is no public screen for it, so
     *  try the known ones; false if none opens (then the user takes the USB notification). */
    private fun openUsbSettings(): Boolean {
        val tries = listOf(
            Intent().setClassName("com.android.settings", "com.android.settings.Settings\$UsbDetailsActivity"),
            Intent("android.settings.USB_PREFERENCES"),
        )
        for (i in tries) {
            try {
                startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                return true
            } catch (_: Exception) {
            }
        }
        return false
    }

    /** "Language: …" – System (phone language if there is a dictionary, else English) or any dictionary. */
    @Composable
    private fun LanguageRow() {
        var open by remember { mutableStateOf(false) }
        val phone = Locale.getDefault().getDisplayLanguage(Locale.getDefault()) +
            if (I18n.phoneLanguage == null) " → English" else ""
        val choices = listOf(I18n.SYSTEM to tr("System (%s)", phone)) +
            I18n.languages.map { it.code to (if (it.code == "tlh") "${it.name} (${tr("Klingon")})" else it.name) }
        val chosen = choices.firstOrNull { it.first == I18n.choice }?.second ?: choices.first().second
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(tr("Language"), style = MaterialTheme.typography.bodySmall)
            Column {
                TextButton(onClick = { open = true }) { Text(chosen) }
                DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                    choices.forEach { (code, label) ->
                        DropdownMenuItem(text = { Text(label) }, onClick = {
                            open = false
                            I18n.choose(this@MainActivity, code)
                        })
                    }
                }
            }
        }
    }
}
