"""Separate settlement evidence, legal status and population visibility bounds."""
import copy
import json
import re
from pathlib import Path

OVERRIDE_PATH = Path(__file__).resolve().parents[1] / 'data/settlement-history-overrides.json'


def event(kind, start, end, source, explanation, precision=None):
    return dict(kind=kind, start=start, end=end, source=source, explanation=explanation,
                precision=precision or ('year' if start == end else 'interval'))


def structured_evidence(rows, q):
    def v(row, key): return row.get(key, {}).get('value', '')
    result = []
    for field, precision, kind, prop in [('mention', 'mentionPrecision', 'settlement-mention', 'P1249'), ('inception', 'precision', 'unclassified-inception', 'P571')]:
        candidates = []
        for row in rows:
            match = re.match(r'^\+?(\d+)-', v(row, field))
            if not match or not v(row, precision).isdigit(): continue
            y = int(match[1]); p = int(v(row, precision))
            if y < 1 or p < 7: continue
            if p >= 9: start = end = y
            else:
                span = 10 if p == 8 else 100
                start = (y // span) * span
                if p == 7: start = ((y - 1) // 100) * 100 + 1
                end = start + span - 1
            candidates.append(event(kind, start, end, f'https://www.wikidata.org/wiki/{q}#{prop}',
                'Первое упоминание в Wikidata.' if prop == 'P1249' else 'Начало существования в Wikidata: тип события не подтверждён; не используется как основание поселения.', 'year' if p >= 9 else ('decade' if p == 8 else 'century')))
        unique = {(c['start'], c['end']): c for c in candidates}
        if kind == 'settlement-mention' and len(unique) > 1:
            for c in unique.values():
                c['kind'] = 'uncertain'; c['explanation'] = 'Противоречивые даты первого упоминания; требуется проверка.'
        result.extend(unique.values())
    return result


def apply_history(city, overrides):
    c = city
    evidence = copy.deepcopy(c.get('historyEvents', []))
    original = c.get('originalDate') or {k: c.get(k) for k in ['founded', 'dateKind', 'dateLabel', 'dateSource', 'statusYear']}
    c['originalDate'] = original
    settlement = None
    status = None
    if original['founded'] is not None and original['dateKind'] in {'foundation', 'foundation-or-mention', 'first-mention'}:
        settlement = event('settlement-foundation' if original['dateKind'] == 'foundation' else 'settlement-mention', original['founded'], original['founded'], original.get('dateSource') or c['url'], original.get('dateLabel') or 'Сохранённое свидетельство прежнего каталога.')
    mentions = [e for e in evidence if e['kind'] in {'settlement-mention', 'settlement-foundation'}]
    if len(mentions) == 1 and settlement is None: settlement = mentions[0]
    elif len(mentions) == 1 and settlement and mentions[0]['end'] != settlement['end']:
        evidence.append(event('uncertain', None, mentions[0]['end'], mentions[0]['source'], 'Источник расходится с сохранённой датой; ранняя дата не выбрана автоматически.'))
    raw_status = original.get('statusYear') or ''
    if re.fullmatch(r'\d{1,4}', raw_status.strip()):
        y = int(raw_status)
        if y > 0: status = event('city-status', y, y, original.get('dateSource') or c['url'], 'Городской статус из сохранённого справочника; исходная формулировка: ' + raw_status)
    override = overrides.get(c.get('wikidata'))
    if override:
        settlement = copy.deepcopy(override['settlement'])
        status = copy.deepcopy(override['cityStatus'])
        evidence = [e for e in evidence if e.get('kind') not in {'settlement-mention', 'settlement-foundation', 'city-status'}] + copy.deepcopy(override.get('events', []))
        c['historyReview'] = {k: override[k] for k in ['reviewNote', 'statusReview', 'sources']}
    first = min(c['population'], key=lambda p: p['year']) if c['population'] else None
    population = event('population-observation', first['year'], first['year'], first['source'], 'Первое доступное датированное наблюдение населения; не основание поселения.') if first else None
    c.update(settlement=settlement, cityStatus=status, firstPopulationObservation=population)
    # Population evidence can establish an earlier conservative bound, never a foundation.
    appearance = settlement
    if population and (appearance is None or population['end'] < appearance['end']): appearance = population
    c['appearanceYear'] = appearance['end'] if appearance else None
    c['appearanceBasis'] = 'population-observation' if appearance and appearance['kind'] == 'population-observation' else ('settlement' if appearance else 'unknown')
    # founded remains a compatibility alias for appearanceYear; never label it "foundation".
    c['founded'] = c['appearanceYear']
    c['dateKind'] = 'first-observation' if c['appearanceBasis'] == 'population-observation' else (settlement['kind'] if settlement else '')
    c['dateSource'] = appearance['source'] if appearance else c.get('dateSource', c['url'])
    c['dateLabel'] = ('Известен не позднее ' + str(c['founded']) + '; начало поселения неизвестно') if c['appearanceBasis'] == 'population-observation' and settlement is None else (appearance['explanation'] if appearance else 'Дата неизвестна')
    events = evidence + [e for e in [settlement, status, population] if e]
    c['historyEvents'] = sorted({json.dumps(e, sort_keys=True, ensure_ascii=False): e for e in events}.values(), key=lambda e: (e['end'], e['kind'], e['source'], e['explanation']))
    return c
