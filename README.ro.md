# My Mobile Media Backup

**Version 0.9.9.0**

Face backup fotografiilor și videoclipurilor de pe telefonul tău Android pe una sau mai multe unități
externe – verificate fișier cu fișier, sortate pe ani și luni, cu un raport după fiecare backup.
Pentru Windows și Linux.

## Funcții principale

* **Un singur clic** – telefonul și computerul arată câte fotografii și videoclipuri sunt încă fără
  backup (și cât de mari sunt); o atingere pe telefon sau un clic pe computer actualizează backup-ul.
* **Se copiază doar fotografiile și videoclipurile noi** – al doilea backup durează minute, nu ore.
* **Fiecare fișier este verificat.** Telefonul calculează o amprentă (SHA-256) a fiecărui fișier,
  iar programul o compară cu ce a sosit și încă o dată cu ce a fost scris pe unitate.
* **Mai multe unități în același timp** – telefonul este citit o singură dată.
* **Sortate automat** în foldere pe ani și luni (`2026/26.11`), fotografiile RAW separat.
* **Nu se șterge niciodată nimic** – nici pe telefon, nici în backup.
* **Întotdeauna cea mai rapidă conexiune** – cablu USB, Wi-Fi sau Wi-Fi-ul propriu al computerului;
  programul alege singur.
* **Niciodată telefonul greșit** – fiecare backup își cunoaște telefonul; un alt telefon este refuzat.
* **Backup-uri automate** – când un telefon cunoscut ajunge acasă, programul îi poate face backup singur.
* **A doua copie** pe altă unitate sau pe Google Drive, cu stările mai vechi păstrate
  (Bunic-Tată-Fiu), și **restaurare** cu un singur clic.
* **Telefoanele vechi și unitățile vechi** pot fi adăugate la un backup sau pot primi un backup propriu.
* Un raport (text, pagină web și tabel) după fiecare backup.
* În germană, engleză, franceză, spaniolă, română, ebraică și klingoniană.

## Cum funcționează – pe scurt

Programul copiază fotografiile și videoclipurile de pe telefon pe o unitate externă (de exemplu un
hard disk USB). Fiecare telefon primește propriul folder pe unitate: *Proprietar / Telefon*, de exemplu
*Karen / Pixel 10 Pro*. Înăuntru, fotografiile și videoclipurile sunt sortate într-un folder pentru fiecare lună.

Programul ține minte ce se află deja pe unitate. Fiecare backup ulterior adaugă doar ce este nou –
de aceea poți apăsa pur și simplu **Actualizează backup-ul** o dată pe săptămână.

### Primul tău backup

1. **Descarcă** programul de pe [pagina Releases](https://github.com/machetso/my-mobile-media-backup/releases)
   și pornește-l – nu trebuie instalat nimic. Windows: fișierul `.exe`. Linux: fișierul `.tar.gz`.
2. **Conectează unitatea externă.**
3. **Conectează telefonul cu cablul său USB** și deblochează-l. Dacă telefonul întreabă pentru ce este
   conexiunea USB, alege **Transfer de fișiere**. Bara colorată de sus arată dacă telefonul
   este conectat.
4. Apasă **Backup nou…**, introdu numele tău ca **proprietar** (numele telefonului se completează
   singur), verifică **folderele telefonului** (folderul camerei este deja acolo) și bifează
   **unitatea de backup**.
5. Apasă **Pornește backup-ul**. Bara de jos arată cât a progresat și cât durează.
6. Când s-a terminat, **Deschide raportul** arată ce s-a copiat, iar **Deschide folderul de backup**
   deschide fotografiile de pe unitate.

### Fiecare backup următor

Conectează unitatea. Pe ecranul de start, telefonul tău are propriul buton **Actualizează backup-ul** –
apasă-l. Se copiază doar fotografiile și videoclipurile noi. Cu aplicația de pe telefon (vezi *Sfaturi*)
telefonul nici nu trebuie conectat: când este în același Wi-Fi, rândul lui spune de exemplu
*În apropiere – 23 de fotografii și 4 videoclipuri (1,5 GB) încă fără backup*, și un clic este de ajuns.
Sau atinge **Fă backup acum** pe telefon.

### Sfaturi

* **Mai rapid:** activează o dată *Depanare USB* pe telefon (programul îți arată cum, pas cu pas,
  pentru modelul tău de telefon). Backup-ul este apoi de două până la patru ori mai rapid.
* **Fără cablu:** instalează aplicația de pe telefon *My Mobile Media Backup* (*Conectează telefonul…*
  pe ecranul de start arată un cod QR). Atunci backup-ul funcționează prin Wi-Fi, iar telefonul și
  computerul se găsesc singure.
* **Două unități** sunt mai sigure decât una: bifează-le pe amândouă, sunt scrise în același timp.

## Manual detaliat

### Fereastra

* **Ecranul de start:** starea conexiunii (roșu = niciun telefon conectat, galben = ai ceva de făcut
  pe telefon, verde = conectat), **Conectează telefonul…** și **Conexiuni posibile**. Un telefon
  cunoscut din același Wi-Fi apare ca *în apropiere*, cu **Fă backup acum**. **Backup nou…** pornește
  un backup pentru alt telefon sau cu alte foldere ori unități. Dedesubt, **Telefoanele tale** – câte o
  intrare pentru fiecare backup, cu data ultimului backup, câte fotografii și videoclipuri sunt încă fără
  backup (când telefonul este în apropiere sau conectat) și propriul buton **Actualizează backup-ul**.
  Butonul este gri cât timp un clic nu poate porni backup-ul; un clic spune atunci ce lipsește.
* **Bara laterală:** Backup, Gestionează backup-urile, rotița (setările programului), Manual și Despre.
  Globul din dreapta sus schimbă limba.
* **Jos:** progresul, viteza și timpul rămas, cu **Anulează** (se oprește după fișierul curent),
  **Deschide raportul** și **Deschide folderul de backup**. Fiecare sarcină scrie și un fișier jurnal.

### Conectarea telefonului

Programul folosește întotdeauna **cea mai rapidă conexiune pe care o găsește**. Dacă telefonul apare pe
cablul USB în timpul unui backup prin Wi-Fi, backup-ul continuă prin cablu. **Conexiuni posibile** arată
toate căile de a ajunge la telefon, cu viteza lor; **Găsește cea mai rapidă conexiune** verifică cablul,
Wi-Fi-ul și Bluetooth-ul.

| Conexiune | Viteză |
|---|---|
| Cablu USB + depanare USB (pornită de aplicația de pe telefon sau manual) | 45–50 MB/s (USB 3), aprox. 20–30 MB/s (USB 2) |
| Cablu USB, transfer de fișiere normal (MTP) | 10–20 MB/s |
| Wi-Fi: aplicația de pe telefon sau Depanare wireless | 10–40 MB/s, depinde de Wi-Fi |
| Wi-Fi direct către acest computer (fără router) | 10–30 MB/s |

**Depanarea USB (ADB).** ADB (Android Debug Bridge) este instrumentul USB al Google pentru Android. Este
calea cea mai rapidă și mai sigură: telefonul însuși calculează amprenta fiecărui fișier. Android cere
ca ea să fie activată o dată manual – niciun program nu poate face asta înainte:

1. Pe telefon: *Setări → Despre telefon* → atinge de 7 ori *Număr versiune* (opțiunile pentru dezvoltatori pornite).
2. *Setări → Sistem → Opțiuni pentru dezvoltatori* → activează **Depanare USB**.
3. Conectează telefonul, deblochează-l și confirmă *Permiteți depanarea USB* cu **Permiteți întotdeauna
   de pe acest computer**.

*Activează depanarea USB (prima dată)…* este un ghid pas cu pas. Recunoaște telefonul de pe
cablu și conține pașii pentru Pixel, Samsung, Xiaomi / Redmi / POCO, OnePlus / OPPO / realme,
Motorola, Huawei / Honor, Sony și Nothing; pentru alte telefoane *Caută pe web pentru acest telefon*.

Programul ADB în sine vine de la Google și nu poate fi livrat împreună cu acest program.
*Setările programului → Descarcă ADB…* îl aduce direct de la Google în folderul propriu al programului –
un clic, fără instalare, fără drepturi de administrator. Pe Linux funcționează și pachetul `adb` al sistemului.

Dacă ADB nu funcționează, programul spune clar acest lucru și folosește în schimb **transferul de fișiere**
normal al telefonului (MTP). Pe Linux telefonul este deschis automat; alege *Transfer de fișiere* în
notificarea USB a telefonului. MTP este mai lent, iar telefonul nu poate calcula amprente – raportul spune asta.

**Aplicația de pe telefon *My Mobile Media Backup*.** Cu aplicația, backup-urile funcționează prin Wi-Fi fără
depanare USB, aplicația pornește și oprește pentru tine cea mai rapidă conexiune, iar telefonul și computerul
arată ce este încă fără backup.

* **Instalare:** *Conectează telefonul…* arată două coduri QR: unul conectează aplicația, celălalt o
  descarcă de pe pagina Releases. Prin cablul USB programul poate instala singur aplicația; **întreabă
  întotdeauna înainte** și spune ce telefon, ce versiune și de ce.
* **Backup:** arată câte fotografii și videoclipuri sunt încă fără backup și cât de mari sunt, de
  exemplu *23 de fotografii și 4 videoclipuri (1,5 GB) încă fără backup*. **Fă backup acum** pornește
  backup-ul: telefonul se conectează, iar computerul actualizează singur backup-ul. Când lipsește ceva
  (programul de pe computer nu rulează, unitatea de backup nu este conectată, …) butonul este gri, iar o
  atingere spune ce ai de făcut.
* **Permite backup-ul:** un singur comutator. Pornit = cea mai rapidă conexiune – depanarea USB și Depanarea
  wireless, acolo unde aplicația are voie să le comute, și accesul propriu al aplicației, doar pentru citire,
  prin Wi-Fi. Lângă el: *Conexiune stabilită* sau *Neconectat*; dedesubt, cât timp rămâne pornit.
  **Deconectează** oprește totul. După fiecare backup computerul oprește din nou depanarea
  (*Oprește … după backup*, activat implicit). Opțiunile pentru dezvoltatori rămân pornite.
* **Când computerul tău vrea un backup:**
  * **Întreabă-mă** (implicit) – telefonul întreabă *Permiți backup-ul?*; nimic nu pornește fără atingerea ta.
  * **Permite fără întrebare** – un clic pe computer pornește backup-ul, fără atingere pe telefon.
    Cu **Pornește și singur**, cele mai noi fotografii și videoclipuri primesc backup când computerul
    găsește telefonul în Wi-Fi sau când conectezi cablul (cel mult o dată pe oră).
  * **Niciodată** – computerul nu poate întreba și nu găsește telefonul în apropiere.
* **VPN pe telefon:** un VPN care trimite totul prin tunel împiedică computerul să ajungă la aplicație
  prin Wi-Fi. Aplicația arată un sfat: exclude *My Mobile Media Backup* din VPN sau folosește cablul.
* **Aceeași versiune:** aplicația de pe telefon are același număr de versiune ca programul. Când este mai
  veche, ecranul de start și *Gestionează backup-urile → Prezentare generală* arată **Actualizează
  aplicația de pe telefon**. Copiile mai vechi ale aplicației sunt eliminate automat.
* Aplicația poate doar să citească fotografii și videoclipuri. Computerul cere fiecare fișier; telefonul
  răspunde doar computerului asociat și nu trimite niciodată nimic singur.

**Când este oprită din nou depanarea** (aplicația de pe telefon face asta chiar dacă computerul nu mai este acolo):

1. Backup-urile prin Wi-Fi rulează în mod normal prin aplicația de pe telefon, cu depanarea oprită; Depanarea
   wireless este folosită doar pentru telefoanele fără aplicație.
2. O singură conexiune per backup: prin cablu, Depanarea wireless este oprită la început;
   prin aplicație, prin Wi-Fi, depanarea USB este oprită la început.
3. Cât timp cablul USB este conectat, depanarea rămâne pornită; la 5 minute după deconectare este
   oprită (numărătoare inversă pe telefon).
4. Cablul nu a fost conectat niciodată: oprită la 5 minute după *Permite backup-ul* dacă nu a pornit niciun backup.
5. În timpul unui backup prin Wi-Fi computerul spune „încă sunt aici” la fiecare 30 de secunde; nimic timp de 2 minute → oprită.
6. Imediat după backup, computerul o oprește.

**Wi-Fi fără aplicație (Depanare wireless, Android 11 și mai nou).** Totul funcționează ca prin
cablu, inclusiv amprentele pe telefon – doar mai lent.

1. Telefon: *Setări → Sistem → Opțiuni pentru dezvoltatori → Depanare wireless* → pornit.
2. Program: **Asociază prin Wi-Fi…** → pe telefon *Asociază dispozitivul cu cod QR* și scanează codul (sau
   *Asociază dispozitivul cu un cod de asociere* și tastează cele 6 cifre). Este nevoie doar o dată.
3. De atunci telefonul este găsit ori de câte ori Depanarea wireless este pornită și amândouă sunt în același Wi-Fi.

**Fără router? Wi-Fi direct.** **Wi-Fi direct…** îi permite computerului să deschidă propria rețea Wi-Fi
(Linux: pe 5 GHz dacă se poate; Windows: *Hotspotul mobil* al său). Telefonul se conectează la ea
cu un cod QR. Pe Linux, majoritatea computerelor părăsesc între timp rețeaua Wi-Fi obișnuită; ea
revine când Wi-Fi direct este oprit. Pe Windows, rețeaua Wi-Fi obișnuită rămâne.

**Cum este recunoscut telefonul în siguranță.** Când aplicația este asociată, ea creează o cheie în cipul
de securitate al telefonului; computerul îi stochează amprenta. Modelul, numărul de serie sau numele singure
nu sunt niciodată considerate de încredere – fiecare conexiune verifică această cheie (conexiune criptată cu
certificatul memorat) înainte de a trimite orice altceva.

* **Cablu:** computerul ajunge la aplicație prin cablu și verifică cheia – starea spune atunci
  *verificat*. Asocierea prin cablu nu are nevoie de cod: atingi **Asociază** pe telefon.
* **Wi-Fi:** aplicația se anunță cu un nume aleatoriu și un cod care se schimbă la fiecare 10 minute
  și pe care doar un computer asociat îl poate recunoaște. Alții din aceeași rețea nu pot vedea despre
  ce telefon este vorba.
* **Bluetooth** (doar pentru a găsi telefonul): același cod care se schimbă, plus adresa Wi-Fi a
  telefonului, criptată. Computerul se conectează apoi prin Wi-Fi. **Prin Bluetooth nu se trimit niciodată fișiere.**
  Pentru asta, aplicația de pe telefon are nevoie de permisiunea „Dispozitive din apropiere”.

### Folderele telefonului

**Cameră** adaugă folderul camerei Android (`DCIM/Camera`). **Alege foldere…** listează folderele
telefonului – de exemplu capturile de ecran (`Pictures/Screenshots`, pe Samsung `DCIM/Screenshots`), imaginile
WhatsApp, `Movies`, `Download` – sau îți permite să tastezi unul.

**Păstrează structura originală de foldere** (opțiune): fișierele din alte foldere decât folderul camerei
își păstrează folderele în backup, de exemplu *Karen / Pixel 10 Pro / Pictures / Screenshots*. Folderul
camerei este întotdeauna sortat în foldere pe ani și luni.

### Unități de backup și planuri de backup

*Adaugă unitate…* listează unitățile externe conectate – și unitățile care sunt conectate, dar încă
nedeschise (Linux: se deschid cu un clic, fără parolă). *Adaugă folder…* îți permite să alegi orice folder. O
previzualizare arată exact unde vor ajunge fișierele. Un telefon arată doar unitățile folosite înainte cu el,
deja bifate.

Fiecare unitate are un **plan de backup**:

* **Simplu** – un singur folder care crește; se adaugă doar fotografiile și videoclipurile noi.
* **Bunic-Tată-Fiu** – backup-uri datate: un backup **complet** la fiecare 3 luni, unul **diferențial**
  în fiecare lună și unele **incrementale** între ele. Backup-urile complete și diferențiale conțin și
  fișierele mai vechi de care au nevoie, astfel încât fotografiile șterse de pe telefon rămân în fiecare backup complet.

Cele două pot fi combinate, de exemplu *Simplu* pe o unitate și *Bunic-Tată-Fiu* pe cealaltă.

### Ce se află pe unitate

* **PhoneBackups** – folderul de pe unitate
  * **Karen** – câte un folder pentru fiecare proprietar
    * **Pixel 10 Pro** – backup-ul acestui telefon
      * **Logs** – rapoartele (`.txt`, `.html`, `.csv`), de ex. *Backup Pixel 10 Pro Karen 2026-11-02*
      * **2026**
        * **26.01 … 26.12** – fotografiile și videoclipurile din fiecare lună
        * **raw / 26.01 …** – doar dacă există fotografii RAW / DNG
      * **.phonebackup** – ce are deja backup (te rugăm să nu îl ștergi)

* Folder de lună = an + lună: `26.02` înseamnă februarie 2026.
* Folderele sunt create doar când un fișier ajunge în ele – fără foldere goale.
* Luna vine din data la care a fost făcută fotografia sau videoclipul; altfel din numele fișierului
  (`PXL_20261102_…`); altfel din data fișierului.
* Fotografiile în mișcare, HEIC, PNG și altele contează ca fotografii; DNG și alte fișiere RAW ajung în `raw`.
* Același nume, conținut diferit → fișierul nou este salvat ca `name_1.jpg`. Fișierele identice sunt
  stocate o singură dată.
* Un al doilea raport în aceeași zi primește ora adăugată la nume.
* Backup-urile făcute cu versiuni mai vechi (foldere de lună ca `02.February-photos`, foldere de backup ca
  `Pixel 10 Pro - Karen`, rapoarte lângă fotografii) sunt convertite înainte de următorul backup. Înainte ca
  folderele de lună să fie redenumite, programul le listează și poți păstra numele vechi. Fișierele sunt doar
  mutate, niciodată șterse.

### Siguranță

* **Telefon → computer:** cu ADB și cu aplicația de pe telefon, telefonul calculează amprenta
  (SHA-256) a fiecărui fișier, iar programul o compară cu datele primite.
* **Computer → unitate:** fiecare copie este scrisă pe disc, citită înapoi și amprenta ei comparată.
* Fișierele sunt scrise sub un nume temporar și redenumite doar după verificare. Un backup întrerupt
  nu lasă niciodată fișiere pe jumătate; următorul backup pur și simplu continuă.
* Spațiul liber este verificat mai întâi. Dacă o unitate se defectează sau se umple, backup-ul continuă pe
  cealaltă unitate, iar raportul arată asta cu roșu.
* **Niciodată telefonul greșit:** fiecare backup își ține minte telefonul (modelul, numărul de serie, cheia
  aplicației de pe telefon). Înainte de backup telefonul conectat este verificat: alt număr de serie sau altă cheie →
  **refuzat, nu se copiază nimic**. Dacă se poate compara doar modelul, trebuie să confirmi. Chiar
  înainte de primul fișier telefonul este verificat a doua oară.

### Gestionează backup-urile

**Backup-uri** listează toate backup-urile tale. Alege unul ca să-i vezi filele:

* **Prezentare generală** – cel mai recent backup, ce unități de backup sunt complete, backup-urile
  Bunic-Tată-Fiu și backup-urile care nu s-au terminat. După fiecare backup programul întreabă dacă este
  complet.
* **Folderele telefonului** – folderele pe care le copiază *Actualizează backup-ul*.
* **Unități de backup** – unitățile acestui backup și planurile lor.
* **Foldere de import** – adaugă fotografii vechi la acest backup (vezi mai jos).
* **Istoricul backup-urilor** – fiecare backup cu rezultatul și raportul său.

**Telefoane vechi și unități vechi.** *Backup nou al unui telefon sau disc vechi…* creează un backup propriu
(de exemplu „Galaxy S7 – Kevin” sau „Disc vechi – Kevin”); *Foldere de import* adaugă la un backup existent.
Adaugă folderele (de exemplu copia unui telefon vechi și a cardului său SD) și apasă *Alege folderele
de importat…*: fiecare folder cu fișiere este listat cu fotografiile, videoclipurile și celelalte fișiere ale lui;
datele aplicațiilor, cache-urile, miniaturile, coșul de gunoi și folderele ascunse sunt lăsate deoparte. Pentru fiecare folder alege:

* **Sortează în foldere an/lună** – sortat după dată exact ca un backup de telefon.
* **Păstrează folderul așa cum este** – copiat cu numele lui în partea de sus a backup-ului (de exemplu
  *Concediu Italia 2019 / Ziua 1*). Subfolderele sunt rânduri separate – bifează-le și pe ele ca să păstrezi
  tot arborele.

Fiecare fișier este verificat ca la un backup de telefon, fișierele identice sunt stocate o singură dată, iar
folderele vechi sunt doar citite.

**Backup-uri sigure (a doua copie).** Copiază un backup pe o a doua unitate sau pe **Google Drive**.
Fiecare copie primește propriul folder datat.

| Tip | Copiază |
|---|---|
| completă | totul |
| diferențială | tot ce e nou de la ultima copie **completă** |
| incrementală | tot ce e nou de la **ultima** copie (de orice tip) |

**Automat – Bunic-Tată-Fiu** (implicit) alege tipul: completă la fiecare 3 luni
(bunicul), diferențială în fiecare lună (tatăl), incrementală între ele (fiul). Păstrează cele mai noi
4 copii complete, 3 diferențiale și 6 incrementale și tot ce le trebuie pentru o restaurare. Cele mai vechi
sunt propuse pentru eliminare și șterse **doar după ce confirmi** (*Curăță exporturile vechi…*). Fiecare
fișier copiat este comparat cu amprenta din backup – un fișier care s-a deteriorat pe prima
unitate este raportat ca avertisment.

**Google Drive.** *Adaugă la spațiul de stocare cloud → Google Drive* te autentifică prin browser. Programul
poate vedea doar fișierele pe care le-a încărcat el însuși; autentificarea rămâne pe acest computer.

* **Copie** – o oglindă a backup-ului în *My Drive / My Smartphone Media Backup*: se încarcă doar fișierele
  noi, nimic nu este șters sau suprascris.
* **Bunic-Tată-Fiu** – fiecare fotografie este stocată o **singură dată**; copiile ulterioare trimit la ea
  (scurtături, fără spațiu în plus). Te rugăm să nu ștergi manual fotografii individuale de acolo – fiecare
  copie care trimite la ele le-ar pierde.

Fiecare încărcare este verificată cu amprenta proprie a Google. Politica de confidențialitate:
<https://machetso.github.io/my-smartphone-media-backup/privacy.html>

**Restaurare.** Alege copia (pe o unitate sau pe Google Drive), data și folderul de destinație. Programul
reconstruiește un folder complet din cât mai puține copii și verifică fiecare fișier.

### Setările programului

* **Limbă** (și prin globul din dreapta sus) – se schimbă după o repornire.
* **ADB** – găsit automat; *Descarcă ADB…* îl aduce de la Google.
* **Forțează scrierea datelor pe disc înainte de verificare** – mai sigur, ușor mai lent (activat implicit).
* **Ține computerul treaz** în timpul backup-ului, importului, copierii și restaurării (activat implicit).
  Setările de alimentare în sine nu sunt modificate. Linux: standby-ul, închiderea capacului și oprirea sunt
  blocate cât rulează o sarcină, iar ecranul rămâne pornit. Windows: modul de repaus este împiedicat, iar Windows
  întreabă înainte de oprire; capacul și butonul de pornire urmează setările Windows.
* **Caută o versiune nouă la pornire** – o dată pe zi. *Actualizează acum* descarcă noua versiune, verifică
  dacă este semnată de proiect, înlocuiește programul și îl repornește. Setările, unitățile, telefoanele
  și asocierile rămân. Dacă noua versiune nu pornește, cea veche este pusă la loc automat.
* **Telefoane cunoscute** – telefoanele asociate, versiunea aplicației de pe telefon și actualizările automate ale aplicației.

Setările sunt stocate în `~/.config/phonebackup/config.json` (Windows:
`%APPDATA%\PhoneBackup\config.json`).

**Pictogramă de pornire (Linux):** scriptul *install-linux-desktop.sh* din folderul programului pune programul
în meniul de aplicații și pe desktop.

### Testat cu

* Linux (Pop!_OS) cu un Google Pixel 10 Pro (Android 17) prin USB 3 cu ADB: 1372 de fișiere / 20 GB
  pe două unități externe în același timp, aprox. 24 MB/s.
* Samsung Galaxy S20 FE prin USB (ADB) și prin Wi-Fi cu aplicația de pe telefon: 12,4 MB/s prin Wi-Fi.
* Google Drive: Copie și Bunic-Tată-Fiu cu un backup de 20 GB, curățare și restaurare.
* Încă netestat pe hardware real: varianta de rezervă cu transfer de fișiere (MTP) și Windows în general.

## Licență

MIT – vezi [LICENSE](LICENSE). Ce este nou: [CHANGELOG.md](CHANGELOG.md).
