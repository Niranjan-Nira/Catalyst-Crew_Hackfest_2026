 How to Read Report.wer Files

## A. How to read a `Report.wer` file

These live in `15_CrashDumps_WER\<crash_folder_name>\Report.wer`. They look
like garbage if you open them the normal way — here's why and how to fix it.

**Problem:** the file is plain text, but encoded in **UTF-16LE**, not UTF-8.
Most default "open file" code assumes UTF-8 and either errors or shows
garbled/spaced-out characters.

**Fix — Python:**
```python
with open(path, encoding="utf-16-le") as f:
    content = f.read()
```
**Fix — command line:**
```bash
iconv -f utf-16le -t utf-8 Report.wer
```
**Fix — PowerShell:**
```powershell
Get-Content -Path "Report.wer" -Encoding Unicode
```

**What's inside — it's a flat `Key=Value` list.** The fields that matter:

| Field | What it tells you |
|---|---|
| `EventType=` | The crash category bucket — e.g. `APPCRASH`, `AppHang`, `OFFICE_MODULE_VERSION_MISMATCH`, `LiveKernelEvent`, `CLR20r3` (.NET crash), `BEX64` (buffer/exception fault). Read this first — it tells you what *kind* of failure you're looking at before anything else. |
| `EventTime=<number>` | **The real crash time — but it's a Windows FILETIME, not Unix time or a normal date string.** Convert it (see below). Don't rely on the crash folder's file-system timestamp instead — it can drift slightly from the true event time. |
| `Sig[0].Name` / `Sig[0].Value`, `Sig[1]...`, etc. | The crash "signature" — usually app name, version, faulting module, and offset. **Two crash reports with identical `Sig` values are the same bug happening again**, not two separate problems. |
| `AppPath=` | Full path to the crashing executable — useful for identifying exactly which install/version was running. |

**Converting `EventTime` to a real date/time (Python):**
```python
from datetime import datetime, timedelta

def filetime_to_datetime(filetime_str):
    filetime = int(filetime_str)
    return datetime(1601, 1, 1) + timedelta(microseconds=filetime / 10)

# Example:
# EventTime=134305807182322575
print(filetime_to_datetime("134305807182322575"))
# -> 2026-08-07 12:51:58.232258
```

**Shortcut before diving into individual files:** the folder *name* itself
already tells you the category — `AppCrash_`, `AppHang_`, `Kernel_<stopcode>_`,
`Critical_`, `NonCritical_`. You can sort/group/filter by folder name alone
before opening a single `Report.wer`, which is much faster than opening every
file to find out what type of crash it is.

---
