$ErrorActionPreference = "Stop"

$root = Join-Path $PSScriptRoot "web"
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, 8010)
$listener.Start()

Write-Host "CipherLane web app running on http://0.0.0.0:8010"

try {
  while ($true) {
    $client = $listener.AcceptTcpClient()

    try {
      $stream = $client.GetStream()
      $buffer = New-Object byte[] 8192
      $count = $stream.Read($buffer, 0, $buffer.Length)

      if ($count -le 0) {
        continue
      }

      $request = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $count)
      $line = ($request -split "`r?`n")[0]
      $parts = $line -split " "
      $url = if ($parts.Length -gt 1) { $parts[1] } else { "/" }
      $url = ($url -split "\?")[0]

      if ($url -eq "/") {
        $url = "/index.html"
      }

      $relative = [System.Uri]::UnescapeDataString($url.TrimStart("/")).Replace("/", [System.IO.Path]::DirectorySeparatorChar)
      $file = Join-Path $root $relative
      $resolved = $null

      if (Test-Path -LiteralPath $file -PathType Leaf) {
        $resolved = (Resolve-Path -LiteralPath $file).Path
      }

      if ($resolved -and $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        $bytes = [System.IO.File]::ReadAllBytes($resolved)
        $extension = [System.IO.Path]::GetExtension($resolved).ToLowerInvariant()
        $contentType = switch ($extension) {
          ".html" { "text/html; charset=utf-8" }
          ".js" { "application/javascript; charset=utf-8" }
          ".css" { "text/css; charset=utf-8" }
          ".svg" { "image/svg+xml" }
          ".webmanifest" { "application/manifest+json" }
          default { "application/octet-stream" }
        }
        $status = "200 OK"
      } else {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes("Not found")
        $contentType = "text/plain; charset=utf-8"
        $status = "404 Not Found"
      }

      $header = "HTTP/1.1 $status`r`nContent-Length: $($bytes.Length)`r`nContent-Type: $contentType`r`nConnection: close`r`n`r`n"
      $headerBytes = [System.Text.Encoding]::ASCII.GetBytes($header)
      $stream.Write($headerBytes, 0, $headerBytes.Length)
      $stream.Write($bytes, 0, $bytes.Length)
    } catch {
      Add-Content -Path (Join-Path $PSScriptRoot "cipherlane_8010.err.log") -Value $_.Exception.ToString()
    } finally {
      $client.Close()
    }
  }
} finally {
  $listener.Stop()
}
