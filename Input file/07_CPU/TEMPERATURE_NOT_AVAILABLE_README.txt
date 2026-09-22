No CPU core temperature sensor was accessible via standard Windows WMI on this machine.
This is common on enterprise laptops because the OEM (Dell/HP/Lenovo) blocks the ACPI
thermal WMI namespace or exposes it only through their own tools.

To still get temperature correlated with the 30-min timeline, install ONE of:
  - HWiNFO64 (has a free 'Shared Memory' + CSV logging mode)
  - LibreHardwareMonitor / OpenHardwareMonitor (has a WMI provider once running)
  - Vendor tool such as Dell Command | Power Manager, HP Support Assistant, Lenovo Vantage

If LibreHardwareMonitor's WMI provider is running, re-run this collector and it will
attempt to read root/LibreHardwareMonitor automatically (see 01_TimelineAndResources.ps1).
