LIVE TIMELINE CAPTURE - README
Capture window : 2026-08-19T15:09:52.5698793+05:30 to 2026-08-19T15:40:04.3210895+05:30
Sample interval: 5 seconds
Duration       : 30 minutes

Files in this folder:
- ResourceUtilization_Timeline.csv : CPU%, memory available, disk queue length, GPU%, NPU%,
  CPU temp (if sensor available), and the active/foreground window title at each sample tick.
  JOIN this to the other files on the Timestamp column to correlate "what was the user doing"
  with "what did resource usage look like".
- TopProcesses_PerSample.csv : top 5 RAM-consuming processes at each sample tick - use this to
  see which specific process was responsible for a CPU/memory spike at a given timestamp.
- ProcessStartStop_Timeline.csv : every process that appeared or disappeared during the capture
  window (app launched / app closed or crashed).
- FileOpenCloseModify_Timeline.csv : file system events (Created/Changed/Deleted/Renamed) for
  Office documents, CSVs, and PDFs under Documents/Desktop/Downloads/OneDrive, with file size
  at time of event - use this to see when an Excel/Word/PPT file was created, grew, or was saved.
- CrashHang_DuringCapture.csv : any "Application Error" / "Application Hang" event that landed
  in the Application event log DURING this exact 30-minute window (real-time correlation to
  whatever spike you see in ResourceUtilization_Timeline.csv at the same timestamp).

Known limitations (be transparent with the hackathon participant about these):
- GPU_Percent / NPU_Percent will show "N/A" if the machine's driver doesn't expose that
  performance counter set - this is normal on many enterprise GPUs/iGPUs and most NPUs.
- CPU_Temp_C requires either exposed ACPI thermal WMI (rare on enterprise laptops) or
  LibreHardwareMonitor running in the background with its WMI provider enabled. If neither
  is available it will show "N/A" - see 07_CPU\TEMPERATURE_NOT_AVAILABLE_README.txt.
- File open/close is inferred from filesystem Created/Changed/Deleted events, not a true
  OS-level "handle open" event - a "Changed" event at save-time is the reliable signal;
  "opened but not saved" won't show a Changed event, only Created for new files.
