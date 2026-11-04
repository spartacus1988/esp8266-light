<#
.SYNOPSIS
  Прошивка MicroPython на Wemos D1 mini — ОДИН раз, по USB-кабелю.

.DESCRIPTION
  1. Ставит esptool (если его нет).
  2. Скачивает образ MicroPython ESP8266_GENERIC v1.29.0 (если его нет).
  3. Стирает флеш и прошивает плату.

  После прошивки код дальше загружается по Wi-Fi (см. upload.ps1), но самые
  первые файлы всё равно кладутся на плату по USB — см. README.md, «Шаг 2».

.EXAMPLE
  .\flash.ps1
  .\flash.ps1 -Port COM3
#>
param(
    [string]$Port = "",          # например COM3; пусто = автоопределение
    [string]$FirmwareUrl = "https://micropython.org/resources/firmware/ESP8266_GENERIC-20260824-v1.29.0.bin"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $here) { $here = (Get-Location).Path }

# --- Python ------------------------------------------------
$python = $null
foreach ($cand in @("python", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $python = $cand; break }
}
if (-not $python) {
    throw "Не найден Python. Установите Python 3: https://www.python.org/downloads/"
}

# --- esptool -----------------------------------------------
Write-Host ">>> Проверяю esptool ..."
$esptoolVer = (& $python -c "import esptool; print(getattr(esptool, '__version__', '?'))" | Out-String)
if ($LASTEXITCODE -ne 0 -or -not $esptoolVer.Trim()) {
    Write-Host ">>> Устанавливаю esptool ..."
    & $python -m pip install --quiet esptool
    if ($LASTEXITCODE -ne 0) {
        throw "esptool не установился. Выполните вручную: pip install esptool"
    }
    $esptoolVer = "установлен"
}
Write-Host ">>> esptool: $($esptoolVer.Trim())"

# --- образ MicroPython -------------------------------------
$bin = Join-Path $here ([System.IO.Path]::GetFileName($FirmwareUrl.Split("?")[0]))
if (-not (Test-Path $bin)) {
    Write-Host ">>> Скачиваю MicroPython ..."
    Invoke-WebRequest -Uri $FirmwareUrl -OutFile $bin -UseBasicParsing
}
Write-Host ">>> Образ: $bin"

# --- прошивка ----------------------------------------------
$common = @("--chip", "esp8266")
if ($Port) { $common += @("--port", $Port) }

Write-Host ">>> Очищаю флеш (erase_flash) ..."
& $python -m esptool @common erase_flash
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось стереть флеш. Проверьте кабель, драйверы и порт (-Port COMx)."
}

Write-Host ">>> Прошиваю MicroPython (write_flash) ..."
# esptool v5 переименовал опцию --flash_size в --flash-size и НЕ принимает
# форму "--flash_size=detect". Узнаём, какая версия стоит, по --help.
$help = ""
try {
    $help = (& $python -m esptool write_flash --help 2>&1 | Out-String)
} catch {
    $help = ""   # не страшно — просто пропустим опцию размера флеша
}
$sizeOpt = $null
if ($help -match '--flash-size') { $sizeOpt = "--flash-size=detect" }
elseif ($help -match '--flash_size') { $sizeOpt = "--flash_size=detect" }
if ($sizeOpt) { Write-Host ">>> Опция размера флеша: $sizeOpt" }

$flashArgs = @("--baud", "460800", "write_flash")
if ($sizeOpt) { $flashArgs += $sizeOpt }
$flashArgs += @("0", $bin)
& $python -m esptool @common @flashArgs
if ($LASTEXITCODE -ne 0) {
    throw "Не удалось прошить плату. Проверьте кабель, драйверы и порт (-Port COMx)."
}

Write-Host ""
Write-Host "Готово! MicroPython прошит." -ForegroundColor Green
Write-Host ""
Write-Host "Дальше (см. README.md, «Шаг 2»):"
Write-Host "  1. подключите плату по USB и загрузите на неё config.py, boot.py, main.py"
Write-Host "     (mpremote / Thonny — Вариант А, либо терминал + WebREPL — Вариант Б);"
Write-Host "  2. нажмите RESET — появится Wi-Fi сеть 'esp-light';"
Write-Host "  3. дальше код загружается только по Wi-Fi: .\upload.ps1"
