#!/bin/sh
# Загрузка файлов прошивки на плату по Wi-Fi (WebREPL) — без USB-кабеля.
# Вместо ampy по UART (так было в оригинальном репозитории).
#
# СНАЧАЛА подключитесь к Wi-Fi сети платы (по умолчанию "esp-light"), затем:
#   ./copy_to_esp.sh                 # адрес 192.168.4.1, пароль из config.py
#   ./copy_to_esp.sh 192.168.4.1     # свой адрес
#   ./copy_to_esp.sh 192.168.4.1 mypass   # свой адрес и пароль
set -e

DIR=$(cd "$(dirname "$0")" && pwd)
IP="${1:-192.168.4.1}"
PASS="${2:-}"
CLI="$DIR/webrepl_cli.py"

# пароль WebREPL по умолчанию берём из config.py
if [ -z "$PASS" ]; then
	PASS=$(sed -n 's/^WEBREPL_PASSWORD[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$DIR/config.py")
	PASS="${PASS:-esp8266}"
fi

# клиент WebREPL (официальный, репозиторий micropython/webrepl)
if [ ! -f "$CLI" ]; then
	echo ">>> Скачиваю webrepl_cli.py ..."
	curl -fsSL -o "$CLI" https://raw.githubusercontent.com/micropython/webrepl/master/webrepl_cli.py
fi

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python

for f in config.py boot.py main.py; do
	echo ">>> $f -> $IP:/$f"
	"$PY" "$CLI" -p "$PASS" "$DIR/$f" "$IP:/$f"
done

echo "Готово. Перезагрузите плату: откройте http://$IP/?reset=1 или нажмите кнопку RESET."
