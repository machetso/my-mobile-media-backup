# My Mobile Media Backup

**Version 0.9.9.0**

Backs up the photos and videos of your Android phone to one or more external drives – checked
file by file, sorted by year and month, with a report after every backup. For Windows and Linux.

## Key features

* **One click** – phone and computer show how many photos and videos are not backed up yet (and how
  big they are); one tap on the phone or one click on the computer updates the backup.
* **Only new photos and videos are copied** – the second backup takes minutes, not hours.
* **Every file is checked.** The phone calculates a fingerprint (SHA-256) of each file, the
  program compares it with what arrived and again with what was written to the drive.
* **Several drives at the same time** – the phone is read only once.
* **Sorted automatically** into year and month folders (`2026/26.11`), RAW photos separately.
* **Nothing is ever deleted** – not on the phone, not in the backup.
* **Always the fastest connection** – USB cable, Wi-Fi or the computer's own Wi-Fi; the program
  chooses by itself.
* **Never the wrong phone** – every backup knows its phone; another phone is refused.
* **Automatic backups** – when a known phone comes home, the program can back it up by itself.
* **Second copy** on another drive or on Google Drive, with older states kept
  (Grandfather-Father-Son), and **restore** with one click.
* **Old phones and old drives** can be added to a backup or get a backup of their own.
* A report (text, web page and table) after every backup.
* In German, English, French, Spanish, Romanian, Hebrew and Klingon.

## How it works – in short

The program copies the photos and videos from your phone to an external drive (for example a USB
hard disk). Each phone gets its own folder on the drive: *Owner / Phone*, for example
*Karen / Pixel 10 Pro*. Inside, the photos and videos are sorted into one folder per month.

The program remembers what is already on the drive. Every later backup only adds what is new –
this is why you can simply press **Update backup** once a week.

### Your first backup

1. **Download** the program from the [Releases page](https://github.com/machetso/my-mobile-media-backup/releases)
   and start it – nothing has to be installed. Windows: the `.exe` file. Linux: the `.tar.gz` file.
2. **Plug in the external drive.**
3. **Plug in the phone with its USB cable** and unlock it. If the phone asks what the USB
   connection is for, choose **File transfer**. The coloured bar at the top shows whether the
   phone is connected.
4. Click **New backup…**, enter your name as the **owner** (the phone's name is filled in by
   itself), check the **phone folders** (the camera folder is already there) and tick the
   **backup drive**.
5. Click **Start backup**. The bar at the bottom shows how far it is and how long it takes.
6. When it is done, **Open report** shows what was copied, **Open backup folder** opens the
   photos on the drive.

### Every next backup

Plug in the drive. On the start screen, your phone has its own **Update backup** button – click it.
Only new photos and videos are copied. With the phone app (see *Tips*) the phone does not even have
to be plugged in: when it is in the same Wi-Fi, its line says for example *Nearby – 23 photos and
4 videos (1.5 GB) not backed up yet*, and one click is enough. Or tap **Back up now** on the phone.

### Tips

* **Faster:** switch on *USB debugging* on the phone once (the program shows you how, step by step,
  for your phone model). The backup is then two to four times faster.
* **Without a cable:** install the phone app *My Mobile Media Backup* (*Connect phone…* on the start
  screen shows a QR code). Then the backup works over Wi-Fi, and phone and computer find each other
  by themselves.
* **Two drives** are safer than one: tick both, they are written at the same time.

## Detailed manual

### The window

* **Start screen:** the connection status (red = no phone connected, yellow = something to do on
  the phone, green = connected), **Connect phone…** and **Possible connections**. A known phone in
  the same Wi-Fi is shown as *nearby*, with **Back up now**. **New backup…** starts a backup of
  another phone, or with other folders or drives. Below it **Your phones** – one entry per backup
  with the date of the last backup, how many photos and videos are not backed up yet (when the
  phone is nearby or connected) and its own **Update backup** button. The button is grey while
  one click cannot start the backup; a click then says what is missing.
* **Side bar:** Backup, Manage backups, the gear (program settings), Manual and About. The globe
  top right changes the language.
* **Bottom:** progress, speed and remaining time, with **Cancel** (stops after the current file),
  **Open report** and **Open backup folder**. Every job also writes a log file.

### Connecting the phone

The program always uses the **fastest connection it finds**. If the phone turns up on the USB cable
during a Wi-Fi backup, the backup continues over the cable. **Possible connections** shows every way
to reach the phone with its speed; **Find the fastest connection** checks the cable, the Wi-Fi and
Bluetooth.

| Connection | Speed |
|---|---|
| USB cable + USB debugging (switched on by the phone app, or by hand) | 45–50 MB/s (USB 3), about 20–30 MB/s (USB 2) |
| USB cable, normal file transfer (MTP) | 10–20 MB/s |
| Wi-Fi: phone app or Wireless debugging | 10–40 MB/s, depends on the Wi-Fi |
| Wi-Fi directly to this computer (no router) | 10–30 MB/s |

**USB debugging (ADB).** ADB (Android Debug Bridge) is Google's own USB tool for Android. It is the
fastest and safest way: the phone itself calculates the fingerprint of every file. Android requires
switching it on once by hand – no program can do that before:

1. On the phone: *Settings → About phone* → tap *Build number* 7 times (developer options on).
2. *Settings → System → Developer options* → switch on **USB debugging**.
3. Plug in the phone, unlock it and confirm *Allow USB debugging* with **Always allow from this
   computer**.

*Switch on USB debugging (first time)…* is a step-by-step guide. It recognises the phone on the
cable and has the steps for Pixel, Samsung, Xiaomi / Redmi / POCO, OnePlus / OPPO / realme,
Motorola, Huawei / Honor, Sony and Nothing; for other phones *Search the web for this phone*.

The ADB program itself comes from Google and may not be shipped with this program.
*Program settings → Download ADB…* fetches it directly from Google into the program's own folder –
one click, no installation, no administrator rights. On Linux the system's `adb` package works too.

If ADB does not work, the program says so clearly and uses the phone's normal **file transfer**
(MTP) instead. On Linux the phone is opened automatically; choose *File transfer* in the phone's USB
notification. MTP is slower, and the phone cannot calculate fingerprints – the report says so.

**The phone app *My Mobile Media Backup*.** With the app, backups work over Wi-Fi without USB
debugging, the app switches the fastest connection on and off for you, and phone and computer show
what is not backed up yet.

* **Install:** *Connect phone…* shows two QR codes: one connects the app, the other downloads it
  from the Releases page. Over the USB cable the program can install the app itself; it always
  **asks first** and says which phone, which version and why.
* **Backup:** shows how many photos and videos are not backed up yet and how big they are, for
  example *23 photos and 4 videos (1.5 GB) not backed up yet*. **Back up now** starts the backup:
  the phone connects, the computer updates the backup by itself. When something is missing (the
  computer program is not running, the backup drive is not connected, …) the button is grey and a
  tap says what to do.
* **Allow backup:** one switch. On = the fastest connection – USB debugging and Wireless debugging
  where the app may switch them, and the app's own read-only access over the Wi-Fi. Next to it:
  *Connection established* or *Not connected*; below it how long it stays on. **Disconnect**
  switches everything off. After every backup the computer switches debugging off again
  (*Switch … off after the backup*, on by default). The developer options stay on.
* **When your computer wants a backup:**
  * **Ask me** (default) – the phone asks *Allow backup?*; nothing starts without your tap.
  * **Allow without asking** – one click on the computer starts the backup, no tap on the phone.
    With **Also start by itself**, the newest photos and videos are backed up when the computer
    finds the phone in the Wi-Fi or you plug in the cable (at most once per hour).
  * **Never** – the computer cannot ask and does not find the phone nearby.
* **VPN on the phone:** a VPN that sends everything through the tunnel stops the computer from
  reaching the app over the Wi-Fi. The app shows a hint: exclude *My Mobile Media Backup* from the
  VPN, or use the cable.
* **Same version:** the phone app has the same version number as the program. When it is older,
  the start screen and *Manage backups → Overview* show **Update phone app**. Older copies of the
  app are removed automatically.
* The app can only read photos and videos. The computer asks for every file; the phone answers only
  the paired computer and never sends anything by itself.

**When debugging is switched off again** (the phone app does this even if the computer is gone):

1. Wi-Fi backups normally run through the phone app with debugging off; Wireless debugging is only
   used for phones without the app.
2. One connection per backup: over the cable, Wireless debugging is switched off at the start;
   through the app over Wi-Fi, USB debugging is switched off at the start.
3. While the USB cable is plugged in, debugging stays on; 5 minutes after unplugging it is switched
   off (countdown on the phone).
4. Cable never plugged in: off 5 minutes after *Allow backup* if no backup started.
5. During a Wi-Fi backup the computer says "still here" every 30 seconds; nothing for 2 minutes → off.
6. Right after the backup the computer switches it off.

**Wi-Fi without the app (Wireless debugging, Android 11 and newer).** Everything works as over the
cable, including the fingerprints on the phone – only slower.

1. Phone: *Settings → System → Developer options → Wireless debugging* → on.
2. Program: **Pair over Wi-Fi…** → on the phone *Pair device with QR code* and scan the code (or
   *Pair device with pairing code* and type the 6 digits). Needed only once.
3. From then on the phone is found whenever Wireless debugging is on and both are in the same Wi-Fi.

**No router? Direct Wi-Fi.** **Direct Wi-Fi…** lets the computer open its own Wi-Fi network (Linux:
5 GHz if possible; Windows: its *Mobile hotspot*). The phone joins it with a QR code. On Linux most
computers leave the normal Wi-Fi meanwhile; it comes back when Direct Wi-Fi is stopped. On Windows
the normal Wi-Fi stays.

**How the phone is recognised securely.** When the app is paired, it creates a key in the phone's
security chip; the computer stores its fingerprint. Model, serial number or names alone are never
trusted – every connection checks this key (encrypted connection with the remembered certificate)
before anything else is sent.

* **Cable:** the computer reaches the app through the cable and checks the key – the status then
  says *verified*. Pairing over the cable needs no code: you tap **Pair** on the phone.
* **Wi-Fi:** the app announces itself with a random name and a code that changes every 10 minutes
  and that only a paired computer can recognise. Others in the same network cannot see which phone
  it is.
* **Bluetooth** (only to find the phone): the same changing code plus the phone's Wi-Fi address,
  encrypted. The computer then connects over Wi-Fi. **No files are ever sent over Bluetooth.**
  The phone app needs the "Nearby devices" permission for this.

### Phone folders

**Camera** adds Android's camera folder (`DCIM/Camera`). **Choose folders…** lists the phone's
folders – for example screenshots (`Pictures/Screenshots`, on Samsung `DCIM/Screenshots`), WhatsApp
pictures, `Movies`, `Download` – or lets you type one.

**Keep the original folder structure** (option): files from folders other than the camera folder
keep their folders in the backup, for example *Karen / Pixel 10 Pro / Pictures / Screenshots*. The
camera folder is always sorted into year and month folders.

### Backup drives and backup plans

*Add drive…* lists the connected external drives – also drives that are plugged in but not opened
yet (Linux: they are opened with one click, no password). *Add folder…* lets you pick any folder. A
preview shows exactly where the files will go. A phone shows only the drives used before with it,
already ticked.

Each drive has a **backup plan**:

* **Simple** – one folder that grows; only new photos and videos are added.
* **Grandfather-Father-Son** – dated backups: a **full** backup every 3 months, a **differential**
  one every month, **incremental** ones in between. Full and differential backups also contain the
  earlier files they need, so photos deleted from the phone stay in every full backup.

Both can be mixed, for example *Simple* on one drive and *Grandfather-Father-Son* on the other.

### What is on the drive

* **PhoneBackups** – the folder on the drive
  * **Karen** – one folder per owner
    * **Pixel 10 Pro** – the backup of this phone
      * **Logs** – the reports (`.txt`, `.html`, `.csv`), e.g. *Backup Pixel 10 Pro Karen 2026-11-02*
      * **2026**
        * **26.01 … 26.12** – the photos and videos of each month
        * **raw / 26.01 …** – only if there are RAW / DNG photos
      * **.phonebackup** – what is already backed up (please do not delete)

* Month folder = year + month: `26.02` is February 2026.
* Folders are only created when a file goes into them – no empty folders.
* The month comes from the date the photo or video was taken; otherwise from the file name
  (`PXL_20261102_…`); otherwise from the file date.
* Motion photos, HEIC, PNG and so on count as photos; DNG and other RAW files go to `raw`.
* Same name, different content → the new file is saved as `name_1.jpg`. Identical files are stored
  only once.
* A second report on the same day gets the time added to its name.
* Backups made with older versions (month folders like `02.February-photos`, backup folders like
  `Pixel 10 Pro - Karen`, reports next to the photos) are converted before the next backup. Before
  month folders are renamed, the program lists them and you can keep the old names. Files are only
  moved, never deleted.

### Safety

* **Phone → computer:** with ADB and with the phone app, the phone calculates the fingerprint
  (SHA-256) of every file and the program compares it with the received data.
* **Computer → drive:** every copy is written to the disk, read back and its fingerprint compared.
* Files are written under a temporary name and renamed only after the check. An interrupted backup
  never leaves half files; the next backup simply continues.
* Free space is checked first. If a drive fails or fills up, the backup continues on the other
  drive and the report shows it in red.
* **Never the wrong phone:** every backup remembers its phone (model, serial number, the phone
  app's key). Before the backup the connected phone is checked: a different serial number or key →
  **refused, nothing is copied**. If only the model can be compared, you have to confirm. Right
  before the first file the phone is checked a second time.

### Manage backups

**Backups** lists all your backups. Pick one to see its tabs:

* **Overview** – the latest backup, which backup drives are complete, the Grandfather-Father-Son
  backups and backups that did not finish. After every backup the program asks whether it is
  complete.
* **Phone folders** – the folders that *Update backup* copies.
* **Backup drives** – the drives of this backup and their plans.
* **Import folders** – add old photos to this backup (see below).
* **Backup history** – every backup with its result and report.

**Old phones and old drives.** *New backup of an old phone or drive…* creates a backup of its own
(for example "Galaxy S7 – Kevin" or "Old drive – Kevin"); *Import folders* adds to an existing backup.
Add the folders (for example the copy of an old phone and of its SD card) and click *Choose folders
to import…*: every folder with files is listed with its photos, videos and other files; app data,
caches, thumbnails, trash and hidden folders are left out. For each folder choose:

* **Sort into year/month folders** – sorted by date exactly like a phone backup.
* **Keep folder as it is** – copied with its name to the top of the backup (for example
  *Holiday Italy 2019 / Day 1*). Sub-folders are separate lines – tick them too to keep the whole
  tree.

Every file is checked like a phone backup, identical files are stored only once, and the old folders
are only read.

**Secure backups (second copy).** Copies a backup to a second drive or to **Google Drive**. Each copy
gets its own dated folder.

| Type | Copies |
|---|---|
| full | everything |
| differential | everything new since the last **full** copy |
| incremental | everything new since the **last** copy (any type) |

**Automatic – Grandfather-Father-Son** (default) chooses the type: full every 3 months
(grandfather), differential every month (father), incremental in between (son). It keeps the newest
4 full, 3 differential and 6 incremental copies and everything they need for a restore. Older ones
are suggested for removal and deleted **only after you confirm** (*Clean up old exports…*). Every
copied file is compared with the fingerprint from the backup – a file that was damaged on the first
drive is reported as a warning.

**Google Drive.** *Add to cloud storage → Google Drive* signs in through the browser. The program
can only see the files it uploaded itself; the sign-in stays on this computer.

* **Copy** – a mirror of the backup in *My Drive / My Smartphone Media Backup*: only new files are
  uploaded, nothing is deleted or overwritten.
* **Grandfather-Father-Son** – every photo is stored only **once**; later copies link to it
  (shortcuts, no extra space). Please do not delete single photos there by hand – every copy that
  links to them would lose them.

Every upload is checked against Google's own fingerprint. Privacy policy:
<https://machetso.github.io/my-smartphone-media-backup/privacy.html>

**Restore.** Pick the copy (on a drive or on Google Drive), the date and the target folder. The
program rebuilds one complete folder from the fewest copies needed and checks every file.

### Program settings

* **Language** (also behind the globe top right) – changes after a restart.
* **ADB** – found automatically; *Download ADB…* fetches it from Google.
* **Force data onto the disk before verifying** – safer, slightly slower (on by default).
* **Keep the computer awake** during backup, import, copy and restore (on by default). The power
  settings themselves are not changed. Linux: standby, closing the lid and shutting down are blocked
  while a job runs, and the screen stays on. Windows: sleep is prevented and Windows asks before
  shutting down; the lid and the power button follow the Windows settings.
* **Check for a new version at start** – once a day. *Update now* downloads the new version, checks
  that it is signed by the project, replaces the program and restarts it. Settings, drives, phones
  and pairings stay. If the new version does not start, the old one is put back automatically.
* **Known phones** – the paired phones, the phone app version and automatic updates of the app.

The settings are stored in `~/.config/phonebackup/config.json` (Windows:
`%APPDATA%\PhoneBackup\config.json`).

**Start icon (Linux):** the script *install-linux-desktop.sh* in the program folder puts the program
into the app menu and on the desktop.

### Tested with

* Linux (Pop!_OS) with a Google Pixel 10 Pro (Android 17) over USB 3 with ADB: 1372 files / 20 GB
  to two external drives at the same time, about 24 MB/s.
* Samsung Galaxy S20 FE over USB (ADB) and over Wi-Fi with the phone app: 12.4 MB/s over Wi-Fi.
* Google Drive: Copy and Grandfather-Father-Son with a 20 GB backup, cleanup and restore.
* Not yet tested on real hardware: the file transfer fallback (MTP) and Windows in general.

## License

MIT – see [LICENSE](LICENSE). What is new: [CHANGELOG.md](CHANGELOG.md).
