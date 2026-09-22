# Diagnostic Cheat Sheet for Non-IT Participants

## Step 1: Translate file names into plain English

| File | Plain English | Red flag to look for |
|---|---|---|
| `_StatusReport\StatusReport.txt` | Did the data collection work? | Any "Failed" line = that data is missing, skip it |
| `09_ReliabilityMonitor\StabilityIndex_DailyScore.csv` | Daily health score, 1 (bad) to 10 (good) | A sudden drop = pinpoints WHEN trouble started |
| `01_Timeline_And_Resources\ResourceUtilization_Timeline.csv` | What the laptop was doing every 5 seconds for 30 min | CPU/Memory number spikes way up, or GPU maxed out |
| `01_Timeline_And_Resources\TopProcesses_PerSample.csv` | Which app was using the most memory at each moment | Same app repeatedly at the top during a spike |
| `01_Timeline_And_Resources\FileOpenCloseModify_Timeline.csv` | When files (Excel, Word, PDF) were opened/saved/changed | A file event exactly when a spike happened |
| `01_Timeline_And_Resources\ProcessStartStop_Timeline.csv` | Apps launching or closing during the capture | An app "closed" unexpectedly (not by the user) |
| `01_Timeline_And_Resources\CrashHang_DuringCapture.csv` | Apps that crashed/froze during the 30 min | Anything listed here at all is a strong clue |
| `16_Services_Processes\AppCrashHang_PersistentHistory.csv` | Same as above, but going back further (not just 30 min) | Same app crashing repeatedly over days = pattern |
| `04_HardwareDevices\ProblemDevices_ONLY.csv` | Hardware pieces (drivers) with issues | Anything listed here at all |
| `06_Memory\WHEA_HardwareMemoryErrors.csv` | Warning signs of failing RAM | Anything listed here at all |
| `07_CPU\CPU_ThrottlingEvents.csv` | CPU slowing itself down (overheating/power limit) | Anything listed here at all |
| `05_Disk\Drives_SizeFreeSpace.csv` | How full the hard drive is | "PercentFree" below ~10% |
| `03_WindowsUpdates\InstalledHotfixes_KB.csv` | Recent Windows updates, with dates | An update installed right before problems began |
| `10_Battery\BatteryReport.html` | Battery wear (laptops only) | Full-charge capacity much lower than design capacity |

Everything else (installed apps, network, startup apps, system info) is **background context** — only check these if the files above point you toward a suspect (e.g. "the crash coincided with a VPN reconnect" → then go check `13_AppLogs\`).

## Step 2: How the files connect to each other (the "join key" is TIME)

Every file has a timestamp. The whole method is: **find a bad moment, then look at every other file at that exact moment.**

```
StabilityIndex_DailyScore.csv
        │  "score dropped on Aug 15"
        ▼
ResourceUtilization_Timeline.csv
        │  "CPU spiked to 98% at 10:32 AM"
        ▼
TopProcesses_PerSample.csv          FileOpenCloseModify_Timeline.csv
   "EXCEL.EXE was #1 at 10:32"          "Report.xlsx was being saved at 10:32"
        │                                       │
        └───────────────┬───────────────────────┘
                         ▼
              CrashHang_DuringCapture.csv
              "Excel crashed at 10:33"
                         │
                         ▼
        AppCrashHang_PersistentHistory.csv
        "Excel has crashed 6 times this month"
                         │
                         ▼
     ProblemDevices_ONLY.csv / WHEA_Errors.csv / CPU_ThrottlingEvents.csv
     "any hardware reason this keeps happening?"
```

## Step 3: The 3-step worksheet to fill in

**1. When did it go wrong?**
_(check StabilityIndex or CrashHang or ProcessStartStop for a timestamp)_
→ Time: ___________

**2. What else was happening at that exact time?**
_(check 2-3 files above for the same timestamp)_
→ File 1 says: ___________
→ File 2 says: ___________

**3. My guess and confidence**
→ I think the cause is: ___________
→ Confidence: Low / Medium / High
→ Why: ___________
→ What I'd need to check next to be more sure: ___________

## The one prompt to give the LLM

> "Here's a CSV row/section from [filename] around [timestamp]. In simple terms, what does this show, and could it explain my laptop crashing/slowing down at that time?"

Paste only the relevant rows — not the whole file — and let the model translate the jargon.