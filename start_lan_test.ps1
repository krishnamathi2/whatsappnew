$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$ip = Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object {
    $_.IPAddress -notlike "127.*" -and
    $_.IPAddress -notlike "169.254.*" -and
    $_.PrefixOrigin -ne "WellKnown"
  } |
  Select-Object -First 1 -ExpandProperty IPAddress

if (-not $ip) {
  $ip = "YOUR-PC-LAN-IP"
}

Write-Host ""
Write-Host "CipherLane LAN test"
Write-Host "Web app:   http://$ip`:8010"
Write-Host "Relay URL: ws://$ip`:8765"
Write-Host ""
Write-Host "Keep the two server windows open while testing."
Write-Host ""

Start-Process -FilePath "powershell.exe" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-NoExit",
  "-File",
  (Join-Path $root "serve_cipherlane_8010.ps1")
) -WorkingDirectory $root

Start-Process -FilePath "powershell.exe" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-NoExit",
  "-File",
  (Join-Path $root "ws_relay_8765.ps1")
) -WorkingDirectory $root
