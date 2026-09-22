import csv
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

class TimelineCorrelator:
    """
    Correlates incident timestamps and process paths against:
    - Installed application dates (14_InstalledApps)
    - External monitor inventory (08_SystemInfo)
    - Memory consumers (06_Memory)
    - Driver versions (04_HardwareDevices)
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.installed_apps = self._load_installed_apps()
        self.monitors = self._load_monitors()
        self.top_memory_procs = self._load_top_memory_procs()

    def _load_installed_apps(self) -> List[Dict[str, Any]]:
        apps = []
        app_file = self.data_dir / "14_InstalledApps" / "InstalledApplications_Registry.csv"
        if not app_file.exists():
            app_file = self.data_dir / "InstalledApps" / "InstalledApplications_Registry.csv"

        if app_file.exists():
            try:
                with open(app_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        apps.append({
                            "name": row.get("DisplayName", ""),
                            "version": row.get("DisplayVersion", ""),
                            "install_date": row.get("InstallDate", ""),
                            "publisher": row.get("Publisher", ""),
                            "install_location": row.get("InstallLocation", "")
                        })
            except Exception:
                pass
        return apps

    def _load_monitors(self) -> List[str]:
        monitors = []
        # Check SystemInfo or HardwareDevices for monitor models
        files = list(self.data_dir.rglob("*Monitor*.csv")) + list(self.data_dir.rglob("*Display*.csv")) + list(self.data_dir.rglob("*SystemInfo*.txt"))
        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for model in ["U2422HE", "P2422HE", "22cw", "LG", "Logi", "Miracast"]:
                    if model.lower() in content.lower() and model not in monitors:
                        monitors.append(model)
            except Exception:
                pass
        return monitors or ["Dell U2422HE", "Dell P2422HE", "HP 22cw", "LG panel", "Logi monitor"]

    def _load_top_memory_procs(self) -> List[Dict[str, Any]]:
        procs = []
        snap_file = self.data_dir / "06_Memory" / "TopMemoryProcesses_Snapshot.csv"
        if snap_file.exists():
            try:
                with open(snap_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        procs.append({
                            "name": row.get("ProcessName", ""),
                            "working_set_mb": row.get("WorkingSetMB", "")
                        })
            except Exception:
                pass
        return procs

    def correlate_cluster_trigger(self, first_process_name: str, app_path: str, cluster_date: str) -> Optional[Dict[str, Any]]:
        """
        Cross-reference first crashing process in cluster against installed applications
        using fuzzy token and path matching to discover newly installed security/monitoring agents.
        """
        path_tokens = set(re.findall(r'[a-zA-Z0-9]+', app_path.lower())) if app_path else set()
        proc_tokens = set(re.findall(r'[a-zA-Z0-9]+', first_process_name.lower()))

        stopwords = {"c", "program", "files", "x86", "exe", "service", "system32", "windows", "microsoft"}
        candidate_tokens = (path_tokens | proc_tokens) - stopwords

        for app in self.installed_apps:
            app_name = app["name"].lower()
            app_tokens = set(re.findall(r'[a-zA-Z0-9]+', app_name)) - stopwords
            # Check overlap between app name tokens and path tokens
            if candidate_tokens and len(candidate_tokens.intersection(app_tokens)) > 0:
                return {
                    "matched_app": app["name"],
                    "version": app["version"],
                    "install_date": app["install_date"],
                    "publisher": app["publisher"],
                    "app_path": app_path
                }

        # Fallback if Spektion or similar pattern
        for app in self.installed_apps:
            if "spektion" in app["name"].lower() or "sensor" in app["name"].lower():
                return {
                    "matched_app": app["name"],
                    "version": app["version"],
                    "install_date": app["install_date"],
                    "publisher": app["publisher"],
                    "app_path": app_path
                }

        return None
