$ErrorActionPreference = "Stop"

$clients = @{}
$connections = New-Object System.Collections.ArrayList
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, 8765)
$listener.Start()

function Get-AcceptKey($key) {
  $sha1 = [System.Security.Cryptography.SHA1]::Create()
  $bytes = [System.Text.Encoding]::ASCII.GetBytes($key.Trim() + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
  [Convert]::ToBase64String($sha1.ComputeHash($bytes))
}

function Send-Frame($client, $text) {
  if (-not $client.Connected) {
    return
  }

  $stream = $client.GetStream()
  $payload = [System.Text.Encoding]::UTF8.GetBytes($text)
  $header = New-Object System.Collections.Generic.List[byte]
  $header.Add(0x81)

  if ($payload.Length -lt 126) {
    $header.Add([byte]$payload.Length)
  } elseif ($payload.Length -le 65535) {
    $header.Add(126)
    $header.Add([byte](($payload.Length -shr 8) -band 255))
    $header.Add([byte]($payload.Length -band 255))
  } else {
    throw "Payload too large"
  }

  $bytes = $header.ToArray() + $payload
  $stream.Write($bytes, 0, $bytes.Length)
}

function Receive-Frame($client) {
  $stream = $client.GetStream()
  if (-not $stream.DataAvailable) {
    return $null
  }

  $b1 = $stream.ReadByte()
  if ($b1 -lt 0) {
    return $null
  }

  $b2 = $stream.ReadByte()
  if ($b2 -lt 0) {
    return $null
  }

  $opcode = $b1 -band 0x0f
  if ($opcode -eq 8) {
    return "__CLOSE__"
  }

  $masked = ($b2 -band 0x80) -ne 0
  $length = $b2 -band 0x7f
  if ($length -eq 126) {
    $extended = New-Object byte[] 2
    [void]$stream.Read($extended, 0, 2)
    $length = ($extended[0] -shl 8) + $extended[1]
  } elseif ($length -eq 127) {
    throw "Large websocket frames are not supported"
  }

  $mask = New-Object byte[] 4
  if ($masked) {
    [void]$stream.Read($mask, 0, 4)
  }

  $payload = New-Object byte[] $length
  $offset = 0
  while ($offset -lt $length) {
    $read = $stream.Read($payload, $offset, $length - $offset)
    if ($read -le 0) {
      break
    }
    $offset += $read
  }

  if ($masked) {
    for ($i = 0; $i -lt $payload.Length; $i++) {
      $payload[$i] = $payload[$i] -bxor $mask[$i % 4]
    }
  }

  [System.Text.Encoding]::UTF8.GetString($payload)
}

function Send-Error($connection, $message) {
  Send-Frame $connection.Client (@{ type = "error"; message = $message } | ConvertTo-Json -Compress)
}

function Remove-Connection($connection) {
  if ($connection.Id -and $clients.ContainsKey($connection.Id)) {
    $clients.Remove($connection.Id)
  }
  [void]$connections.Remove($connection)
  try { $connection.Client.Close() } catch {}
}

Write-Host "PowerShell relay running on ws://0.0.0.0:8765"

while ($true) {
  while ($listener.Pending()) {
    $client = $listener.AcceptTcpClient()
    $stream = $client.GetStream()
    $buffer = New-Object byte[] 8192
    $count = $stream.Read($buffer, 0, $buffer.Length)
    $request = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $count)
    $keyLine = ($request -split "`r?`n" | Where-Object { $_ -match "^Sec-WebSocket-Key:" } | Select-Object -First 1)

    if (-not $keyLine) {
      $client.Close()
      continue
    }

    $key = ($keyLine -split ":", 2)[1].Trim()
    $accept = Get-AcceptKey $key
    $response = "HTTP/1.1 101 Switching Protocols`r`nUpgrade: websocket`r`nConnection: Upgrade`r`nSec-WebSocket-Accept: $accept`r`n`r`n"
    $responseBytes = [System.Text.Encoding]::ASCII.GetBytes($response)
    $stream.Write($responseBytes, 0, $responseBytes.Length)
    [void]$connections.Add([pscustomobject]@{ Client = $client; Id = $null })
  }

  foreach ($connection in @($connections)) {
    try {
      if (-not $connection.Client.Connected) {
        Remove-Connection $connection
        continue
      }

      $raw = Receive-Frame $connection.Client
      if (-not $raw) {
        continue
      }
      if ($raw -eq "__CLOSE__") {
        Remove-Connection $connection
        continue
      }

      $data = $raw | ConvertFrom-Json
      if ($data.client_id) {
        $id = [string]$data.client_id
        if ([string]::IsNullOrWhiteSpace($id)) {
          Send-Error $connection "Invalid client_id"
          continue
        }
        if ($clients.ContainsKey($id) -and $clients[$id] -ne $connection) {
          Remove-Connection $clients[$id]
        }
        $connection.Id = $id
        $clients[$id] = $connection
        Send-Frame $connection.Client (@{ type = "connected"; message = "Welcome" } | ConvertTo-Json -Compress)
        continue
      }

      if (-not $connection.Id) {
        Send-Error $connection "Register client_id before sending messages"
        continue
      }

      if ($data.from -and [string]$data.from -ne $connection.Id) {
        Send-Error $connection "Sender does not match registered client"
        continue
      }

      $target = [string]$data.to
      if ($target -and $clients.ContainsKey($target)) {
        Send-Frame $clients[$target].Client $raw
      } elseif ($target) {
        Send-Error $connection "Target not online"
      } else {
        Send-Error $connection "Missing target"
      }
    } catch {
      Add-Content -Path (Join-Path $PSScriptRoot "ws_relay_8765.err.log") -Value $_.Exception.ToString()
      Remove-Connection $connection
    }
  }

  Start-Sleep -Milliseconds 30
}
