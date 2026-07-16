# EVN ⇄ TBS direct flights fare board

Локальный сайт с ценами на прямые рейсы Ереван ⇄ Тбилиси:
Georgian Airways (A9, кэш Airtrfx) + FlyOne Armenia (3F, живой календарь IBE).

## Запуск

```sh
python3 fetch_fares.py          # обновить data.json / data.js (ключи достаёт сам)
python3 -m http.server 8642     # открыть http://localhost:8642/
```

`index.html` можно открыть и просто файлом — данные подключаются через `data.js`.

## Автообновление на маке (launchd, каждые 6 часов)

`~/Library/LaunchAgents/org.pavelz.evn-tbs-fares.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>org.pavelz.evn-tbs-fares</string>
  <key>ProgramArguments</key>
  <array><string>/usr/bin/python3</string><string>/Users/pavelz/p2p/evn-tbs-flights/fetch_fares.py</string></array>
  <key>StartInterval</key><integer>21600</integer>
  <key>StandardErrorPath</key><string>/tmp/evn-tbs-fares.err</string>
</dict></plist>
```

```sh
launchctl load ~/Library/LaunchAgents/org.pavelz.evn-tbs-fares.plist
```

## Заметки

- Ключи (em-api-key Airtrfx, COOKIE_TOKEN FlyOne) извлекаются из публичных страниц при каждом запуске — хардкода нет, ротацию переживает.
- Если один источник падает, сайт продолжает работать на втором (`errors` в data.json и плашка на странице).
- Цены A9 — «замеченные за 48 ч» тарифы, не гарантированы; FlyOne — минимальный бесбагажный тариф на дату из их системы бронирования.
