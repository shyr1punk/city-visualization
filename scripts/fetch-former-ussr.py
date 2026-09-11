"""Refresh the pinned Wikidata snapshot for cities in the other former USSR states."""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

COUNTRIES = {
    "Q399": "Армения",
    "Q227": "Азербайджан",
    "Q184": "Беларусь",
    "Q191": "Эстония",
    "Q230": "Грузия",
    "Q232": "Казахстан",
    "Q813": "Кыргызстан",
    "Q211": "Латвия",
    "Q37": "Литва",
    "Q217": "Молдова",
    "Q863": "Таджикистан",
    "Q874": "Туркменистан",
    "Q212": "Украина",
    "Q265": "Узбекистан",
}

CITY_QUERY = """
SELECT ?city ?cityLabel ?coord ?admin ?adminLabel ?article
       ?inception ?precision ?mention ?mentionPrecision WHERE {{
  VALUES ?cityClass {{ wd:Q515 wd:Q7930989 }}
  ?city wdt:P17 wd:{country};
        wdt:P31/wdt:P279* ?cityClass;
        wdt:P625 ?coord.
  FILTER NOT EXISTS {{ ?city wdt:P576 ?dissolved. }}
  OPTIONAL {{ ?city wdt:P131 ?admin. }}
  OPTIONAL {{
    ?city p:P571/psv:P571 ?dateNode.
    ?dateNode wikibase:timeValue ?inception;
              wikibase:timePrecision ?precision.
  }}
  OPTIONAL {{
    ?city p:P1249/psv:P1249 ?mentionNode.
    ?mentionNode wikibase:timeValue ?mention;
                 wikibase:timePrecision ?mentionPrecision.
  }}
  OPTIONAL {{
    ?article schema:about ?city;
             schema:isPartOf <https://ru.wikipedia.org/>.
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru,en". }}
}}
"""

POPULATION_QUERY = """
SELECT ?city ?statement ?date ?population ?reference WHERE {{
  VALUES ?city {{ {cities} }}
  ?city p:P1082 ?statement.
  ?statement ps:P1082 ?population;
             pq:P585 ?date;
             wikibase:rank ?rank.
  FILTER(?rank != wikibase:DeprecatedRank)
  OPTIONAL {{ ?statement prov:wasDerivedFrom/pr:P854 ?reference. }}
}}
"""


def fetch(query: str):
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode(
        {"query": query, "format": "json"}
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CityTimeAtlas/2.0 (city history data snapshot)"},
    )
    for retry in range(5):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.load(response)["results"]["bindings"]
        except Exception:
            if retry == 4:
                raise
            time.sleep(10 * (retry + 1))


rows = []
for qid, name in COUNTRIES.items():
    result = fetch(CITY_QUERY.format(country=qid))
    city_qids = sorted({value["city"]["value"].split("/")[-1] for value in result})
    population_rows = []
    for offset in range(0, len(city_qids), 75):
        batch = " ".join("wd:" + city for city in city_qids[offset : offset + 75])
        population_rows.extend(fetch(POPULATION_QUERY.format(cities=batch)))
        time.sleep(1)
    result.extend(population_rows)
    for row in result:
        row["countryLabel"] = {"type": "literal", "value": name}
        row["country"] = {
            "type": "uri",
            "value": "http://www.wikidata.org/entity/" + qid,
        }
    rows.extend(result)
    print(name, len(result), flush=True)
    time.sleep(2)

path = Path("data/raw/wikidata-former-ussr.json")
path.write_text(
    json.dumps({"results": {"bindings": rows}}, ensure_ascii=False),
    encoding="utf-8",
)
print("Saved", len(rows), "rows to", path)
