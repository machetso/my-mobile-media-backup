# My Mobile Media Backup

**Version 0.9.9.0**

Sichert die Fotos und Videos deines Android-Telefons auf ein oder mehrere externe Laufwerke – Datei
für Datei geprüft, nach Jahr und Monat sortiert, mit einem Bericht nach jedem Backup. Für Windows und Linux.

## Die wichtigsten Funktionen

* **Ein Klick** – Telefon und Computer zeigen, wie viele Fotos und Videos noch nicht gesichert sind
  (und wie groß sie sind); ein Tippen auf dem Telefon oder ein Klick am Computer aktualisiert das Backup.
* **Nur neue Fotos und Videos werden kopiert** – das zweite Backup dauert Minuten, nicht Stunden.
* **Jede Datei wird geprüft.** Das Telefon berechnet einen Fingerabdruck (SHA-256) jeder Datei, das
  Programm vergleicht ihn mit dem, was angekommen ist, und noch einmal mit dem, was auf das Laufwerk
  geschrieben wurde.
* **Mehrere Laufwerke gleichzeitig** – das Telefon wird nur einmal gelesen.
* **Automatisch sortiert** in Jahres- und Monatsordner (`2026/26.11`), RAW-Fotos getrennt.
* **Nie wird etwas gelöscht** – nicht auf dem Telefon und nicht im Backup.
* **Immer die schnellste Verbindung** – USB-Kabel, Wi-Fi oder das eigene Wi-Fi des Computers; das
  Programm wählt von selbst.
* **Nie das falsche Telefon** – jedes Backup kennt sein Telefon; ein anderes Telefon wird abgelehnt.
* **Automatische Backups** – wenn ein bekanntes Telefon nach Hause kommt, kann das Programm es von
  selbst sichern.
* **Zweite Kopie** auf einem anderen Laufwerk oder auf Google Drive, mit Aufbewahrung älterer Stände
  (Großvater-Vater-Sohn), und **Wiederherstellen** mit einem Klick.
* **Alte Telefone und alte Laufwerke** können zu einem Backup hinzugefügt werden oder ein eigenes
  Backup bekommen.
* Ein Bericht (Text, Webseite und Tabelle) nach jedem Backup.
* Auf Deutsch, Englisch, Französisch, Spanisch, Rumänisch, Hebräisch und Klingonisch.

## So funktioniert es – kurz gesagt

Das Programm kopiert die Fotos und Videos von deinem Telefon auf ein externes Laufwerk (zum Beispiel
eine USB-Festplatte). Jedes Telefon bekommt einen eigenen Ordner auf dem Laufwerk: *Besitzer / Telefon*,
zum Beispiel *Karen / Pixel 10 Pro*. Darin werden die Fotos und Videos in einen Ordner pro Monat sortiert.

Das Programm merkt sich, was schon auf dem Laufwerk ist. Jedes spätere Backup fügt nur Neues hinzu –
deshalb kannst du einfach einmal pro Woche auf **Backup aktualisieren** klicken.

### Dein erstes Backup

1. **Lade** das Programm von der [Releases-Seite](https://github.com/machetso/my-mobile-media-backup/releases)
   **herunter** und starte es – es muss nichts installiert werden. Windows: die `.exe`-Datei. Linux:
   die `.tar.gz`-Datei.
2. **Schließe das externe Laufwerk an.**
3. **Stecke das Telefon mit seinem USB-Kabel an** und entsperre es. Wenn das Telefon fragt, wofür
   die USB-Verbindung ist, wähle **Dateiübertragung**. Der farbige Balken oben zeigt, ob das
   Telefon verbunden ist.
4. Klicke auf **Neues Backup…**, gib deinen Namen als **Besitzer** ein (der Name des Telefons wird
   von selbst ausgefüllt), prüfe die **Telefonordner** (der Kamera-Ordner ist schon dabei) und hake
   das **Backup-Laufwerk** an.
5. Klicke auf **Backup starten**. Der Balken unten zeigt, wie weit es ist und wie lange es dauert.
6. Wenn es fertig ist, zeigt **Bericht öffnen**, was kopiert wurde, und **Backup-Ordner öffnen**
   öffnet die Fotos auf dem Laufwerk.

### Jedes weitere Backup

Schließe das Laufwerk an. Auf dem Startbildschirm hat dein Telefon eine eigene Schaltfläche
**Backup aktualisieren** – klicke darauf. Nur neue Fotos und Videos werden kopiert. Mit der
Telefon-App (siehe *Tipps*) muss das Telefon nicht einmal angesteckt sein: Wenn es im selben Wi-Fi
ist, steht in seiner Zeile zum Beispiel *In der Nähe – 23 Fotos und 4 Videos (1,5 GB) noch nicht
gesichert*, und ein Klick genügt. Oder tippe auf dem Telefon auf **Jetzt sichern**.

### Tipps

* **Schneller:** Schalte auf dem Telefon einmal *USB-Debugging* ein (das Programm zeigt dir Schritt
  für Schritt, wie das bei deinem Telefonmodell geht). Das Backup ist dann zwei- bis viermal schneller.
* **Ohne Kabel:** Installiere die Telefon-App *My Mobile Media Backup* (*Telefon verbinden…* auf dem
  Startbildschirm zeigt einen QR-Code). Dann funktioniert das Backup über Wi-Fi, und Telefon und
  Computer finden sich von selbst.
* **Zwei Laufwerke** sind sicherer als eines: Hake beide an, sie werden gleichzeitig beschrieben.

## Ausführliche Anleitung

### Das Fenster

* **Startbildschirm:** der Verbindungsstatus (rot = kein Telefon verbunden, gelb = am Telefon ist
  etwas zu tun, grün = verbunden), **Telefon verbinden…** und **Mögliche Verbindungen**. Ein bekanntes
  Telefon im selben Wi-Fi wird als *In der Nähe* angezeigt, mit **Jetzt sichern**. **Neues Backup…**
  startet ein Backup eines anderen Telefons oder mit anderen Ordnern oder Laufwerken. Darunter
  **Deine Telefone** – ein Eintrag pro Backup mit dem Datum des letzten Backups, wie viele Fotos und
  Videos noch nicht gesichert sind (wenn das Telefon in der Nähe oder verbunden ist), und einer eigenen
  Schaltfläche **Backup aktualisieren**. Die Schaltfläche ist grau, solange ein Klick das Backup nicht
  starten kann; ein Klick sagt dann, was fehlt.
* **Seitenleiste:** Backup, Backups verwalten, das Zahnrad (Programmeinstellungen), Anleitung und
  Über. Die Weltkugel oben rechts ändert die Sprache.
* **Unten:** Fortschritt, Geschwindigkeit und Restzeit, mit **Abbrechen** (stoppt nach der aktuellen
  Datei), **Bericht öffnen** und **Backup-Ordner öffnen**. Jeder Auftrag schreibt außerdem eine
  Protokolldatei.

### Das Telefon verbinden

Das Programm nutzt immer die **schnellste Verbindung, die es findet**. Taucht das Telefon während
eines Wi-Fi-Backups am USB-Kabel auf, läuft das Backup über das Kabel weiter. **Mögliche Verbindungen**
zeigt jeden Weg zum Telefon mit seiner Geschwindigkeit; **Schnellste Verbindung finden** prüft das
Kabel, das Wi-Fi und Bluetooth.

| Verbindung | Geschwindigkeit |
|---|---|
| USB-Kabel + USB-Debugging (von der Telefon-App oder von Hand eingeschaltet) | 45–50 MB/s (USB 3), etwa 20–30 MB/s (USB 2) |
| USB-Kabel, normale Dateiübertragung (MTP) | 10–20 MB/s |
| Wi-Fi: Telefon-App oder Kabelloses Debugging | 10–40 MB/s, je nach Wi-Fi |
| Wi-Fi direkt zu diesem Computer (ohne Router) | 10–30 MB/s |

**USB-Debugging (ADB).** ADB (Android Debug Bridge) ist Googles eigenes USB-Werkzeug für Android. Es
ist der schnellste und sicherste Weg: Das Telefon selbst berechnet den Fingerabdruck jeder Datei.
Android verlangt, dass du es einmal von Hand einschaltest – vorher kann kein Programm das tun:

1. Am Telefon: *Einstellungen → Über das Telefon* → 7-mal auf *Buildnummer* tippen (Entwickleroptionen an).
2. *Einstellungen → System → Entwickleroptionen* → **USB-Debugging** einschalten.
3. Stecke das Telefon an, entsperre es und bestätige *USB-Debugging zulassen* mit **Immer von diesem
   Computer zulassen**.

*USB-Debugging einschalten (erstes Mal)…* ist eine Schritt-für-Schritt-Anleitung. Sie erkennt das
Telefon am Kabel und hat die Schritte für Pixel, Samsung, Xiaomi / Redmi / POCO, OnePlus / OPPO / realme,
Motorola, Huawei / Honor, Sony und Nothing; für andere Telefone gibt es *Im Web nach diesem Telefon suchen*.

Das ADB-Programm selbst stammt von Google und darf nicht mit diesem Programm mitgeliefert werden.
*Programmeinstellungen → ADB herunterladen…* holt es direkt von Google in den eigenen Ordner des
Programms – ein Klick, keine Installation, keine Administratorrechte. Unter Linux funktioniert auch
das `adb`-Paket des Systems.

Wenn ADB nicht funktioniert, sagt das Programm das deutlich und nutzt stattdessen die normale
**Dateiübertragung** (MTP) des Telefons. Unter Linux wird das Telefon automatisch geöffnet; wähle in
der USB-Benachrichtigung des Telefons *Dateiübertragung*. MTP ist langsamer, und das Telefon kann
keine Fingerabdrücke berechnen – der Bericht sagt das.

**Die Telefon-App *My Mobile Media Backup*.** Mit der App funktionieren Backups über Wi-Fi ohne
USB-Debugging, die App schaltet die schnellste Verbindung für dich ein und aus, und Telefon und
Computer zeigen, was noch nicht gesichert ist.

* **Installieren:** *Telefon verbinden…* zeigt zwei QR-Codes: Einer verbindet die App, der andere lädt
  sie von der Releases-Seite herunter. Über das USB-Kabel kann das Programm die App selbst
  installieren; es **fragt immer vorher** und sagt, auf welchem Telefon, welche Version und warum.
* **Backup:** zeigt, wie viele Fotos und Videos noch nicht gesichert sind und wie groß sie sind, zum
  Beispiel *23 Fotos und 4 Videos (1,5 GB) noch nicht gesichert*. **Jetzt sichern** startet das
  Backup: Das Telefon verbindet sich, der Computer aktualisiert das Backup von selbst. Wenn etwas
  fehlt (das Computerprogramm läuft nicht, das Backup-Laufwerk ist nicht angeschlossen, …), ist die
  Schaltfläche grau, und ein Tippen sagt, was zu tun ist.
* **Backup zulassen:** ein Schalter. An = die schnellste Verbindung – USB-Debugging und Kabelloses
  Debugging, wo die App sie schalten darf, und der eigene Nur-Lese-Zugriff der App über das Wi-Fi.
  Daneben: *Verbindung hergestellt* oder *Nicht verbunden*; darunter, wie lange er an bleibt.
  **Trennen** schaltet alles aus. Nach jedem Backup schaltet der Computer das Debugging wieder aus
  (*… nach dem Backup auf dem Telefon ausschalten*, standardmäßig an). Die Entwickleroptionen bleiben an.
* **Wenn dein Computer ein Backup möchte:**
  * **Mich fragen** (Standard) – das Telefon fragt *Backup zulassen?*; nichts startet ohne dein Tippen.
  * **Ohne Nachfrage zulassen** – ein Klick am Computer startet das Backup, ohne Tippen am Telefon.
    Mit **Auch von selbst starten** werden die neuesten Fotos und Videos gesichert, wenn der Computer
    das Telefon im Wi-Fi findet oder du das Kabel ansteckst (höchstens einmal pro Stunde).
  * **Nie** – der Computer kann nicht fragen und findet das Telefon nicht in der Nähe.
* **VPN auf dem Telefon:** Ein VPN, das alles durch den Tunnel schickt, hindert den Computer daran,
  die App über das Wi-Fi zu erreichen. Die App zeigt einen Hinweis: Nimm *My Mobile Media Backup* vom
  VPN aus oder nutze das Kabel.
* **Gleiche Version:** Die Telefon-App hat dieselbe Versionsnummer wie das Programm. Ist sie älter,
  zeigen der Startbildschirm und *Backups verwalten → Übersicht* **Telefon-App aktualisieren**. Ältere
  Kopien der App werden automatisch entfernt.
* Die App kann nur Fotos und Videos lesen. Der Computer fragt nach jeder Datei; das Telefon antwortet
  nur dem gekoppelten Computer und sendet nie etwas von selbst.

**Wann das Debugging wieder ausgeschaltet wird** (die Telefon-App tut das auch, wenn der Computer weg ist):

1. Wi-Fi-Backups laufen normalerweise über die Telefon-App mit ausgeschaltetem Debugging; Kabelloses
   Debugging wird nur für Telefone ohne die App verwendet.
2. Eine Verbindung pro Backup: Über das Kabel wird Kabelloses Debugging zu Beginn ausgeschaltet; über
   die App im Wi-Fi wird USB-Debugging zu Beginn ausgeschaltet.
3. Solange das USB-Kabel angesteckt ist, bleibt das Debugging an; 5 Minuten nach dem Abziehen wird es
   ausgeschaltet (Countdown auf dem Telefon).
4. Kabel nie angesteckt: aus 5 Minuten nach *Backup zulassen*, wenn kein Backup gestartet wurde.
5. Während eines Wi-Fi-Backups meldet der Computer alle 30 Sekunden „noch da“; 2 Minuten nichts → aus.
6. Direkt nach dem Backup schaltet der Computer es aus.

**Wi-Fi ohne die App (Kabelloses Debugging, Android 11 und neuer).** Alles funktioniert wie über das
Kabel, einschließlich der Fingerabdrücke auf dem Telefon – nur langsamer.

1. Telefon: *Einstellungen → System → Entwickleroptionen → Kabelloses Debugging* → an.
2. Programm: **Über Wi-Fi koppeln…** → auf dem Telefon *Gerät mit QR-Code koppeln* und den Code scannen
   (oder *Gerät mit Kopplungscode koppeln* und die 6 Ziffern eintippen). Nur einmal nötig.
3. Ab dann wird das Telefon gefunden, sobald Kabelloses Debugging an ist und beide im selben Wi-Fi sind.

**Kein Router? Direktes Wi-Fi.** **Direktes Wi-Fi…** lässt den Computer ein eigenes Wi-Fi-Netzwerk
öffnen (Linux: wenn möglich mit 5 GHz; Windows: sein *Mobiler Hotspot*). Das Telefon verbindet sich
per QR-Code damit. Unter Linux verlassen die meisten Computer währenddessen ihr normales Wi-Fi; es
kommt zurück, wenn Direktes Wi-Fi beendet wird. Unter Windows bleibt das normale Wi-Fi.

**Wie das Telefon sicher erkannt wird.** Wenn die App gekoppelt wird, erzeugt sie einen Schlüssel im
Sicherheitschip des Telefons; der Computer speichert dessen Fingerabdruck. Modell, Seriennummer oder
Namen allein wird nie vertraut – jede Verbindung prüft diesen Schlüssel (verschlüsselte Verbindung mit
dem gemerkten Zertifikat), bevor irgendetwas anderes gesendet wird.

* **Kabel:** Der Computer erreicht die App über das Kabel und prüft den Schlüssel – im Status steht
  dann *geprüft*. Das Koppeln über das Kabel braucht keinen Code: Du tippst auf dem Telefon auf **Koppeln**.
* **Wi-Fi:** Die App meldet sich mit einem zufälligen Namen und einem Code, der sich alle 10 Minuten
  ändert und den nur ein gekoppelter Computer erkennen kann. Andere im selben Netzwerk können nicht
  sehen, welches Telefon es ist.
* **Bluetooth** (nur zum Finden des Telefons): derselbe wechselnde Code plus die Wi-Fi-Adresse des
  Telefons, verschlüsselt. Der Computer verbindet sich dann über Wi-Fi. **Über Bluetooth werden nie
  Dateien gesendet.** Die Telefon-App braucht dafür die Berechtigung „Geräte in der Nähe“.

### Telefonordner

**Kamera** fügt den Kamera-Ordner von Android hinzu (`DCIM/Camera`). **Ordner wählen…** listet die
Ordner des Telefons auf – zum Beispiel Screenshots (`Pictures/Screenshots`, bei Samsung `DCIM/Screenshots`),
WhatsApp-Bilder, `Movies`, `Download` – oder lässt dich einen eintippen.

**Ursprüngliche Ordnerstruktur beibehalten** (Option): Dateien aus anderen Ordnern als dem Kamera-Ordner
behalten im Backup ihre Ordner, zum Beispiel *Karen / Pixel 10 Pro / Pictures / Screenshots*. Der
Kamera-Ordner wird immer in Jahres- und Monatsordner sortiert.

### Backup-Laufwerke und Backup-Pläne

*Laufwerk hinzufügen…* listet die angeschlossenen externen Laufwerke auf – auch Laufwerke, die
angesteckt, aber noch nicht geöffnet sind (Linux: Sie werden mit einem Klick geöffnet, ohne Passwort).
*Ordner hinzufügen…* lässt dich einen beliebigen Ordner wählen. Eine Vorschau zeigt genau, wohin die
Dateien kommen. Bei einem Telefon werden nur die Laufwerke angezeigt, die schon vorher mit ihm genutzt
wurden, bereits angehakt.

Jedes Laufwerk hat einen **Backup-Plan**:

* **Einfach** – ein Ordner, der wächst; nur neue Fotos und Videos werden hinzugefügt.
* **Großvater-Vater-Sohn** – datierte Backups: alle 3 Monate ein **volles** Backup, jeden Monat ein
  **differenzielles**, dazwischen **inkrementelle**. Volle und differenzielle Backups enthalten auch die
  früheren Dateien, die sie brauchen, sodass Fotos, die auf dem Telefon gelöscht wurden, in jedem
  vollen Backup bleiben.

Beides lässt sich mischen, zum Beispiel *Einfach* auf einem Laufwerk und *Großvater-Vater-Sohn* auf
dem anderen.

### Was auf dem Laufwerk liegt

* **PhoneBackups** – der Ordner auf dem Laufwerk
  * **Karen** – ein Ordner pro Besitzer
    * **Pixel 10 Pro** – das Backup dieses Telefons
      * **Logs** – die Berichte (`.txt`, `.html`, `.csv`), z. B. *Backup Pixel 10 Pro Karen 2026-11-02*
      * **2026**
        * **26.01 … 26.12** – die Fotos und Videos jedes Monats
        * **raw / 26.01 …** – nur wenn es RAW- / DNG-Fotos gibt
      * **.phonebackup** – was schon gesichert ist (bitte nicht löschen)

* Monatsordner = Jahr + Monat: `26.02` ist Februar 2026.
* Ordner werden erst angelegt, wenn eine Datei hineinkommt – keine leeren Ordner.
* Der Monat kommt aus dem Aufnahmedatum des Fotos oder Videos; sonst aus dem Dateinamen
  (`PXL_20261102_…`); sonst aus dem Dateidatum.
* Bewegte Fotos, HEIC, PNG und so weiter zählen als Fotos; DNG und andere RAW-Dateien kommen nach `raw`.
* Gleicher Name, anderer Inhalt → die neue Datei wird als `name_1.jpg` gespeichert. Identische Dateien
  werden nur einmal gespeichert.
* Ein zweiter Bericht am selben Tag bekommt die Uhrzeit an den Namen angehängt.
* Backups aus älteren Versionen (Monatsordner wie `02.February-photos`, Backup-Ordner wie
  `Pixel 10 Pro - Karen`, Berichte neben den Fotos) werden vor dem nächsten Backup umgestellt. Bevor
  Monatsordner umbenannt werden, listet das Programm sie auf, und du kannst die alten Namen behalten.
  Dateien werden nur verschoben, nie gelöscht.

### Sicherheit

* **Telefon → Computer:** Mit ADB und mit der Telefon-App berechnet das Telefon den Fingerabdruck
  (SHA-256) jeder Datei, und das Programm vergleicht ihn mit den empfangenen Daten.
* **Computer → Laufwerk:** Jede Kopie wird auf den Datenträger geschrieben, zurückgelesen und ihr
  Fingerabdruck verglichen.
* Dateien werden unter einem vorläufigen Namen geschrieben und erst nach der Prüfung umbenannt. Ein
  unterbrochenes Backup hinterlässt nie halbe Dateien; das nächste Backup macht einfach weiter.
* Der freie Speicherplatz wird vorher geprüft. Fällt ein Laufwerk aus oder wird es voll, läuft das
  Backup auf dem anderen Laufwerk weiter, und der Bericht zeigt es rot.
* **Nie das falsche Telefon:** Jedes Backup merkt sich sein Telefon (Modell, Seriennummer, den
  Schlüssel der Telefon-App). Vor dem Backup wird das verbundene Telefon geprüft: andere Seriennummer
  oder anderer Schlüssel → **abgelehnt, nichts wird kopiert**. Kann nur das Modell verglichen werden,
  musst du bestätigen. Direkt vor der ersten Datei wird das Telefon ein zweites Mal geprüft.

### Backups verwalten

**Backups** listet alle deine Backups auf. Wähle eines, um seine Tabs zu sehen:

* **Übersicht** – das neueste Backup, welche Backup-Laufwerke vollständig sind, die
  Großvater-Vater-Sohn-Backups und Backups, die nicht fertig wurden. Nach jedem Backup fragt das
  Programm, ob es vollständig ist.
* **Telefonordner** – die Ordner, die *Backup aktualisieren* kopiert.
* **Backup-Laufwerke** – die Laufwerke dieses Backups und ihre Pläne.
* **Ordner importieren** – alte Fotos zu diesem Backup hinzufügen (siehe unten).
* **Backup-Verlauf** – jedes Backup mit seinem Ergebnis und Bericht.

**Alte Telefone und alte Laufwerke.** *Neues Backup eines alten Telefons oder Laufwerks…* erstellt ein
eigenes Backup (zum Beispiel „Galaxy S7 – Kevin“ oder „Altes Laufwerk – Kevin“); *Ordner importieren*
fügt etwas zu einem vorhandenen Backup hinzu. Füge die Ordner hinzu (zum Beispiel die Kopie eines alten
Telefons und seiner SD-Karte) und klicke auf *Zu importierende Ordner wählen…*: Jeder Ordner mit
Dateien wird mit seinen Fotos, Videos und anderen Dateien aufgelistet; App-Daten, Caches,
Vorschaubilder, Papierkorb und versteckte Ordner werden ausgelassen. Wähle für jeden Ordner:

* **In Jahres-/Monatsordner sortieren** – nach Datum sortiert, genau wie bei einem Telefon-Backup.
* **Ordner so lassen, wie er ist** – mit seinem Namen oben ins Backup kopiert (zum Beispiel
  *Urlaub Italien 2019 / Tag 1*). Unterordner sind eigene Zeilen – hake sie auch an, um den ganzen
  Ordnerbaum zu behalten.

Jede Datei wird wie bei einem Telefon-Backup geprüft, identische Dateien werden nur einmal gespeichert,
und die alten Ordner werden nur gelesen.

**Backups sichern (zweite Kopie).** Kopiert ein Backup auf ein zweites Laufwerk oder auf **Google Drive**.
Jede Kopie bekommt ihren eigenen datierten Ordner.

| Art | Kopiert |
|---|---|
| voll | alles |
| differenziell | alles Neue seit der letzten **vollen** Kopie |
| inkrementell | alles Neue seit der **letzten** Kopie (jeder Art) |

**Automatisch – Großvater-Vater-Sohn** (Standard) wählt die Art: voll alle 3 Monate (Großvater),
differenziell jeden Monat (Vater), dazwischen inkrementell (Sohn). Es behält die neuesten 4 vollen,
3 differenziellen und 6 inkrementellen Kopien und alles, was sie für eine Wiederherstellung brauchen.
Ältere werden zum Entfernen vorgeschlagen und **erst nach deiner Bestätigung** gelöscht (*Alte Exporte
aufräumen…*). Jede kopierte Datei wird mit dem Fingerabdruck aus dem Backup verglichen – eine Datei,
die auf dem ersten Laufwerk beschädigt wurde, wird als Warnung gemeldet.

**Google Drive.** *Zum Cloud-Speicher hinzufügen → Google Drive* meldet dich über den Browser an. Das
Programm sieht nur die Dateien, die es selbst hochgeladen hat; die Anmeldung bleibt auf diesem Computer.

* **Kopie** – ein Spiegel des Backups in *My Drive / My Smartphone Media Backup*: Nur neue Dateien
  werden hochgeladen, nichts wird gelöscht oder überschrieben.
* **Großvater-Vater-Sohn** – jedes Foto wird nur **einmal** gespeichert; spätere Kopien verknüpfen
  darauf (Verknüpfungen, kein zusätzlicher Speicherplatz). Bitte lösche dort keine einzelnen Fotos von
  Hand – jede Kopie, die darauf verknüpft, würde sie verlieren.

Jeder Upload wird mit Googles eigenem Fingerabdruck geprüft. Datenschutzerklärung:
<https://machetso.github.io/my-smartphone-media-backup/privacy.html>

**Wiederherstellen.** Wähle die Kopie (auf einem Laufwerk oder auf Google Drive), das Datum und den
Zielordner. Das Programm baut aus möglichst wenigen Kopien einen vollständigen Ordner wieder auf und
prüft jede Datei.

### Programmeinstellungen

* **Sprache** (auch hinter der Weltkugel oben rechts) – ändert sich nach einem Neustart.
* **ADB** – wird automatisch gefunden; *ADB herunterladen…* holt es von Google.
* **Daten vor der Prüfung auf den Datenträger erzwingen** – sicherer, etwas langsamer (standardmäßig an).
* **Computer wach halten** während Backup, Import, Kopie und Wiederherstellung (standardmäßig an). Die
  Energieeinstellungen selbst werden nicht geändert. Linux: Standby, Zuklappen des Deckels und
  Herunterfahren sind blockiert, solange ein Auftrag läuft, und der Bildschirm bleibt an. Windows: Der
  Ruhezustand wird verhindert, und Windows fragt vor dem Herunterfahren; Deckel und Ein-/Aus-Taste
  folgen den Windows-Einstellungen.
* **Beim Start nach einer neuen Version suchen** – einmal am Tag. *Jetzt aktualisieren* lädt die neue
  Version herunter, prüft, dass sie vom Projekt signiert ist, ersetzt das Programm und startet es neu.
  Einstellungen, Laufwerke, Telefone und Kopplungen bleiben erhalten. Startet die neue Version nicht,
  wird die alte automatisch wiederhergestellt.
* **Bekannte Telefone** – die gekoppelten Telefone, die Version der Telefon-App und automatische
  Updates der App.

Die Einstellungen werden in `~/.config/phonebackup/config.json` gespeichert (Windows:
`%APPDATA%\PhoneBackup\config.json`).

**Startsymbol (Linux):** Das Skript *install-linux-desktop.sh* im Programmordner trägt das Programm
ins App-Menü und auf den Desktop ein.

### Getestet mit

* Linux (Pop!_OS) mit einem Google Pixel 10 Pro (Android 17) über USB 3 mit ADB: 1372 Dateien / 20 GB
  auf zwei externe Laufwerke gleichzeitig, etwa 24 MB/s.
* Samsung Galaxy S20 FE über USB (ADB) und über Wi-Fi mit der Telefon-App: 12,4 MB/s über Wi-Fi.
* Google Drive: Kopie und Großvater-Vater-Sohn mit einem 20-GB-Backup, Aufräumen und Wiederherstellen.
* Noch nicht auf echter Hardware getestet: der Ersatz über Dateiübertragung (MTP) und Windows allgemein.

## Lizenz

MIT – siehe [LICENSE](LICENSE). Was neu ist: [CHANGELOG.md](CHANGELOG.md).
