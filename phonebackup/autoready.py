"""Auto backup per phone (user request 2026-11-23): what is needed so that a backup runs completely
by itself, without anybody clicking anything – in the order the steps build on each other.

No Qt here. Each requirement: Req(id, title, ok, done_hint, todo_hint).
"""

from dataclasses import dataclass

from .i18n import tr


@dataclass
class Req:
    id: str
    title: str
    ok: bool
    done: str        # mouse-over text when fulfilled
    todo: str        # mouse-over text when not (yet) fulfilled
    optional: bool = False   # not needed for the switch (user 2026-11-23: battery unrestricted)

    @property
    def hint(self):
        if self.ok:
            return "✓ " + self.title + "\n" + self.done
        return ("○ " + tr("%s (optional)", self.title) if self.optional else "✗ " + self.title) + "\n" + self.todo


def requirements(has_backup, drive_there, paired, allow_without_asking, home_wifi, unrestricted):
    """The six steps, in the order they build on each other (the phone app reports the last three
    when it checks in – battery-saving backup requests, 2026-11-23)."""
    return [
        Req("backup", tr("First backup made"), has_backup,
            tr("The first backup of this phone was made by hand – it says which folders and which drives."),
            tr("Make the first backup by hand: “New backup…”.")),
        Req("drive", tr("Backup drive connected"), drive_there,
            tr("A backup drive of this backup is connected."),
            tr("Connect (and, for VeraCrypt, open) a backup drive of this backup – the automatic backup "
               "only writes to its own drives.")),
        Req("paired", tr("Phone app paired"), paired,
            tr("The phone app is installed on the phone and paired with this computer."),
            tr("Install the phone app and pair it: “Help connect…” on the start screen, then scan the "
               "QR code with the phone.")),
        Req("allow", tr("“Allow without asking” on the phone"), paired and allow_without_asking,
            tr("The phone app allows a backup without asking."),
            tr("Pair the phone app first.") if not paired else
            tr("In the phone app under “When your computer wants a backup” choose “Allow without asking”. "
               "Android then asks to let the app run unrestricted – allow it.")),
        Req("wifi", tr("Trusted Wi-Fi on the phone"), paired and allow_without_asking and home_wifi,
            tr("The phone trusts your home Wi-Fi – there it checks in with this computer (when it joins the "
               "Wi-Fi, when it is charging and every 30 minutes)."),
            tr("Optional. Without it the automatic backup runs only over the USB cable. For backups without "
               "a cable: in the phone app under “Trusted Wi-Fi” tap “Trust the current Wi-Fi” while the "
               "phone is in your home Wi-Fi."),
            optional=True),                     # the cable needs no Wi-Fi (user 2026-11-23)
        Req("battery", tr("Battery: unrestricted"), paired and allow_without_asking and unrestricted,
            tr("The backup starts on the phone without any tap (battery: unrestricted)."),
            tr("Optional. Without it the phone asks once per backup (“Allow backup?” – one tap). For no tap "
               "at all: on the phone Settings → Apps → My Mobile Media Backup → Battery → “Unrestricted”."),
            optional=True),
    ]


# the next thing to do, in plain words (user request 2026-11-23) – one sentence per step
def _next_texts():
    return {
        "backup": tr("Next step: make the first backup of this phone – click “New backup…” above."),
        "drive": tr("Next step: plug in your backup drive (with VeraCrypt: open it first)."),
        "paired": tr("Next step: put the app on your phone and connect it with this computer – click "
                     "“Help connect…” at the top."),
        "allow": tr("Next step: open the app on your phone and choose “Allow without asking”."),
        "wifi": tr("Tip: it works over the USB cable now. To back up without a cable as well: at home, open "
                   "the app on your phone and tap “Trust the current Wi-Fi”."),
        "battery": tr("Tip: so that the phone does not ask before each backup – on the phone open Settings → "
                      "Apps → My Mobile Media Backup → Battery and choose “Unrestricted”."),
    }


def next_step(reqs, on):
    """The sentence under the blocks: the first step that is not done yet; "" when nothing is left."""
    texts = _next_texts()
    for r in reqs:
        if not r.ok and not r.optional:
            return texts.get(r.id, r.todo)
    if not on:
        return tr("Everything is ready – switch “Auto backup” on.")
    for r in reqs:
        if not r.ok:
            return texts.get(r.id, r.todo)
    return ""


def ready(reqs):
    """The switch can be used: every step that is not optional is done."""
    return all(r.ok for r in reqs if not r.optional)


def help_text():
    """The text behind the small "?" next to the switch."""
    steps = [
        tr("<b>First backup made</b> – make the first backup by hand (“New backup…”). It sets which phone "
           "folders and which drives are used."),
        tr("<b>Backup drive connected</b> – a drive of this backup must be connected (VeraCrypt: opened). "
           "The automatic backup never chooses other drives."),
        tr("<b>Phone app paired</b> – install the phone app and pair it with this computer: “Help connect…” "
           "on the start screen, scan the QR code with the phone."),
        tr("<b>“Allow without asking”</b> – in the phone app under “When your computer wants a backup”."),
        tr("<b>Trusted Wi-Fi on the phone</b> (optional) – in the phone app under “Trusted Wi-Fi”: tap "
           "“Trust the current Wi-Fi” while the phone is in your home Wi-Fi (several are possible). Only "
           "there the phone checks in with this computer. Without it the backup runs over the USB cable only."),
        tr("<b>Battery: unrestricted</b> (optional) – on the phone: Settings → Apps → My Mobile Media "
           "Backup → Battery → “Unrestricted”. Then the backup starts without any tap; without it the "
           "phone asks once per backup (“Allow backup?”)."),
    ]
    return ("<p>" + tr("With <b>Auto backup</b> on, the backup runs completely by itself: the phone checks "
                       "in with this computer when it joins your home Wi-Fi, when it is charging and "
                       "every 30 minutes – nothing runs on the phone in between (saves battery). Then "
                       "the new photos and videos are copied – at most once an hour, without any window.")
            + "</p><p>" + tr("The switch can be used when the first four steps are done – the blocks "
                             "show which ones are (point at a block for details). The last two are "
                             "optional:") + "</p><ol>"
            + "".join(f"<li style='margin-bottom:5px'>{s}</li>" for s in steps) + "</ol><p>"
            + tr("The program must be running on the computer (it may be in the background).") + "</p>")
