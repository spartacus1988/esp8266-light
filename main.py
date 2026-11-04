# -*- coding: utf-8 -*-
# main.py — веб-интерфейс включения/выключения света
#
# Плата: Wemos D1 mini (ESP8266) + модуль реле, MicroPython
# Откройте в браузере:  http://192.168.4.1/
#
# Страница:   /                — состояние и кнопки
# Переключение: /?relay=on     — включить
#               /?relay=off    — выключить
# Перезагрузка: /?reset=1
# API (JSON):  /api            — состояние
#              /api?relay=on   — переключить и вернуть состояние

import gc
import socket
import time
import machine
from machine import Pin, ADC

import config

# ------------------------------------------------------- реле и светодиод
def _level(on, active_high):
    """Уровень пина: 1 — если устройство активно по ВЫСОКОМУ уровню, иначе 0.

    on          — состояние (True = включено)
    active_high — True, если устройство срабатывает от HIGH (для светодиода
                  D4 передаётся "not LED_ACTIVE_LOW", т.к. он активен по LOW)
    """
    return bool(on) == bool(active_high)


# Значение пина при ВЫКЛЮЧЕННОМ свете:
#   реле: 0, если активный уровень высокий (RELAY_ACTIVE_HIGH = True)
#   LED:  1, т.к. светодиод D4 активен по НИЗКОМУ уровню (LED_ACTIVE_LOW = True)
# Обратите внимание: _level() принимает "активен по высокому", поэтому для
# светодиода используется отрицание LED_ACTIVE_LOW.
relay = Pin(config.RELAY_PIN, Pin.OUT, value=_level(False, config.RELAY_ACTIVE_HIGH))
led = Pin(config.LED_PIN, Pin.OUT, value=_level(False, not config.LED_ACTIVE_LOW))

adc = ADC(0)
light_on = False


def set_light(on):
    """Включает/выключает реле и индикатор."""
    global light_on
    light_on = bool(on)
    relay.value(_level(light_on, config.RELAY_ACTIVE_HIGH))
    led.value(_level(light_on, not config.LED_ACTIVE_LOW))


def read_a0():
    try:
        return adc.read()
    except OSError:
        return -1


# --- автоуправление по A0 ------------------------------------
# auto_mode = True  -> реле задаётся входом A0 (см. config.py)
# auto_mode = False -> реле задаётся только кнопками на странице
auto_mode = bool(config.AUTO_CONTROL)
last_auto_ms = time.ticks_ms()


def set_auto(enabled):
    """Переключает авто-режим (без перезагрузки платы)."""
    global auto_mode
    auto_mode = bool(enabled)


def poll_auto():
    """Раз в AUTO_ADC_POLL_MS сверяет состояние реле с входом A0."""
    global last_auto_ms
    if not auto_mode:
        return
    now = time.ticks_ms()
    if time.ticks_diff(now, last_auto_ms) < config.AUTO_ADC_POLL_MS:
        return
    last_auto_ms = now
    value = read_a0()
    if value < 0:  # АЦП не отвечает — не трогаем реле
        return
    want = value > config.AUTO_ADC_THRESHOLD
    if want != light_on:
        set_light(want)


# ------------------------------------------------------- адрес платы
def _ap_ip():
    try:
        import network

        ap = network.WLAN(network.WLAN.IF_AP)
        if ap.active():
            return ap.ifconfig()[0]
    except Exception:
        pass
    return "192.168.4.1"


IP = _ap_ip()

# ------------------------------------------------------- страница
# Порядок подстановок (%s / %d) должен совпадать с render() ниже.
_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>
*{box-sizing:border-box}
body{margin:0;padding:1.2em;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:#12141a;color:#eaeef5;text-align:center}
h1{font-size:1.35em;font-weight:600;margin:.5em 0 1.1em}
.dot{width:120px;height:120px;border-radius:60px;margin:0 auto .7em;background:%s;box-shadow:0 0 50px %s}
.state{font-size:1.5em;font-weight:700;letter-spacing:.08em;margin-bottom:.5em;color:%s}
.mode{font-size:.86em;color:#8b93a3;margin-bottom:1.2em;line-height:1.5}
.mode b{color:#eaeef5}
a.btn{display:block;padding:1.05em;margin:.55em auto;max-width:360px;border-radius:14px;text-decoration:none;font-size:1.05em;font-weight:700;color:#12141a;background:#ff5c5c}
a.btn.go{background:#38d07a}
a.btn.auto{background:#4aa3ff;color:#08111f}
a.btn.warn{background:#3a3f4b;color:#eaeef5}
.meta{margin-top:1.8em;font-size:.88em;color:#8b93a3;line-height:1.8}
</style>
</head>
<body>
<h1>%s</h1>
<div class="dot"></div>
<div class="state">%s</div>
<div class="mode">%s</div>
<a class="btn%s" href="%s">%s</a>
%s
<a class="btn warn" href="/?reset=1">ПЕРЕЗАГРУЗКА ПЛАТЫ</a>
<div class="meta">
Режим: <b>%s</b><br>
Напряжение на A0: %d<br>
Реле на GPIO%d &middot; WebREPL %s:%d
</div>
</body>
</html>"""


def render():
    if light_on:
        color, glow, state = "#38d07a", "rgba(56,208,122,.45)", "ВКЛЮЧЁН"
        extra, href, btn = " go", "/?relay=off", "ВЫКЛЮЧИТЬ"
    else:
        color, glow, state = "#2c313c", "rgba(255,255,255,.06)", "ВЫКЛЮЧЕН"
        extra, href, btn = "", "/?relay=on", "ВКЛЮЧИТЬ"

    if auto_mode:
        mode_name = "АВТО (по A0)"
        mode_line = (
            "реле управляется входом <b>A0</b>: больше %d &rarr; свет включён, "
            "меньше или равно &rarr; выключен"
            % config.AUTO_ADC_THRESHOLD
        )
        auto_btn = ""
    else:
        mode_name = "РУЧНОЙ"
        mode_line = "автоуправление выключено &mdash; свет задаётся кнопками"
        auto_btn = (
            '<a class="btn auto" href="/?mode=auto">ВЕРНУТЬ АВТОУПРАВЛЕНИЕ ПО A0</a>'
        )

    return _PAGE % (
        config.DEVICE_NAME,        # <title>
        color, glow,               # индикатор
        color,                     # цвет надписи состояния
        config.DEVICE_NAME,        # <h1>
        state,                     # ВКЛЮЧЁН / ВЫКЛЮЧЕН
        mode_line,                 # строка режима
        extra, href, btn,          # кнопка
        auto_btn,                  # кнопка «АВТО» (пусто в авто-режиме)
        mode_name,                 # АВТО (по A0) / РУЧНОЙ
        read_a0(),                 # A0
        config.RELAY_PIN,          # GPIO реле
        IP,                        # IP
        config.WEBREPL_PORT,       # порт WebREPL
    )


# ------------------------------------------------------- HTTP-ответы
def _head(code, reason, ctype, length):
    return (
        "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
        "Connection: close\r\n\r\n" % (code, reason, ctype, length)
    )


def send_page(conn):
    body = render().encode("utf-8")
    conn.sendall(_head(200, "OK", "text/html; charset=utf-8", len(body)).encode("utf-8") + body)


def send_json(conn):
    body = (
        '{"relay":"%s","mode":"%s","adc":%d,"threshold":%d,"ip":"%s"}'
        % (
            "on" if light_on else "off",
            "auto" if auto_mode else "manual",
            read_a0(),
            config.AUTO_ADC_THRESHOLD,
            IP,
        )
    ).encode("utf-8")
    conn.sendall(_head(200, "OK", "application/json; charset=utf-8", len(body)).encode("utf-8") + body)


def send_empty(conn, code, reason):
    conn.sendall(
        ("HTTP/1.1 %d %s\r\nContent-Length: 0\r\nConnection: close\r\n\r\n" % (code, reason)).encode(
            "utf-8"
        )
    )


def send_redirect(conn, location="/"):
    conn.sendall(
        (
            "HTTP/1.1 303 See Other\r\nLocation: %s\r\nContent-Length: 0\r\n"
            "Connection: close\r\n\r\n" % location
        ).encode("utf-8")
    )


# ------------------------------------------------------- разбор запроса
def parse_request(data):
    """Возвращает (путь, словарь параметров)."""
    try:
        line = data.split(b"\r\n", 1)[0]
        parts = line.split(b" ")
        if len(parts) < 2:
            return "/", {}
        target = parts[1].decode("utf-8")
    except Exception:
        return "/", {}

    if "?" in target:
        path, query = target.split("?", 1)
    else:
        path, query = target, ""

    params = {}
    for kv in query.split("&"):
        if not kv:
            continue
        if "=" in kv:
            key, value = kv.split("=", 1)
        else:
            key, value = kv, ""
        params[key] = value
    return path, params


def is_on(value):
    return value.strip().lower() in ("1", "on", "true", "yes")


def parse_mode(value):
    """'auto'/'manual' (и синонимы) -> True/False; неизвестное значение -> None."""
    v = (value or "").strip().lower()
    if v in ("auto", "on", "1", "true", "yes"):
        return True
    if v in ("manual", "off", "0", "false", "no"):
        return False
    return None


# ------------------------------------------------------- обработка запроса
def handle(conn):
    conn.settimeout(3)
    data = b""
    try:
        while b"\r\n\r\n" not in data and len(data) < 4096:
            chunk = conn.recv(512)
            if not chunk:
                break
            data += chunk
    except OSError:
        pass

    if not data:
        return

    path, params = parse_request(data)

    if path == "/favicon.ico":
        send_empty(conn, 204, "No Content")
        return

    # Кнопка ВКЛ/ВЫКЛ всегда означает «ручной режим»: авто-режим
    # отключается только здесь, при простом просмотре страницы — нет.
    if path == "/api":
        if "relay" in params:
            set_auto(False)
            set_light(is_on(params["relay"]))
        elif "mode" in params:
            mode = parse_mode(params["mode"])
            if mode is not None:
                set_auto(mode)
        send_json(conn)
        return

    if path in ("/", ""):
        if "relay" in params:
            set_auto(False)
            set_light(is_on(params["relay"]))
            send_redirect(conn, "/")
            return
        if "mode" in params:
            mode = parse_mode(params["mode"])
            if mode is not None:
                set_auto(mode)
            send_redirect(conn, "/")
            return
        if "reset" in params:
            send_redirect(conn, "/")
            time.sleep_ms(300)
            machine.reset()
            return
        send_page(conn)
        return

    send_empty(conn, 404, "Not Found")


# ------------------------------------------------------- сервер
set_light(False)  # при включении свет выключен

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", config.HTTP_PORT))
srv.listen(3)
srv.settimeout(0.5)

gc.collect()
print("Управление светом: http://%s/" % IP)

while True:
    try:
        conn, _addr = srv.accept()
    except OSError:
        # таймаут — просто ждём дальше (заодно WebREPL успевает работать)
        continue

    try:
        handle(conn)
    except Exception as err:
        print("Ошибка запроса:", err)
    finally:
        try:
            conn.close()
        except OSError:
            pass
    gc.collect()
