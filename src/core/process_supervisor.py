import os
import sys
import subprocess
from typing import Optional, List, Dict, Any, Tuple

class ProcessSupervisor:
    """
    Supervises and manages Antigravity IDE and client processes.
    Uses pure standard library subprocess commands (tasklist/taskkill on Windows)
    with zero external third-party dependencies (no psutil requirement).
    Ported from src-tauri/src/modules/process.rs.
    """

    @staticmethod
    def get_running_antigravity_processes() -> List[Dict[str, Any]]:
        """
        Finds all active Antigravity and Antigravity IDE processes via tasklist on Windows.
        """
        procs = []
        if sys.platform == "win32":
            try:
                # Run tasklist with csv output
                cmd = ["tasklist", "/FO", "CSV", "/NH"]
                output = subprocess.check_output(cmd, creationflags=0x08000000, text=True, errors="ignore")
                for line in output.splitlines():
                    parts = [p.strip('"') for p in line.split('","')]
                    if len(parts) >= 2:
                        name = parts[0].lower()
                        pid_str = parts[1]
                        if "antigravity" in name:
                            try:
                                pid = int(pid_str)
                                procs.append({
                                    "pid": pid,
                                    "name": parts[0],
                                    "exe": parts[0],
                                    "cmdline": [parts[0]]
                                })
                            except ValueError:
                                continue
            except Exception:
                pass
        return procs

    @classmethod
    def sweep_orphan_language_servers(cls):
        """
        Kills lingering language_server processes belonging to Antigravity on Windows.
        """
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "language_server.exe"],
                    creationflags=0x08000000,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

    @classmethod
    def sanitize_restart_args(cls, args: List[str]) -> List[str]:
        """
        Filters out internal engine arguments so relaunches start clean.
        """
        clean = []
        for a in args:
            lower = a.lower().strip()
            if not lower:
                continue
            if any(lower.startswith(prefix) for prefix in ['--standalone', '--override_ide_name', '--subclient_type']):
                continue
            if 'language_server' in lower:
                continue
            clean.append(a)
        return clean

    @classmethod
    def restart_antigravity(cls) -> Tuple[bool, str]:
        """
        Safely terminates existing instances, sweeps orphan language servers,
        and relaunches the IDE cleanly.
        """
        if sys.platform == "win32":
            try:
                # Terminate running instances
                subprocess.run(
                    ["taskkill", "/F", "/T", "/IM", "Antigravity.exe"],
                    creationflags=0x08000000,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                subprocess.run(
                    ["taskkill", "/F", "/T", "/IM", "Antigravity IDE.exe"],
                    creationflags=0x08000000,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

        cls.sweep_orphan_language_servers()

        # Search candidates
        appdata = os.environ.get('APPDATA', '')
        localappdata = os.environ.get('LOCALAPPDATA', '')
        candidates = [
            os.path.join(localappdata, 'Programs', 'Antigravity', 'Antigravity.exe'),
            os.path.join(localappdata, 'Programs', 'Antigravity IDE', 'Antigravity IDE.exe'),
            os.path.join(appdata, '..', 'Local', 'Programs', 'Antigravity', 'Antigravity.exe')
        ]
        for c in candidates:
            if os.path.exists(c):
                subprocess.Popen([c], creationflags=0x08000000 if sys.platform == "win32" else 0)
                return True, f"Relaunched Antigravity from candidate: {c}"

        return False, "Antigravity closed, but executable was not found for restart."
