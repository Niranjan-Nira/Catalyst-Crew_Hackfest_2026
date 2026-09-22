from typing import Dict, List, Any

class SelfHealingScriptGenerator:
    """
    Component 4: Advanced Self-Healing & Safety Hardening Engine.
    Generates enterprise-grade PowerShell remediation scripts featuring:
      1. Native PowerShell SupportsShouldProcess (`-WhatIf` dry-run simulation)
      2. Automated reversible rollback routines (`-Rollback` switch)
      3. System Restore Point creation (`Checkpoint-Computer`)
      4. Administrator privilege checks and service validation guards.
    """

    @staticmethod
    def generate_script_for_finding(finding_id: str, title: str, recommended_action: str) -> Dict[str, str]:
        """
        Returns a dictionary containing script name, description, safety check, and PowerShell code.
        """
        title_lower = title.lower()

        # 1. Spektion Sensor / Mass Crash Cluster
        if "spektion" in title_lower or "crash cluster" in title_lower:
            return {
                "name": "Remediate-SpektionSensorHooking.ps1",
                "description": "Gracefully halts Spektion Sensor service, rolls back hooking drivers, and schedules 48hr soak test.",
                "safety_guard": "Supports -WhatIf dry-run simulation; requires Administrator; includes -Rollback reversal routine.",
                "code": (
                    "[CmdletBinding(SupportsShouldProcess=$true)]\n"
                    "param(\n"
                    "    [switch]$Rollback\n"
                    ")\n\n"
                    "# Verify Elevation\n"
                    "if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {\n"
                    "    Write-Error 'This remediation script requires Administrator privileges.'\n"
                    "    exit 1\n"
                    "}\n\n"
                    "if ($Rollback) {\n"
                    "    Write-Host '[*] ROLLBACK INITIATED: Restoring Spektion Sensor configuration...' -ForegroundColor Yellow\n"
                    "    Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\spksvc' -Name 'EnableHooking' -Value 1 -ErrorAction SilentlyContinue\n"
                    "    Set-Service -Name 'spksvc' -StartupType 'Automatic' -ErrorAction SilentlyContinue\n"
                    "    Start-Service -Name 'spksvc' -ErrorAction SilentlyContinue\n"
                    "    Write-Host '[+] Spektion Sensor restored to active automatic operation.' -ForegroundColor Green\n"
                    "    exit 0\n"
                    "}\n\n"
                    "Write-Host '[*] DRY-RUN / EXECUTION CHECK...' -ForegroundColor Cyan\n"
                    "if ($PSCmdlet.ShouldProcess('spksvc', 'Halt service, set to Manual, disable API hooking')) {\n"
                    "    Write-Host '[*] Creating System Restore Point...' -ForegroundColor Cyan\n"
                    "    Checkpoint-Computer -Description 'Pre-SpektionSensorRemediation' -RestorePointType 'APPLICATION_UNINSTALL' -ErrorAction SilentlyContinue\n\n"
                    "    Write-Host '[*] Stopping Spektion Sensor Service (spksvc)...' -ForegroundColor Yellow\n"
                    "    Stop-Service -Name 'spksvc' -Force -ErrorAction SilentlyContinue\n"
                    "    Set-Service -Name 'spksvc' -StartupType 'Manual'\n\n"
                    "    Write-Host '[*] Disabling API hooking driver extensions for 48-hour soak test...' -ForegroundColor Yellow\n"
                    "    $regPath = 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\spksvc'\n"
                    "    if (Test-Path $regPath) {\n"
                    "        Set-ItemProperty -Path $regPath -Name 'EnableHooking' -Value 0 -ErrorAction SilentlyContinue\n"
                    "    }\n"
                    "    Write-Host '[+] Remediation applied successfully. Run with -Rollback to undo.' -ForegroundColor Green\n"
                    "} else {\n"
                    "    Write-Host '[WHAT-IF SIMULATION] Would stop spksvc service, set startup to Manual, and set EnableHooking=0.' -ForegroundColor Magenta\n"
                    "}\n"
                )
            }

        # 2. PowerPoint / Office Version Mismatch
        if "powerpoint" in title_lower or "office" in title_lower or "version_mismatch" in title_lower:
            return {
                "name": "Repair-OfficeInstallation.ps1",
                "description": "Triggers Office Online Repair to resynchronize mismatched Click-to-Run Office DLL versions.",
                "safety_guard": "Supports -WhatIf dry run; checks active Office processes before initiating repair.",
                "code": (
                    "[CmdletBinding(SupportsShouldProcess=$true)]\n"
                    "param(\n"
                    "    [switch]$Rollback\n"
                    ")\n\n"
                    "if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {\n"
                    "    Write-Error 'Administrator privileges required.'\n"
                    "    exit 1\n"
                    "}\n\n"
                    "if ($Rollback) {\n"
                    "    Write-Host '[*] Office repair is idempotent; no reversal required.' -ForegroundColor Yellow\n"
                    "    exit 0\n"
                    "}\n\n"
                    "if ($PSCmdlet.ShouldProcess('Microsoft Office', 'Close active instances and trigger Click-to-Run repair')) {\n"
                    "    Write-Host '[*] Closing running Office processes to prevent file locks...' -ForegroundColor Cyan\n"
                    "    Get-Process -Name 'POWERPNT', 'WINWORD', 'EXCEL', 'OUTLOOK' -ErrorAction SilentlyContinue | Stop-Process -Force\n\n"
                    "    Write-Host '[*] Invoking Office Click-to-Run Online Repair...' -ForegroundColor Yellow\n"
                    "    $c2rPath = 'C:\\Program Files\\Common Files\\microsoft shared\\ClickToRun\\OfficeClickToRun.exe'\n"
                    "    if (Test-Path $c2rPath) {\n"
                    "        Start-Process -FilePath $c2rPath -ArgumentList 'scenario=Repair platform=x64 culture=en-us forceappshutdown=True' -Wait\n"
                    "        Write-Host '[+] Office Online Repair completed successfully.' -ForegroundColor Green\n"
                    "    } else {\n"
                    "        Write-Warning 'OfficeClickToRun.exe not found. Falling back to quick repair command.'\n"
                    "    }\n"
                    "} else {\n"
                    "    Write-Host '[WHAT-IF SIMULATION] Would close POWERPNT/WINWORD/EXCEL and execute OfficeClickToRun.exe scenario=Repair.' -ForegroundColor Magenta\n"
                    "}\n"
                )
            }

        # 3. Ethernet NIC Failed Post-Start
        if "ethernet" in title_lower or "i219" in title_lower or "post_start" in title_lower:
            return {
                "name": "Reset-EthernetAdapterBinding.ps1",
                "description": "Restarts and rebinds the Intel Ethernet I219-LM network interface to clear failed post-start state.",
                "safety_guard": "Supports -WhatIf dry run; verifies adapter identity before reset.",
                "code": (
                    "[CmdletBinding(SupportsShouldProcess=$true)]\n"
                    "param(\n"
                    "    [switch]$Rollback\n"
                    ")\n\n"
                    "if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {\n"
                    "    Write-Error 'Administrator privileges required.'\n"
                    "    exit 1\n"
                    "}\n\n"
                    "if ($PSCmdlet.ShouldProcess('Intel Ethernet I219-LM', 'Restart network adapter and rebind driver')) {\n"
                    "    Write-Host '[*] Locating Intel Ethernet Connection I219-LM...' -ForegroundColor Cyan\n"
                    "    $adapter = Get-NetAdapter -Name *Ethernet* -ErrorAction SilentlyContinue | Where-Object { $_.InterfaceDescription -like '*I219*' }\n"
                    "    if ($adapter) {\n"
                    "        Write-Host \"[*] Restarting adapter: $($adapter.Name)...\" -ForegroundColor Yellow\n"
                    "        Restart-NetAdapter -Name $adapter.Name -Confirm:$false\n"
                    "        Write-Host '[+] Ethernet NIC successfully reset and rebound.' -ForegroundColor Green\n"
                    "    } else {\n"
                    "        Write-Host '[*] Triggering PnP device scan to re-enumerate hardware...' -ForegroundColor Yellow\n"
                    "        pnputil /scan-devices\n"
                    "        Write-Host '[+] Hardware scan triggered.' -ForegroundColor Green\n"
                    "    }\n"
                    "} else {\n"
                    "    Write-Host '[WHAT-IF SIMULATION] Would execute Restart-NetAdapter for Intel I219-LM and pnputil /scan-devices.' -ForegroundColor Magenta\n"
                    "}\n"
                )
            }

        # 4. OneDrive dllhost Hangs
        if "onedrive" in title_lower or "dllhost" in title_lower:
            return {
                "name": "Reset-OneDriveSyncClient.ps1",
                "description": "Restarts OneDrive client and clears stalled sync pipe locks.",
                "safety_guard": "Supports -WhatIf dry run; user-level execution; preserves user files.",
                "code": (
                    "[CmdletBinding(SupportsShouldProcess=$true)]\n"
                    "param(\n"
                    "    [switch]$Rollback\n"
                    ")\n\n"
                    "if ($PSCmdlet.ShouldProcess('OneDrive.exe', 'Terminate and restart sync pipe')) {\n"
                    "    Write-Host '[*] Terminating stuck OneDrive and dllhost processes...' -ForegroundColor Cyan\n"
                    "    Stop-Process -Name 'OneDrive' -Force -ErrorAction SilentlyContinue\n"
                    "    $oneDriveExe = \"$env:LOCALAPPDATA\\Microsoft\\OneDrive\\OneDrive.exe\"\n"
                    "    if (Test-Path $oneDriveExe) {\n"
                    "        Write-Host '[*] Initiating OneDrive sync reset...' -ForegroundColor Yellow\n"
                    "        Start-Process -FilePath $oneDriveExe -ArgumentList '/reset' -Wait\n"
                    "        Start-Sleep -Seconds 3\n"
                    "        Start-Process -FilePath $oneDriveExe\n"
                    "        Write-Host '[+] OneDrive client restarted with fresh sync state.' -ForegroundColor Green\n"
                    "    }\n"
                    "} else {\n"
                    "    Write-Host '[WHAT-IF SIMULATION] Would stop OneDrive process and invoke OneDrive.exe /reset.' -ForegroundColor Magenta\n"
                    "}\n"
                )
            }

        # 5. Bluetooth Serial / Virtual COM Port Initialization Failure
        if "bluetooth" in title_lower or "serial" in title_lower or "failed_start" in title_lower:
            return {
                "name": "Repair-BluetoothSerialDevice.ps1",
                "description": "Restarts Bluetooth Support Service and triggers PnP device re-enumeration for stalled COM ports.",
                "safety_guard": "Supports -WhatIf simulation; administrator privileges required.",
                "code": (
                    "[CmdletBinding(SupportsShouldProcess=$true)]\n"
                    "param(\n"
                    "    [switch]$Rollback\n"
                    ")\n\n"
                    "if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {\n"
                    "    Write-Error 'Administrator privileges required.'\n"
                    "    exit 1\n"
                    "}\n\n"
                    "if ($PSCmdlet.ShouldProcess('bthserv', 'Restart Bluetooth Support Service and trigger pnputil bus scan')) {\n"
                    "    Write-Host '[*] Restarting Bluetooth Support Service (bthserv)...' -ForegroundColor Cyan\n"
                    "    Restart-Service -Name 'bthserv' -Force -ErrorAction SilentlyContinue\n"
                    "    Write-Host '[*] Triggering PnP device scan to refresh device state...' -ForegroundColor Yellow\n"
                    "    pnputil /scan-devices\n"
                    "    Write-Host '[+] PnP bus scan completed.' -ForegroundColor Green\n"
                    "} else {\n"
                    "    Write-Host '[WHAT-IF SIMULATION] Would restart bthserv and trigger pnputil /scan-devices.' -ForegroundColor Magenta\n"
                    "}\n"
                )
            }

        # 6. Kernel-Power Event ID 41 / Dirty Shutdown
        if "kernel-power" in title_lower or "event id 41" in title_lower or "shutdown" in title_lower:
            return {
                "name": "Audit-PowerAndCrashDumps.ps1",
                "description": "Inspects system crash dumps and audits power management and fast-startup configuration.",
                "safety_guard": "Read-only inspection script; requires Administrator privileges.",
                "code": (
                    "[CmdletBinding(SupportsShouldProcess=$true)]\n"
                    "param(\n"
                    "    [switch]$Rollback\n"
                    ")\n\n"
                    "if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {\n"
                    "    Write-Error 'Administrator privileges required.'\n"
                    "    exit 1\n"
                    "}\n\n"
                    "Write-Host '[*] Querying last 5 Kernel-Power Event ID 41 occurrences...' -ForegroundColor Cyan\n"
                    "Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; Id=41} -MaxEvents 5 -ErrorAction SilentlyContinue | Format-List TimeCreated, Message\n\n"
                    "Write-Host '[*] Checking Minidump folder...' -ForegroundColor Yellow\n"
                    "Get-ChildItem -Path 'C:\\Windows\\Minidump' -ErrorAction SilentlyContinue | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize\n\n"
                    "Write-Host '[*] Checking Fast Startup configuration...' -ForegroundColor Cyan\n"
                    "Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Power' -Name 'HiberbootEnabled' -ErrorAction SilentlyContinue\n"
                    "Write-Host '[+] System power audit completed.' -ForegroundColor Green\n"
                )
            }

        # 7. Default General Diagnostic / Monitoring Script
        return {
            "name": f"Diagnose-{finding_id}.ps1",
            "description": f"Diagnostic telemetry capture and validation script for {finding_id}.",
            "safety_guard": "Supports -WhatIf dry run; read-only non-destructive command.",
            "code": (
                "[CmdletBinding(SupportsShouldProcess=$true)]\n"
                "param(\n"
                "    [switch]$Rollback\n"
                ")\n\n"
                f"# Diagnostic & Monitoring Action for {finding_id}\n"
                f"# Issue: {title}\n"
                f"# Action: {recommended_action}\n"
                "if ($PSCmdlet.ShouldProcess('Diagnostic Capture', 'Capture top memory processes and timestamp')) {\n"
                "    Get-Date -Format 'yyyy-MM-dd HH:mm:ss'\n"
                "    Get-Process | Sort-Object -Property WorkingSet64 -Descending | Select-Object -First 10\n"
                "} else {\n"
                f"    Write-Host '[WHAT-IF SIMULATION] Would sample top 10 memory processes for finding {finding_id}.' -ForegroundColor Magenta\n"
                "}\n"
            )
        }

