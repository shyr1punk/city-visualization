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
    inception_dates = {
        year(value(row, "inception"))
        for row in rows
        if value(row, "precision").isdigit()
        and int(value(row, "precision")) >= 9
        and year(value(row, "inception")) is not None
    }
    mention_dates = {
        year(value(row, "mention"))
        for row in rows
        if value(row, "mentionPrecision").isdigit()
        and int(value(row, "mentionPrecision")) >= 9
        and year(value(row, "mention")) is not None
    }
    inception_dates.discard(None)
    mention_dates.discard(None)
    founded = min(inception_dates) if inception_dates else None
    date_kind = "inception"
    date_source = f"https://www.wikidata.org/wiki/{qid}#P571"
    if founded is None and mention_dates:
        founded = min(mention_dates)
        date_kind = "first-mention"
        date_source = f"https://www.wikidata.org/wiki/{qid}#P1249"
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
    if founded is None:
        founded = min(populations)
        date_kind = "first-observation"
        date_source = populations[founded]["source"]
        date_label = f"не позднее {founded} года — первое наблюдение населения"
        date_note = (
            "Дата основания или первого упоминания в Wikidata не указана; "
            "на карте город появляется с первого датированного наблюдения населения."
        )
    else:
        date_label = str(founded)
        date_note = "Запись добавлена из воспроизводимого снимка Wikidata для городов бывшего СССР."
    added.append(
        {
            "id": "city-" + hashlib.sha1(qid.encode()).hexdigest()[:10],
            "name": name,
            "region": regions[0] if regions else country,
            "country": country,
            "coordinates": coordinates,
            "coordinateSource": f"https://www.wikidata.org/wiki/{qid}#P625",
            "founded": founded,
            "dateLabel": date_label,
            "dateKind": date_kind,
            "dateSource": date_source,
            "statusYear": "",
            "formerNames": "",
            "url": source_url,
            "population": [populations[key] for key in sorted(populations)],
            "notes": [date_note],
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
