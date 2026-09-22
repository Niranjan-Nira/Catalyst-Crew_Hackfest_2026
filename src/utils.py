from pathlib import Path
from typing import Union

def resolve_diagnostic_dir(raw_path: Union[str, Path]) -> Path:
    """
    Intelligently resolves any user-pasted path to the directory containing
    the diagnostic folders (01_Timeline_And_Resources through 17_StatusReport).
    Handles:
    - Surrounding quotes and whitespace (e.g. "C:\\Path..." or 'C:\\Path...')
    - Relative and absolute paths
    - Direct 17-module folders
    - Nested 17-module folders (e.g. Device 4/Collection_... or Device 2/Device 2)
    """
    if isinstance(raw_path, str):
        clean = raw_path.strip(' "\'')
        p = Path(clean)
    else:
        p = Path(raw_path)

    if not p.is_absolute():
        p = p.resolve()

    if not p.exists():
        return p

    indicators = [
        "01_Timeline_And_Resources",
        "_StatusReport",
        "15_CrashDumps_WER",
        "02_EventLogs",
        "04_HardwareDevices",
        "06_Memory",
        "14_InstalledApps",
        "EventLogs",
        "Hardware",
        "InstalledApps"
    ]

    # 1. Direct check
    if any((p / ind).exists() for ind in indicators):
        return p

    # 2. Check 1 level down
    try:
        for sub in p.iterdir():
            if sub.is_dir() and any((sub / ind).exists() for ind in indicators):
                return sub
    except Exception:
        pass

    # 3. Check 2 levels down
    try:
        for sub in p.iterdir():
            if sub.is_dir():
                for sub2 in sub.iterdir():
                    if sub2.is_dir() and any((sub2 / ind).exists() for ind in indicators):
                        return sub2
    except Exception:
        pass

    return p
