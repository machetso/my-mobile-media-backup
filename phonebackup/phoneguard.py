"""Read-only guard for everything the app sends to the phone over ADB.

ADB itself cannot be restricted on the phone: a trusted computer may do anything the 'shell' user
may do. So the app restricts itself. Every command for the phone must match one of the fixed,
read-only templates below, and every path in it must be inside the phone's shared storage
(/sdcard). Anything else - deleting, installing, changing settings, screenshots, input, ... - is
refused before it reaches adb, even if a bug or a manipulated file name tried it.

The only exceptions are the few fixed commands in CONTROL (no arguments, nothing built from data):
they let the app switch USB debugging off again after a backup and set up its own phone app so it
can switch debugging on for the next backup (user request 2026-11-04). See `check_control`. And
`old_copy_command`: remove an OLD copy of the phone app (asked first, user 2026-11-17).
"""

import re

from .i18n import tr

PHONE_ROOT = "/sdcard"

_Q = r"'(?:[^']|'\\'')*'"              # one argument quoted by sources._q
_TEMPLATES = [re.compile(t) for t in (
    r"getprop (?:ro\.product\.model|ro\.product\.manufacturer|ro\.build\.version\.release|ro\.serialno)",
    rf"\[ -d (?P<p0>{_Q}) \] && echo YES",
    rf"find (?P<p0>{_Q}) -mindepth 1 -maxdepth 1 -type d 2>/dev/null",
    rf"find (?P<p0>{_Q}) -type f -exec stat -c '%s %Y %n' \{{\}} \+ 2>/dev/null",
    r"command -v sha256sum >/dev/null && echo YES",
    rf"sha256sum(?P<many>(?: {_Q})+)",
    rf"cat(?P<many>(?: {_Q})+)",           # one file, or several small ones in a row
)]
_ONE_Q = re.compile(_Q)


COMPANION_PACKAGE = "io.github.machetso.mediabackup"

# exact commands, nothing appended - see check_control
CONTROL = {
    "usb_debugging_off": "settings put global adb_enabled 0",
    "wifi_debugging_off": "settings put global adb_wifi_enabled 0",
    "companion_installed": f"pm list packages {COMPANION_PACKAGE}",
    "companion_grant": f"pm grant {COMPANION_PACKAGE} android.permission.WRITE_SECURE_SETTINGS",
    "companion_granted": f"dumpsys package {COMPANION_PACKAGE}",
    "companion_path": f"pm path {COMPANION_PACKAGE}",
    "companion_open": f"am start -a android.intent.action.VIEW -d phonebackup://cable -p {COMPANION_PACKAGE}",
    # every app that opens the phone app's link: finds OLD copies of the phone app (an earlier
    # package name) that still run and block the current one (user 2026-11-17)
    "companion_copies": "cmd package query-activities --brief -a android.intent.action.VIEW -d phonebackup://cable",
}

_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")


def old_copy_command(action, package):
    """Commands for an OLD copy of the phone app (another package that opens phonebackup://):
    'version' (read its version) or 'remove' (uninstall it – only after the user said yes, and
    only a package that `companion_copies` listed; see AdbSource.remove_old_companion). Never the
    current phone app, never anything but a plain package name."""
    if not _PACKAGE.fullmatch(package or "") or package == COMPANION_PACKAGE:
        raise ForbiddenPhoneCommand(tr("refused (not an old copy of the phone app): %s", str(package)[:80]))
    if action == "version":
        return f"dumpsys package {package}"
    if action == "remove":
        return f"pm uninstall {package}"
    raise ForbiddenPhoneCommand(tr("refused (unknown control action): %s", str(action)[:80]))


class ForbiddenPhoneCommand(PermissionError):
    pass


def _unquote(q):
    return q[1:-1].replace("'\\''", "'")


def _path_ok(path):
    if not (path == PHONE_ROOT or path.startswith(PHONE_ROOT + "/")):
        return False
    return ".." not in path.split("/") and "\x00" not in path and "\n" not in path


def check(cmd):
    """Raise ForbiddenPhoneCommand unless cmd is one of the allowed read-only commands."""
    for t in _TEMPLATES:
        m = t.fullmatch(cmd)
        if not m:
            continue
        groups = m.groupdict()
        paths = []
        if groups.get("p0"):
            paths.append(_unquote(groups["p0"]))
        if groups.get("many"):
            paths += [_unquote(q) for q in _ONE_Q.findall(groups["many"])]
        if all(_path_ok(p) for p in paths):
            return
        raise ForbiddenPhoneCommand(tr("refused (path outside %s): %s", PHONE_ROOT, cmd[:200]))
    raise ForbiddenPhoneCommand(tr("refused (not a read-only backup command): %s", cmd[:200]))


def check_control(name):
    """The exact command for the control action `name` - anything not in CONTROL is refused."""
    try:
        return CONTROL[name]
    except KeyError:
        raise ForbiddenPhoneCommand(tr("refused (unknown control action): %s", str(name)[:80])) from None


_APK_PATH = re.compile(r"/data/app/[A-Za-z0-9._~=+-]+(?:/[A-Za-z0-9._~=+-]+)?/base\.apk")


def check_companion_apk(path):
    """The only file outside /sdcard the app may read: the INSTALLED phone app's own APK (to check
    who signed it). Exactly '/data/app/<dir>[/<dir>]/base.apk', no '..'."""
    if not _APK_PATH.fullmatch(path) or ".." in path.split("/"):
        raise ForbiddenPhoneCommand(tr("refused (not the phone app's file): %s", path[:200]))
    return path
