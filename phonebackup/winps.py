"""Windows: small PowerShell scripts for Windows' own interfaces (WinRT) – the Mobile hotspot and
Bluetooth (user request 2026-11-20: the Windows version gets the same functions as the Linux one).

Values go to the script as environment variables (PB_…), never pasted into the script text, so a
network name or password cannot change what the script does. No Qt here.
"""

import os
import subprocess
import sys

_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0

# Await a WinRT async operation / action from Windows PowerShell 5.1 (it has no 'await').
PRELUDE = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$__ext = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 }
$__op = $__ext | Where-Object { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
$__act = $__ext | Where-Object { $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' } | Select-Object -First 1
function AwaitOp($op, [Type]$type) {
    $t = $__op.MakeGenericMethod($type).Invoke($null, @($op)); $null = $t.Wait(60000); $t.Result }
function AwaitAction($op) { $t = $__act.Invoke($null, @($op)); $null = $t.Wait(60000) }
"""


def powershell():
    """Full path: Windows would otherwise also look in the current folder for powershell.exe."""
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell",
                        "v1.0", "powershell.exe")


# Every script answers with one of its known lines – also when Windows refuses (no Wi-Fi adapter, no
# Bluetooth, …): then "PSERROR <reason>" (found on GitHub's Windows machine 2026-11-20).
WRAP = "try {{\n{body}\n}} catch {{ 'PSERROR ' + $_.Exception.Message }}\nexit 0\n"

# PowerShell errors that mean the SCRIPT is wrong (not the computer) – the real-Windows tests check them
SCRIPT_ERRORS = ("Unable to find type", "is not recognized as", "Cannot find an overload",
                 "Method invocation failed", "ParserError", "Missing ", "Unexpected token")


def run(script, env=None, timeout=90):
    """Run `script` (after PRELUDE). Returns (exit code, stdout text). Raises OSError /
    subprocess.TimeoutExpired."""
    full_env = dict(os.environ)
    full_env.update({k: str(v) for k, v in (env or {}).items()})
    r = subprocess.run([powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", PRELUDE + WRAP.format(body=script)], capture_output=True, timeout=timeout,
                       env=full_env, creationflags=_NO_WINDOW)
    out = r.stdout.decode("utf-8", "replace").strip()
    if r.returncode and not out:
        out = r.stderr.decode("utf-8", "replace").strip()
    return r.returncode, out
