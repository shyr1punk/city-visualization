"""Merge the pinned former-USSR Wikidata snapshot into the Russian catalog base."""
import collections
import hashlib
import json
import re
from pathlib import Path


def value(row, key):
    return row.get(key, {}).get("value", "")


def point(raw):
    numbers = re.findall(r"-?\d+(?:\.\d+)?", raw)
    return list(map(float, numbers)) if len(numbers) == 2 else None


def year(raw):
    match = re.match(r"([+-]?\d+)-", raw)
    return int(match.group(1)) if match else None


snapshot = json.loads(
    Path("data/raw/wikidata-former-ussr.json").read_text(encoding="utf-8")
)["results"]["bindings"]
base = json.loads(Path("data/catalog-base.json").read_text(encoding="utf-8"))
known_qids = set(json.loads(Path("data/raw/identities.json").read_text()).values())
grouped = collections.defaultdict(list)
for row in snapshot:
    grouped[value(row, "city").split("/")[-1]].append(row)

added = []
for qid, rows in grouped.items():
    if not qid or qid in known_qids:
        continue
    first = rows[0]
    name = value(first, "cityLabel")
    coordinates = point(value(first, "coord"))
    if not name or not coordinates:
        continue
    dates = {
        year(value(row, "inception"))
        for row in rows
        if value(row, "precision").isdigit()
        and int(value(row, "precision")) >= 9
        and year(value(row, "inception")) is not None
    }
    dates.discard(None)
    founded = min(dates) if dates else None
    country = value(first, "countryLabel")
    regions = sorted(
        {value(row, "adminLabel") for row in rows if value(row, "adminLabel")},
        key=lambda item: (len(item), item),
    )
    article = next((value(row, "article") for row in rows if value(row, "article")), "")
    populations = {}
    for row in rows:
        observed = year(value(row, "date"))
        raw_population = value(row, "population")
        if observed is None or not raw_population:
            continue
        population = round(float(raw_population))
        if observed < 1 or observed > 2026 or population <= 0:
            continue
        if founded is not None and observed < founded:
            continue
        source = value(row, "reference")
        if not source.startswith(("http://", "https://")):
            source = f"https://www.wikidata.org/wiki/{qid}#P1082"
        candidate = {
            "year": observed,
            "value": population,
            "source": source,
            "statement": value(row, "statement").split("/")[-1],
            "date": value(row, "date")[:10],
            "segment": "0",
        }
        current = populations.get(observed)
        if current is None or ("wikidata.org" in current["source"] and "wikidata.org" not in source):
            populations[observed] = candidate
    source_url = article or f"https://www.wikidata.org/wiki/{qid}"
    if not populations:
        continue
    added.append(
        {
            "id": "city-" + hashlib.sha1(qid.encode()).hexdigest()[:10],
            "name": name,
            "region": regions[0] if regions else country,
            "country": country,
            "coordinates": coordinates,
            "coordinateSource": f"https://www.wikidata.org/wiki/{qid}#P625",
            "founded": founded,
            "dateLabel": str(founded) if founded is not None else "дата неизвестна",
            "dateKind": "inception",
            "dateSource": f"https://www.wikidata.org/wiki/{qid}#P571",
            "statusYear": "",
            "formerNames": "",
            "url": source_url,
            "population": [populations[key] for key in sorted(populations)],
            "notes": [
                "Запись добавлена из воспроизводимого снимка Wikidata для городов бывшего СССР."
            ],
            "wikidata": qid,
        }
    )

for city in base:
    city["country"] = "Россия"
Path("data/catalog-base.json").write_text(
    json.dumps(base + sorted(added, key=lambda city: (city["country"], city["name"])), ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print("Added", len(added), "cities from", len({city['country'] for city in added}), "countries")
