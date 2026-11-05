<#
.SYNOPSIS
  Загрузка файлов прошивки на плату по Wi-Fi (WebREPL) — без USB-кабеля.

.DESCRIPTION
  СНАЧАЛА подключитесь к Wi-Fi сети платы (по умолчанию "esp-light"),
  а затем запустите этот скрипт.

  Пароль WebREPL берётся автоматически из config.py.

.EXAMPLE
  .\upload.ps1
  .\upload.ps1 -Ip 192.168.4.1
  .\upload.ps1 -Password mypass      # если пароль отличается от config.py
#>
param(
    [string]$Ip = "192.168.4.1",              # адрес платы в её собственной сети
    [string]$Password = "",                   # пусто = взять из config.py
    [string]$Cli = ""                         # путь к webrepl_cli.py (скачается сам)
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $here) { $here = (Get-Location).Path }
if (-not $Cli) { $Cli = Join-Path $here "webrepl_cli.py" }

# --- Python ------------------------------------------------
$python = $null
foreach ($cand in @("python", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $python = $cand; break }
}
if (-not $python) {
    throw "Не найден Python. Установите Python 3: https://www.python.org/downloads/"
}

# --- пароль WebREPL берём из config.py (если не задан явно) -
if (-not $Password) {
    $Password = "esp8266"
    $cfgPath = Join-Path $here "config.py"
    if (Test-Path $cfgPath) {
        $cfg = Get-Content $cfgPath -Raw
        if ($cfg -match 'WEBREPL_PASSWORD\s*=\s*["'']([^"'']+)["'']') { $Password = $Matches[1] }
    }
}

# --- клиент WebREPL (официальный, репозиторий micropython) --
if (-not (Test-Path $Cli)) {
    Write-Host ">>> Скачиваю webrepl_cli.py ..."
    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/micropython/webrepl/master/webrepl_cli.py" `
        -OutFile $Cli -UseBasicParsing
}

# --- загрузка файлов ---------------------------------------
$files = @("config.py", "boot.py", "main.py")
foreach ($f in $files) {
    $src = Join-Path $here $f
    if (-not (Test-Path $src)) { throw "Не найден файл: $src" }
    Write-Host ">>> $f  ->  ${Ip}:/$f"
    & $python $Cli -p $Password $src "${Ip}:/$f"
    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось загрузить $f. Проверьте, что вы подключены к сети платы."
    }
}

Write-Host ""
Write-Host "Все файлы загружены." -ForegroundColor Green
Write-Host "Перезагрузите плату: откройте http://${Ip}/?reset=1  или нажмите кнопку RESET."
