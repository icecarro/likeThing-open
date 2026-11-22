$ErrorActionPreference = "Continue"
$root = "D:\python\pythonProject\LikeThing"
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "autostart.log"
function Write-Log($m) {
  "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Add-Content -Path $log -Encoding UTF8
}

Write-Log "=== 开机启动 ==="

# 环境变量（用户级）
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "User")
foreach ($k in @("SMTP_HOST","SMTP_PORT","SMTP_USER","SMTP_PASS","SMTP_FROM")) {
  $v = [Environment]::GetEnvironmentVariable($k, "User")
  if ($v) { Set-Item "env:$k" $v }
}
if (-not $env:DEEPSEEK_API_KEY) { Write-Log "警告：没有 DEEPSEEK_API_KEY" }

# 清理旧进程
Get-NetTCPConnection -LocalPort 8799 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 启动问卷服务
Start-Process -FilePath "python" -ArgumentList "scripts\server.py", "8799" `
  -WorkingDirectory $root -WindowStyle Hidden
Write-Log "服务已启动"

# 启动隧道
$cf = Join-Path $root "bin\cloudflared.exe"
$cfLog = Join-Path $logDir "tunnel.log"
Remove-Item $cfLog -ErrorAction SilentlyContinue
Start-Process -FilePath $cf `
  -ArgumentList "tunnel", "--url", "http://127.0.0.1:8799", "--no-autoupdate" `
  -RedirectStandardError $cfLog -WindowStyle Hidden

# 等 URL
$url = $null
for ($i = 0; $i -lt 45; $i++) {
  Start-Sleep -Seconds 2
  if (Test-Path $cfLog) {
    $m = Select-String -Path $cfLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value; break }
  }
}
if (-not $url) { Write-Log "没有拿到隧道地址"; exit 1 }

Write-Log "新链接: $url"
Set-Content -Path (Join-Path $root "问卷\当前链接.txt") -Value $url -Encoding UTF8

# 生成二维码 + 发邮件
Push-Location $root
python "scripts\notify_link.py" $url 2>&1 | ForEach-Object { Write-Log $_ }
Pop-Location
Write-Log "=== 完成 ==="
