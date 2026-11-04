# -*- coding: utf-8 -*-
# boot.py — выполняется при каждом включении платы (до main.py)
#
#  1) убираем отладочные сообщения SDK;
#  2) поднимаем свою Wi-Fi сеть (точка доступа);
#  3) запускаем WebREPL — чтобы код можно было загружать по Wi-Fi.
#
# Управление светом при этом НЕ зависит от Wi-Fi-роутера:
# плата сама раздаёт сеть, роутер не нужен.

import esp

esp.osdebug(None)

import gc
import time
import network

import config

# --- своя точка доступа -------------------------------------
ap = network.WLAN(network.WLAN.IF_AP)
ap.active(True)
ap.config(
    ssid=config.AP_SSID.encode(),
    security=network.AUTH_WPA_WPA2_PSK,
    key=config.AP_PASSWORD.encode(),
)
time.sleep_ms(300)  # даём интерфейсу подняться

# Клиентский режим (STA) не нужен — экономим память.
# Важно: выключаем его ТОЛЬКО ПОСЛЕ того, как AP уже поднят: иначе режим
# мелькнёт в NULL_MODE и радиомодуль уйдёт в сон до конца загрузки.
sta = network.WLAN(network.WLAN.IF_STA)
if sta.active():
    sta.active(False)

# --- WebREPL: загрузка/правка кода по Wi-Fi -----------------
# Подключение: ws://192.168.4.1:8266 (пароль — WEBREPL_PASSWORD в config.py)
try:
    import webrepl

    webrepl.start(password=config.WEBREPL_PASSWORD, port=config.WEBREPL_PORT)
except Exception as err:
    print("WebREPL не запустился:", err)

gc.collect()
try:
    print("Wi-Fi сеть:", config.AP_SSID, "  IP:", ap.ifconfig()[0])
except Exception:
    pass
