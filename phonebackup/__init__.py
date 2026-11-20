"""My Mobile Media Backup - verified photo/video backup from Android phones to external drives."""

# renamed 2026-11-20 (was "My Smartphone Media Backup"; phone app "My Media Backup")
APP_NAME = "My Mobile Media Backup"

__version__ = "0.9.9.0"


def _start_language():
    """The interface language, set once when the program starts – before any window or text
    table is built (texts are read when they are created). Every entry point imports this
    package first: GUI, terminal version, start scripts, the Windows .exe."""
    try:
        from . import i18n
        i18n.use(i18n.stored_choice())
    except Exception:  # noqa: BLE001 - never stop the program because of the language
        pass


_start_language()
