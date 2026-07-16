#!/usr/bin/env python3
"""Collect direct EVN<->TBS fares from Georgian Airways (Airtrfx cache) and
FlyOne Armenia (live IBE fare calendar), write data.json + data.js for index.html.

Keys/tokens are extracted from the public pages on every run, nothing is hardcoded.
"""
import json
import re
import sys
import urllib.request
import datetime as dt

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"
OUT_DIR = __file__.rsplit("/", 1)[0]
MONTHS_AHEAD = 4


def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


# ---------- Georgian Airways (A9) via Airtrfx fare cache ----------

def fetch_a9():
    page = http("https://flights.georgian-airways.com/en/flights-from-yerevan-to-tbilisi")
    m = re.search(r'"em-api-key":"([^"]+)"', page)
    if not m:
        raise RuntimeError("em-api-key not found in Airtrfx page")
    key = m.group(1)

    def search(origin, dest):
        body = json.dumps({
            "origins": [origin], "destinations": [dest],
            "journeyType": "ONE_WAY",
            "departureDaysInterval": {"start": 0, "end": 120},
            "faresLimit": 100, "routesLimit": 1, "faresPerRoute": 100,
        }).encode()
        raw = http(
            "https://openair-california.airtrfx.com/airfare-sputnik-service/v3/a9/fares/search",
            data=body,
            headers={
                "Content-Type": "application/json",
                "em-api-key": key,
                "Origin": "https://flights.georgian-airways.com",
                "Referer": "https://flights.georgian-airways.com/",
            },
        )
        best = {}
        for f in json.loads(raw):
            p = f.get("priceSpecification") or {}
            usd = p.get("usdTotalPrice")
            date = f.get("departureDate")
            if usd is None or not date:
                continue
            if date not in best or usd < best[date]["usd"]:
                best[date] = {
                    "date": date,
                    "price": p.get("totalPrice"),
                    "currency": p.get("currencyCode"),
                    "usd": round(usd, 2),
                    "seen": (f.get("searchDate") or "")[:10],
                }
        return sorted(best.values(), key=lambda x: x["date"])

    return {"evn_tbs": search("EVN", "TBS"), "tbs_evn": search("TBS", "EVN")}


# ---------- FlyOne Armenia (3F) via live IBE fare calendar ----------

def fetch_flyone():
    page = http("https://flyone.eu/en/")
    m = re.search(r"loadCookieToken\('([^']+)'\)", page)
    if not m:
        raise RuntimeError("COOKIE_TOKEN not found on flyone.eu")
    token = m.group(1)

    def calendar(origin, dest, travel_date):
        body = json.dumps({
            "ipAddress": "", "currencyCode": "EUR",
            "searchCriteria": {
                "paxInfo": [{"paxType": 1, "paxKey": "pax1"}],
                "journeyInfo": {
                    "journeyType": 1,
                    "routeInfo": [{"depCity": origin, "arrCity": dest, "travelDate": travel_date}],
                },
            },
            "qsParams": [{"key": "", "value": ""}],
            "languageCode": "en-GB", "currency": "sting",
            "paxInfoId": 0, "reservationType": 0,
        }).encode()
        raw = http(
            "https://api4.flyone.eu/api/search/fare-calendar-schedule",
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": "Bearer " + token,
                "Origin": "https://flyone.eu",
                "Referer": "https://flyone.eu/",
            },
        )
        return json.loads(raw)

    def search(origin, dest):
        today = dt.date.today()
        probe_dates = [today.isoformat()]
        y, mo = today.year, today.month
        for _ in range(MONTHS_AHEAD - 1):
            mo += 1
            if mo > 12:
                mo, y = 1, y + 1
            probe_dates.append(f"{y}-{mo:02d}-01")

        best = {}
        for pd in probe_dates:
            res = calendar(origin, dest, pd)
            for ys in res.get("flightSchedule") or []:
                for mth in ys.get("month") or []:
                    for day in mth.get("days") or []:
                        if not day.get("isFlightAvailable") or day.get("price") == "0":
                            continue
                        date = f"{ys['year']}-{int(mth['month']):02d}-{int(day['date']):02d}"
                        price = float(day["price"])
                        if date not in best or price < best[date]["eur"]:
                            best[date] = {
                                "date": date,
                                "eur": price,
                                "soldOut": bool(day.get("isSoldOut")),
                            }
        return sorted(best.values(), key=lambda x: x["date"])

    return {"evn_tbs": search("EVN", "TBS"), "tbs_evn": search("TBS", "EVN")}


def main():
    data = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    errors = {}
    for name, fn in (("a9", fetch_a9), ("flyone", fetch_flyone)):
        try:
            data[name] = fn()
        except Exception as e:  # keep the site alive even if one source breaks
            data[name] = {"evn_tbs": [], "tbs_evn": []}
            errors[name] = str(e)
    data["errors"] = errors

    with open(f"{OUT_DIR}/data.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    with open(f"{OUT_DIR}/data.js", "w") as f:
        f.write("window.FARES_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")

    n = lambda src: sum(len(v) for v in data[src].values() if isinstance(v, list))
    print(f"updated={data['updated']} a9_dates={n('a9')} flyone_dates={n('flyone')} errors={errors or 'none'}")
    return 1 if len(errors) == 2 else 0


if __name__ == "__main__":
    sys.exit(main())
