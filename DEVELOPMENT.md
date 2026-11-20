# Development

Notes for working on the source code. The user manual is [README.md](README.md).

## Start from source

Python 3.8+. The graphical interface needs PySide6; the terminal version needs no extra packages.

```
./start-linux.sh                   # Linux (uses the project's .venv, PySide6 is already installed there)
start-windows.pyw                  # Windows: double-click (after: py -m pip install PySide6)
```

**Terminal version:** `python3 smartphone_media_backup.py --cli` or directly
`smartphone_media_backup.py backup | export | restore | settings`. If PySide6 is missing,
`smartphone_media_backup.py` starts the terminal version automatically. Started from source, update
with `git pull` instead of the built-in update.

Bluetooth discovery needs the Python package `bleak` (in requirements.txt).

Windows MTP fallback: needs `py -m pip install pywin32` once.

## Tests

```
python3 -m unittest discover tests
```

The tests run in a throw-away sandbox (see `tests/__init__.py`) and never touch real settings.

## Icons

`./install-linux-desktop.sh` installs the start icon (`--remove` takes it away). All icons – the
program's and the phone app's (Android mipmaps) – are built from `assets/icon.svg` with
`.venv/bin/python tools/make_icons.py`.

## Phone app

The Android app is in `android/` (Kotlin, Jetpack Compose). It always has the program's version.
`tools/build_companion.sh` builds it and puts it into `assets/companion/MediaBackup.apk`, from where
the program installs it and every release offers it as a download (needs a JDK: `JAVA_HOME`).
Its unit tests: `cd android && ./gradlew testDebugUnitTest`.

## Translations

The program and the phone app share the dictionaries `i18n/<code>.json`. New texts are written in
English; `python3 tools/i18n_keys.py` shows what each language still lacks (`--missing de` gives
the list as JSON). The manual is translated as `README.<code>.md` with the same headings as
README.md (a test compares them).

## Google key

Builds from source need the app's Google key: `python3 tools/set_google_key.py client_secret_….json`
(writes the git-ignored `phonebackup/_gkey.py`); release builds get it from GitHub secrets.

## Making a release

Push the tag → GitHub Actions builds the draft release →
`python3 tools/sign_release.py sign vX.Y.Z` on the maintainer's computer (adds the signed
`update-manifest.json`; the private key never goes to GitHub) → publish the release.

Update the version line at the top of README.md (`**Version X.Y.Z**`) with every release; the
program shows its own exact version there anyway.
