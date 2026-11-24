# My Mobile Media Backup

**Version 0.9.9.1**

Sauvegarde les photos et vidéos de ton téléphone Android sur un ou plusieurs disques externes – vérifiées
fichier par fichier, triées par année et par mois, avec un rapport après chaque sauvegarde. Pour Windows et Linux.

## Points forts

* **Un clic** – le téléphone et l’ordinateur indiquent combien de photos et de vidéos ne sont pas encore
  sauvegardées (et leur taille) ; un appui sur le téléphone ou un clic sur l’ordinateur met la sauvegarde à jour.
* **Seules les nouvelles photos et vidéos sont copiées** – la deuxième sauvegarde prend des minutes, pas des heures.
* **Chaque fichier est vérifié.** Le téléphone calcule une empreinte (SHA-256) de chaque fichier, le
  programme la compare avec ce qui est arrivé, puis encore une fois avec ce qui a été écrit sur le disque.
* **Plusieurs disques en même temps** – le téléphone n’est lu qu’une seule fois.
* **Tri automatique** dans des dossiers par année et par mois (`2026/26.11`), les photos RAW à part.
* **Rien n’est jamais supprimé** – ni sur le téléphone, ni dans la sauvegarde.
* **Toujours la connexion la plus rapide** – câble USB, Wi-Fi ou le propre Wi-Fi de l’ordinateur ; le
  programme choisit tout seul.
* **Jamais le mauvais téléphone** – chaque sauvegarde connaît son téléphone ; un autre téléphone est refusé.
* **Sauvegardes automatiques** – quand un téléphone connu rentre à la maison, le programme peut le sauvegarder tout seul.
* **Deuxième copie** sur un autre disque ou sur Google Drive, avec les anciens états conservés
  (Grand-père-Père-Fils), et **restauration** en un clic.
* **Les anciens téléphones et les anciens disques** peuvent être ajoutés à une sauvegarde ou recevoir leur propre sauvegarde.
* Un rapport (texte, page web et tableau) après chaque sauvegarde.
* En allemand, anglais, français, espagnol, roumain, hébreu et klingon.

## Comment ça marche – en bref

Le programme copie les photos et vidéos de ton téléphone sur un disque externe (par exemple un disque dur
USB). Chaque téléphone a son propre dossier sur le disque : *Propriétaire / Téléphone*, par exemple
*Karen / Pixel 10 Pro*. À l’intérieur, les photos et vidéos sont triées dans un dossier par mois.

Le programme se souvient de ce qui est déjà sur le disque. Chaque sauvegarde suivante n’ajoute que ce qui est nouveau –
c’est pourquoi tu peux simplement appuyer sur **Mettre à jour la sauvegarde** une fois par semaine.

### Ta première sauvegarde

1. **Télécharge** le programme depuis la [page des versions](https://github.com/machetso/my-mobile-media-backup/releases)
   et démarre-le – rien à installer. Windows : le fichier `.exe`. Linux : le fichier `.tar.gz`.
2. **Branche le disque externe.**
3. **Branche le téléphone avec son câble USB** et déverrouille-le. Si le téléphone demande à quoi sert la
   connexion USB, choisis **Transfert de fichiers**. La barre colorée en haut indique si le
   téléphone est connecté.
4. Clique sur **Nouvelle sauvegarde…**, saisis ton nom comme **propriétaire** (le nom du téléphone se remplit
   tout seul), vérifie les **dossiers du téléphone** (le dossier de l’appareil photo y est déjà) et coche le
   **disque de sauvegarde**.
5. Clique sur **Démarrer la sauvegarde**. La barre en bas indique l’avancement et la durée.
6. Une fois terminé, **Ouvrir le rapport** montre ce qui a été copié, **Ouvrir le dossier de sauvegarde** ouvre les
   photos sur le disque.

### Chaque sauvegarde suivante

Branche le disque. Sur l’écran d’accueil, ton téléphone a son propre bouton **Mettre à jour la sauvegarde** – clique dessus.
Seules les nouvelles photos et vidéos sont copiées. Avec l’app du téléphone (voir *Astuces*), le téléphone n’a même pas
besoin d’être branché : quand il est sur le même Wi-Fi, sa ligne indique par exemple *À proximité – 23 photos et
4 vidéos (1,5 GB) à sauvegarder*, et un clic suffit. Ou appuie sur **Sauvegarder maintenant** sur le téléphone.

### Astuces

* **Plus rapide :** active une fois le *débogage USB* sur le téléphone (le programme te montre comment, pas à pas,
  pour ton modèle de téléphone). La sauvegarde est alors deux à quatre fois plus rapide.
* **Sans câble :** installe l’app du téléphone *My Mobile Media Backup* (*Aide à la connexion…* sur l’écran
  d’accueil affiche un code QR). La sauvegarde fonctionne alors par Wi-Fi, et le téléphone et l’ordinateur se trouvent
  tout seuls.
* **Deux disques** sont plus sûrs qu’un seul : coche les deux, ils sont écrits en même temps.

## Manuel détaillé

### La fenêtre

* **Écran d’accueil :** l’état de la connexion (rouge = aucun téléphone connecté, jaune = quelque chose à faire sur
  le téléphone, vert = connecté – il indique aussi comment : câble USB ou Wi-Fi, et si le transfert des données
  est vérifié), **Aide à la connexion…** et **Connexions possibles**. Un téléphone connu sur le même réseau est
  affiché *à proximité*, avec **Sauvegarder maintenant** – à la maison, au bureau, partout où il a déjà été connecté. **Nouvelle sauvegarde…** démarre la sauvegarde
  d’un autre téléphone, ou avec d’autres dossiers ou disques. En dessous, **Tes téléphones** – une entrée par sauvegarde
  avec la date de la dernière sauvegarde, le nombre de photos et vidéos pas encore sauvegardées (quand le
  téléphone est à proximité ou connecté) et son propre bouton **Mettre à jour la sauvegarde**. Le bouton est gris tant
  qu’un clic ne peut pas démarrer la sauvegarde ; un clic indique alors ce qui manque. L’interrupteur **Sauvegarde auto** de
  chaque téléphone lance la sauvegarde toute seule quand le téléphone est à proximité ; de petits blocs montrent ce qui
  manque encore et la prochaine étape.
* **Barre latérale :** Sauvegardes de smartphones, Gérer les sauvegardes, Sauvegardes sûres, l’engrenage (paramètres du programme),
  Manuel et À propos. Le globe
  en haut à droite change la langue.
* **En bas :** l’avancement, la vitesse et le temps restant, avec **Annuler** (s’arrête après le fichier en cours),
  **Ouvrir le rapport** et **Ouvrir le dossier de sauvegarde**. Chaque tâche écrit aussi un fichier journal.

### Connecter le téléphone

Le programme utilise toujours **la connexion la plus rapide qu’il trouve**. Si le téléphone apparaît sur le câble USB
pendant une sauvegarde par Wi-Fi, la sauvegarde continue par le câble. **Connexions possibles** montre toutes les façons
de joindre le téléphone avec leur vitesse ; **Trouver la connexion la plus rapide** vérifie le câble, le Wi-Fi et
le Bluetooth.

| Connexion | Vitesse |
|---|---|
| Câble USB + débogage USB (activé par l’app du téléphone, ou à la main) | 45–50 MB/s (USB 3), environ 20–30 MB/s (USB 2) |
| Câble USB, transfert de fichiers normal (MTP) | 10–20 MB/s |
| Wi-Fi : app du téléphone ou débogage sans fil | 10–40 MB/s, selon le Wi-Fi |
| Wi-Fi directement vers cet ordinateur (sans routeur) | 10–30 MB/s |

**Débogage USB (ADB).** ADB (Android Debug Bridge) est l’outil USB de Google pour Android. C’est le moyen
le plus rapide et le plus sûr : le téléphone calcule lui-même l’empreinte de chaque fichier. Android exige
de l’activer une fois à la main – aucun programme ne peut le faire avant :

1. Sur le téléphone : *Paramètres → À propos du téléphone* → appuie 7 fois sur *Numéro de build* (options pour les développeurs activées).
2. *Paramètres → Système → Options pour les développeurs* → active **Débogage USB**.
3. Branche le téléphone, déverrouille-le et confirme *Autoriser le débogage USB* avec **Toujours autoriser depuis cet
   ordinateur**.

*Activer le débogage USB (première fois)…* est un guide pas à pas. Il reconnaît le téléphone sur le
câble et contient les étapes pour Pixel, Samsung, Xiaomi / Redmi / POCO, OnePlus / OPPO / realme,
Motorola, Huawei / Honor, Sony et Nothing ; pour les autres téléphones, *Rechercher ce téléphone sur le web*.

Le programme ADB lui-même vient de Google et ne peut pas être livré avec ce programme.
*Paramètres du programme → Télécharger ADB…* le récupère directement chez Google dans le dossier du programme –
un clic, aucune installation, aucun droit d’administrateur. Sous Linux, le paquet `adb` du système fonctionne aussi.

Si ADB ne fonctionne pas, le programme le dit clairement et utilise à la place le **transfert de fichiers** normal du téléphone
(MTP). Sous Linux, le téléphone est ouvert automatiquement ; choisis *Transfert de fichiers* dans la notification USB
du téléphone. MTP est plus lent, et le téléphone ne peut pas calculer d’empreintes – le rapport le signale.

**L’app du téléphone *My Mobile Media Backup*.** Avec l’app, les sauvegardes fonctionnent par Wi-Fi sans débogage
USB, l’app active et désactive pour toi la connexion la plus rapide, et le téléphone et l’ordinateur indiquent
ce qui n’est pas encore sauvegardé.

* **Installer :** *Aide à la connexion…* affiche deux codes QR : l’un connecte l’app, l’autre la télécharge
  depuis la page des versions. Par le câble USB, le programme peut installer l’app lui-même ; il **demande
  toujours d’abord** et indique quel téléphone, quelle version et pourquoi.
* **Sauvegarde :** indique combien de photos et de vidéos ne sont pas encore sauvegardées et leur taille, par
  exemple *23 photos et 4 vidéos (1,5 GB) à sauvegarder*. **Sauvegarder maintenant** démarre la sauvegarde :
  le téléphone se connecte, l’ordinateur met la sauvegarde à jour tout seul. Quand il manque quelque chose (le
  programme de l’ordinateur n’est pas lancé, le disque de sauvegarde n’est pas connecté, …) le bouton est gris et un
  appui indique quoi faire.
* **Autoriser la sauvegarde :** un seul interrupteur. Activé = la connexion la plus rapide – débogage USB et débogage sans fil
  là où l’app peut les activer, et l’accès de l’app en lecture seule par le Wi-Fi. À côté :
  *Connexion établie* ou *Non connecté* ; en dessous, combien de temps cela reste activé. **Déconnecter**
  désactive tout. Après chaque sauvegarde, l’ordinateur désactive à nouveau le débogage
  (*Désactiver … après la sauvegarde*, activé par défaut). Les options pour les développeurs restent activées.
* **Quand ton ordinateur veut une sauvegarde :**
  * **Me demander** (par défaut) – le téléphone demande *Autoriser la sauvegarde ?* ; rien ne démarre sans ton appui.
  * **Autoriser sans demander** – un clic sur l’ordinateur démarre la sauvegarde, sans appui sur le téléphone.
    Avec **Sauvegarde auto** activée pour ce téléphone sur l’ordinateur, les photos et vidéos les plus récentes
    sont sauvegardées toutes seules (au plus une fois par heure).
  * **Jamais** – l’ordinateur ne peut pas demander et ne trouve pas le téléphone à proximité.
  La question *Autoriser la sauvegarde ?* apparaît aussi directement dans l’app ouverte.
* **Économiser la batterie :** rien n’écoute en permanence. Le téléphone se signale à l’ordinateur quand il
  rejoint un Wi-Fi, quand il est en charge et toutes les 30 minutes – sur n’importe quel Wi-Fi, sans rien qui
  l’identifie. Ce n’est que sur un **Wi-Fi de confiance** (*Faire confiance au Wi-Fi actuel*) qu’une sauvegarde peut
  démarrer sans demander ; ailleurs, le téléphone demande toujours d’abord.
* **VPN sur le téléphone :** un VPN qui fait tout passer par le tunnel empêche l’ordinateur de
  joindre l’app par le Wi-Fi. L’app affiche alors un avertissement rouge en haut avec
  **Ouvrir les paramètres VPN**, et l’ordinateur le signale aussi : exclus *My Mobile Media Backup* du
  VPN, ou utilise le câble.
* **Même version :** l’app du téléphone a le même numéro de version que le programme. Quand elle est plus ancienne,
  l’écran d’accueil et *Gérer les sauvegardes → Vue d’ensemble* affichent **Mettre à jour l’app du téléphone**. Les anciennes copies de
  l’app sont supprimées automatiquement.
* L’app peut seulement lire les photos et les vidéos. L’ordinateur demande chaque fichier ; le téléphone ne répond qu’à
  l’ordinateur associé et n’envoie jamais rien de lui-même.

**Quand le débogage est désactivé à nouveau** (l’app du téléphone le fait même si l’ordinateur n’est plus là) :

1. Les sauvegardes par Wi-Fi passent normalement par l’app du téléphone avec le débogage désactivé ; le débogage sans fil ne sert
   qu’aux téléphones sans l’app.
2. Une seule connexion par sauvegarde : par le câble, le débogage sans fil est désactivé au début ;
   par l’app en Wi-Fi, le débogage USB est désactivé au début.
3. Tant que le câble USB est branché, le débogage reste activé ; 5 minutes après le débranchement, il est
   désactivé (compte à rebours sur le téléphone).
4. Câble jamais branché : désactivé 5 minutes après *Autoriser la sauvegarde* si aucune sauvegarde n’a démarré.
5. Pendant une sauvegarde par Wi-Fi, l’ordinateur dit « toujours là » toutes les 30 secondes ; rien pendant 2 minutes → désactivé.
6. Juste après la sauvegarde, l’ordinateur le désactive.

**Wi-Fi sans l’app (débogage sans fil, Android 11 et plus récent).** Tout fonctionne comme par le
câble, y compris les empreintes sur le téléphone – seulement plus lentement.

1. Téléphone : *Paramètres → Système → Options pour les développeurs → Débogage sans fil* → activé.
2. Programme : **Associer par Wi-Fi…** → sur le téléphone, *Associer l’appareil avec un code QR* et scanne le code (ou
   *Associer l’appareil avec un code d’association* et saisis les 6 chiffres). Nécessaire une seule fois.
3. Ensuite, le téléphone est trouvé chaque fois que le débogage sans fil est activé et que les deux sont sur le même Wi-Fi.

**Pas de routeur ? Wi-Fi direct.** **Wi-Fi direct…** permet à l’ordinateur d’ouvrir son propre réseau Wi-Fi
(Linux : en 5 GHz si possible ; Windows : son *Point d’accès sans fil mobile*). Le téléphone s’y
connecte avec un code QR. Sous Linux, la plupart des ordinateurs quittent pendant ce temps le Wi-Fi
normal ; il revient quand le Wi-Fi direct est arrêté. Sous Windows, le Wi-Fi normal reste.

**Comment le téléphone est reconnu en toute sécurité.** Quand l’app est associée, elle crée une clé dans la puce de
sécurité du téléphone ; l’ordinateur enregistre son empreinte. Le modèle, le numéro de série ou les noms seuls ne suffisent jamais
– chaque connexion vérifie cette clé (connexion chiffrée avec le certificat mémorisé)
avant que quoi que ce soit d’autre ne soit envoyé.

* **Câble :** l’ordinateur joint l’app par le câble et vérifie la clé – l’état indique alors
  *vérifié*. L’association par le câble ne demande aucun code : tu appuies sur **Associer** sur le téléphone.
* **Wi-Fi :** l’app s’annonce avec un nom aléatoire et un code qui change toutes les 10 minutes
  et que seul un ordinateur associé peut reconnaître. Les autres sur le même réseau ne peuvent pas voir de quel téléphone
  il s’agit.
* **Bluetooth** (seulement pour trouver le téléphone) : le même code changeant plus l’adresse Wi-Fi du téléphone,
  chiffrés. L’ordinateur se connecte ensuite par Wi-Fi. **Aucun fichier n’est jamais envoyé par Bluetooth.**
  L’app du téléphone a besoin pour cela de l’autorisation « Appareils à proximité ».

### Dossiers du téléphone

**Appareil photo** ajoute le dossier de l’appareil photo d’Android (`DCIM/Camera`). **Choisir des dossiers…** liste les
dossiers du téléphone – par exemple les captures d’écran (`Pictures/Screenshots`, sur Samsung `DCIM/Screenshots`), les images
WhatsApp, `Movies`, `Download` – ou te permet d’en saisir un.

**Garder la structure de dossiers d’origine** (option) : les fichiers des dossiers autres que celui de l’appareil photo
gardent leurs dossiers dans la sauvegarde, par exemple *Karen / Pixel 10 Pro / Pictures / Screenshots*. Le
dossier de l’appareil photo est toujours trié dans des dossiers par année et par mois.

### Disques de sauvegarde et plans de sauvegarde

*Ajouter un disque…* liste les disques externes connectés – aussi les disques branchés mais pas encore
ouverts (Linux : ils sont ouverts en un clic, sans mot de passe). *Ajouter un dossier…* te permet de choisir n’importe quel dossier. Un
aperçu montre exactement où iront les fichiers. Pour un téléphone, seuls les disques déjà utilisés avec lui sont affichés,
déjà cochés.

Chaque disque a un **plan de sauvegarde** :

* **Simple** – un dossier qui grandit ; seules les nouvelles photos et vidéos sont ajoutées.
* **Grand-père-Père-Fils** – des sauvegardes datées : une sauvegarde **complète** tous les 3 mois, une
  **différentielle** chaque mois, des **incrémentielles** entre les deux. Les sauvegardes complètes et différentielles contiennent aussi les
  fichiers antérieurs dont elles ont besoin, donc les photos supprimées du téléphone restent dans chaque sauvegarde complète.

Les deux peuvent être combinés, par exemple *Simple* sur un disque et *Grand-père-Père-Fils* sur l’autre.

### Ce qui se trouve sur le disque

* **PhoneBackups** – le dossier sur le disque
  * **Karen** – un dossier par propriétaire
    * **Pixel 10 Pro** – la sauvegarde de ce téléphone
      * **Logs** – les rapports (`.txt`, `.html`, `.csv`), p. ex. *Backup Pixel 10 Pro Karen 2026-11-02*
      * **2026**
        * **26.01 … 26.12** – les photos et vidéos de chaque mois
        * **raw / 26.01 …** – seulement s’il y a des photos RAW / DNG
      * **.phonebackup** – ce qui est déjà sauvegardé (merci de ne pas le supprimer)

* Dossier du mois = année + mois : `26.02` correspond à février 2026.
* Les dossiers ne sont créés que lorsqu’un fichier y va – pas de dossiers vides.
* Le mois vient de la date de prise de la photo ou de la vidéo ; sinon du nom du fichier
  (`PXL_20261102_…`) ; sinon de la date du fichier.
* Les photos animées, HEIC, PNG, etc. comptent comme des photos ; les DNG et autres fichiers RAW vont dans `raw`.
* Même nom, contenu différent → le nouveau fichier est enregistré sous `name_1.jpg`. Les fichiers identiques ne sont stockés
  qu’une seule fois.
* Un deuxième rapport le même jour reçoit l’heure en plus dans son nom.
* Les sauvegardes faites avec d’anciennes versions (dossiers de mois comme `02.February-photos`, dossiers de sauvegarde comme
  `Pixel 10 Pro - Karen`, rapports à côté des photos) sont converties avant la sauvegarde suivante. Avant
  de renommer les dossiers de mois, le programme les liste et tu peux garder les anciens noms. Les fichiers sont seulement
  déplacés, jamais supprimés.

### Sécurité

* **Téléphone → ordinateur :** avec ADB et avec l’app du téléphone, le téléphone calcule l’empreinte
  (SHA-256) de chaque fichier et le programme la compare avec les données reçues.
* **Ordinateur → disque :** chaque copie est écrite sur le disque, relue et son empreinte comparée.
* Les fichiers sont écrits sous un nom temporaire et renommés seulement après la vérification. Une sauvegarde interrompue
  ne laisse jamais de fichiers à moitié copiés ; la sauvegarde suivante continue simplement.
* L’espace libre est vérifié d’abord. Si un disque tombe en panne ou est plein, la sauvegarde continue sur l’autre
  disque et le rapport l’affiche en rouge.
* **Jamais le mauvais téléphone :** chaque sauvegarde se souvient de son téléphone (modèle, numéro de série, clé de l’app
  du téléphone). Avant la sauvegarde, le téléphone connecté est vérifié : un autre numéro de série ou une autre clé →
  **refusé, rien n’est copié**. Si seul le modèle peut être comparé, tu dois confirmer. Juste
  avant le premier fichier, le téléphone est vérifié une deuxième fois.

### Gérer les sauvegardes

**Sauvegardes** liste toutes tes sauvegardes. Choisis-en une pour voir ses onglets :

* **Vue d’ensemble** – la dernière sauvegarde, si les disques de sauvegarde sont à jour et si la sauvegarde
  est sécurisée (deuxième copie).
* **Disques de destination** – les disques de cette sauvegarde avec leur état (à jour, combien de photos et
  de vidéos manquent, non connecté, dossier introuvable). **Ajouter un disque…** en ajoute un ; **Intégrer un
  dossier…** trouve les dossiers de sauvegarde existants sur tes disques et les reprend ; **Préparer les dossiers**
  (il s’allume quand les disques diffèrent) met tous les disques de la sauvegarde dans le même état – il
  fusionne aussi une ancienne sauvegarde imbriquée à l’intérieur, et les fichiers identiques vont dans un dossier à vérifier
  (*Doublons*) au lieu d’être supprimés. **Contrôle d’intégrité…** relit chaque photo et vidéo
  et la compare avec son empreinte. Chaque sauvegarde porte une marque sur ses disques, de sorte qu’un disque qui
  revient sous un autre chemin (par exemple des emplacements VeraCrypt échangés) est retrouvé tout seul.
* **Dossiers du téléphone** – les dossiers que *Mettre à jour la sauvegarde* copie (*Dossiers supplémentaires…*).
* **Importer des médias** – ajouter d’anciennes photos à cette sauvegarde (voir ci-dessous).
* **Historique des sauvegardes** – chaque sauvegarde avec son résultat et son rapport.

**Anciens téléphones et anciens disques.** *Nouvelle sauvegarde…* crée une sauvegarde à part
(par exemple « Galaxy S7 – Kevin » ou « Old drive – Kevin ») ; *Importer des médias* ajoute à une sauvegarde existante.
Ajoute les dossiers (par exemple la copie d’un ancien téléphone et de sa carte SD) et clique sur *Choisir les dossiers
à importer…* : chaque dossier contenant des fichiers est listé avec ses photos, vidéos et autres fichiers ; les données d’apps,
caches, miniatures, corbeilles et dossiers cachés sont laissés de côté. Pour chaque dossier, choisis :

* **Trier dans les dossiers année/mois** – trié par date exactement comme une sauvegarde de téléphone.
* **Garder le dossier tel quel** – copié avec son nom tout en haut de la sauvegarde (par exemple
  *Holiday Italy 2019 / Day 1*). Les sous-dossiers sont des lignes séparées – coche-les aussi pour garder toute
  l’arborescence.

Chaque fichier est vérifié comme pour une sauvegarde de téléphone, les fichiers identiques ne sont stockés qu’une fois, et les anciens dossiers
sont seulement lus.

**Sauvegardes sûres (deuxième copie)** – sa propre page dans la barre latérale. Copie une sauvegarde sur un deuxième disque ou
sur **Google Drive**. Chaque copie
reçoit son propre dossier daté.

| Type | Copie |
|---|---|
| complète | tout |
| différentielle | tout ce qui est nouveau depuis la dernière copie **complète** |
| incrémentielle | tout ce qui est nouveau depuis la **dernière** copie (de n’importe quel type) |

**Automatique – Grand-père-Père-Fils** (par défaut) choisit le type : complète tous les 3 mois
(grand-père), différentielle chaque mois (père), incrémentielle entre les deux (fils). Il garde les 4 copies complètes,
3 différentielles et 6 incrémentielles les plus récentes, ainsi que tout ce dont elles ont besoin pour une restauration. Les plus anciennes
sont proposées à la suppression et supprimées **seulement après ta confirmation** (*Nettoyer les anciennes copies de sécurité…*). Chaque
fichier copié est comparé avec l’empreinte de la sauvegarde – un fichier endommagé sur le premier
disque est signalé par un avertissement.

**Google Drive.** *Ajouter au stockage cloud → Google Drive* te connecte via le navigateur. Le programme
ne voit que les fichiers qu’il a lui-même envoyés ; la connexion reste sur cet ordinateur.

* **Copie** – un miroir de la sauvegarde dans *My Drive / My Smartphone Media Backup* : seuls les nouveaux fichiers sont
  envoyés, rien n’est supprimé ni écrasé.
* **Grand-père-Père-Fils** – chaque photo n’est stockée qu’**une seule fois** ; les copies suivantes y renvoient
  (raccourcis, aucun espace supplémentaire). Merci de ne pas y supprimer de photos à la main – chaque copie qui
  y renvoie les perdrait.

Chaque envoi est vérifié avec l’empreinte de Google. Politique de confidentialité :
<https://machetso.github.io/my-smartphone-media-backup/privacy.html>

**Restaurer.** Choisis la copie (sur un disque ou sur Google Drive), la date et le dossier cible. Le
programme reconstruit un dossier complet à partir du plus petit nombre de copies nécessaire et vérifie chaque fichier.

### Paramètres du programme

* **Langue** (aussi via le globe en haut à droite) – change après un redémarrage.
* **ADB** – trouvé automatiquement ; *Télécharger ADB…* le récupère chez Google.
* **Forcer l’écriture des données sur le disque avant la vérification** – plus sûr, un peu plus lent (activé par défaut).
* **Garder l’ordinateur éveillé** pendant la sauvegarde, l’import, la copie et la restauration (activé par défaut). Les
  paramètres d’alimentation eux-mêmes ne sont pas modifiés. Linux : la mise en veille, la fermeture du capot et l’arrêt sont bloqués
  pendant une tâche, et l’écran reste allumé. Windows : la mise en veille est empêchée et Windows demande avant
  de s’éteindre ; le capot et le bouton d’alimentation suivent les paramètres de Windows.
* **Rechercher une nouvelle version au démarrage** – une fois par jour. *Mettre à jour maintenant* télécharge la nouvelle version, vérifie
  qu’elle est signée par le projet, remplace le programme et le redémarre. Les paramètres, disques, téléphones
  et associations sont conservés. Si la nouvelle version ne démarre pas, l’ancienne est remise en place automatiquement.
* **Téléphones connus** – les téléphones associés, la version de l’app du téléphone et les mises à jour automatiques de l’app.

Les paramètres sont enregistrés dans `~/.config/phonebackup/config.json` (Windows :
`%APPDATA%\PhoneBackup\config.json`).

**Icône de démarrage (Linux) :** le script *install-linux-desktop.sh* dans le dossier du programme ajoute le programme
au menu des applications et sur le bureau.

### Testé avec

* Linux (Pop!_OS) avec un Google Pixel 10 Pro (Android 17) en USB 3 avec ADB : 1372 fichiers / 20 GB
  vers deux disques externes en même temps, environ 24 MB/s.
* Samsung Galaxy S20 FE en USB (ADB) et en Wi-Fi avec l’app du téléphone : 12,4 MB/s en Wi-Fi.
* Google Drive : Copie et Grand-père-Père-Fils avec une sauvegarde de 20 GB, nettoyage et restauration.
* Pas encore testé sur du vrai matériel : le transfert de fichiers de secours (MTP) et Windows en général.

## Licence

MIT – voir [LICENSE](LICENSE). Les nouveautés : [CHANGELOG.md](CHANGELOG.md).
