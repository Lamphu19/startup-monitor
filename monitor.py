import re
from datetime import datetime
from html import escape
from pathlib import Path
from playwright.sync_api import sync_playwright

SOURCES = {
    'Sowefund': 'https://sowefund.com/investir',
    'WiSEED': 'https://www.wiseed.com/projets/crowdfunding?statuts=EN_FINANCEMENT',
    'Lita': 'https://fr.lita.co/fr/opportunities',
    'Tudigo': 'https://app.tudigo.com/les-opportunites-d-investissement',
    'Crowdcube': 'https://www.crowdcube.eu/fr-fr',
}


def lines(text):
    return [' '.join(x.split()) for x in text.splitlines() if ' '.join(x.split())]


def classify(block):
    text = ' | '.join(block).upper()
    status, reduction, envelope = [], [], []
    for tag in ('JEIR', 'JEII', 'JEIC'):
        if re.search(rf'\b{tag}\b', text): status.append(tag)
    if re.search(r'\bJEI\b', text): status.append('JEI')
    if 'IR-PME' in text or 'IR PME' in text: reduction.append('IR-PME')
    for rate in re.findall(r'(?:IR|REDUCTION IR|RÉDUCTION IR)\s*(\d{1,2})\s*%', text):
        reduction.append(f'Réduction IR {rate}%')
    if 'IR 2026' in text: reduction.append('IR 2026')
    if 'PEA-PME' in text: envelope.append('PEA-PME')
    elif re.search(r'\bPEA\b', text): envelope.append('PEA')
    if '150 0 B TER' in text or '150-0 B TER' in text: envelope.append('150-0 B ter')
    if 'APPORT-CESSION' in text or 'APPORT CESSION' in text: envelope.append('Apport-cession')
    return list(dict.fromkeys(status)), list(dict.fromkeys(reduction)), list(dict.fromkeys(envelope))


def item(platform, title, description, state, amount, product, block):
    status, reduction, envelope = classify(block)
    return dict(platform=platform, title=title, description=description, state=state,
                amount=amount, product=product, status=status, reduction=reduction,
                envelope=envelope, url=SOURCES[platform])


def parse_sowefund(text):
    data, out, i = lines(text), [], 0
    pct = re.compile(r'^\d{1,3}%$')
    money = re.compile(r'^[\d\s\u202f]+(?:,\d{2})?\s*€$')
    while i + 5 < len(data):
        if not pct.match(data[i]): i += 1; continue
        progress, sector, stage, amount, state, desc = data[i:i+6]
        if stage not in {'Seed','SerieA','PreSerieA'} or not money.match(amount) or state != 'Campagne en cours':
            i += 1; continue
        j = i + 6
        while j < len(data) and not pct.match(data[j]) and not data[j].startswith('+150 sociétés'): j += 1
        block = data[i:j]
        title = desc.split(':', 1)[0] if ':' in desc and len(desc.split(':',1)[0]) < 50 else sector
        out.append(item('Sowefund', title, desc, state, amount, f'{stage} - {progress}', block))
        i = j
    return out


def parse_wiseed(text):
    data, out = lines(text), []
    starts = [i for i,x in enumerate(data) if x in {'Collecte en cours','Clôture en cours'}]
    for pos, i in enumerate(starts):
        block = data[i:starts[pos+1] if pos+1 < len(starts) else len(data)]
        if len(block) < 3: continue
        ai = next((k for k,x in enumerate(block) if re.match(r'^€[\d,.\s]+$', x)), None)
        amount = block[ai] if ai is not None else 'Non détecté'
        desc = ' '.join(block[2:ai if ai is not None else min(len(block),8)])
        out.append(item('WiSEED', block[1], desc, block[0], amount, 'À vérifier', block))
    return out


def parse_lita(text):
    data, out = lines(text), []
    marks = {'clôture imminente','en collecte','bientôt ouverte','ouverture imminente','nouveauté'}
    starts = [i for i,x in enumerate(data) if x.lower() in marks or re.match(r'^plus que \d+ jours?$', x.lower())]
    for pos, i in enumerate(starts):
        block = data[i:starts[pos+1] if pos+1 < len(starts) else min(len(data),i+30)]
        if len(block) < 3: continue
        product = next((x for x in block if x.lower() in {'actions','action','obligations','obligation','dette privée'}), 'À vérifier')
        desc = next((x for x in block[2:] if len(x) > 45), ' '.join(block[2:8]))
        out.append(item('Lita', block[1], desc, block[0], 'Non détecté', product, block))
    return dedupe(out)


def parse_tudigo(text):
    data, out = lines(text), []
    for i,x in enumerate(data):
        if x.lower() != 'collecte en cours': continue
        block = data[i:min(len(data),i+30)]
        title = next((v for v in block[1:9] if v not in {'Populaire','B2B','SaaS','Services','Food','Health','Real estate'}), 'Opportunité Tudigo')
        pi = next((k for k,v in enumerate(block) if v.lower() == 'produit financier'), None)
        product = block[pi+1] if pi is not None and pi+1 < len(block) else 'À vérifier'
        ticket_i = next((k for k,v in enumerate(block) if 'ticket minimum' in v.lower()), None)
        ticket = block[ticket_i + 1] if ticket_i is not None and ticket_i + 1 < len(block) else 'Non détecté'
        desc = next((v for v in block if len(v) > 50), ' '.join(block[1:8]))
        out.append(item('Tudigo', title, desc, 'Collecte en cours', ticket, product, block))
    return dedupe(out)


def parse_crowdcube(text):
    data, out = lines(text), []
    start = next((i for i,x in enumerate(data) if "opportunités d'investissement" in x.lower()), None)
    if start is None: return out
    block = data[start:start+180]
    money = re.compile(r'\d[\d\s,.]*\s*(?:€|£|\$US)')
    for i in range(len(block)-1):
        if 2 <= len(block[i]) <= 70 and money.search(block[i+1]) and not money.search(block[i]):
            out.append(item('Crowdcube', block[i], block[i+1], 'Marché secondaire affiché', block[i+1], 'Action secondaire', block[i:i+2]))
    return dedupe(out)[:30]


def dedupe(items):
    out, seen = [], set()
    for x in items:
        key = (x['platform'], x['title'].lower())
        if key not in seen: seen.add(key); out.append(x)
    return out


def fetch(browser, platform, url):
    slug = platform.lower()
    page = browser.new_page(viewport={'width':1440,'height':1600}, locale='fr-FR')
    page.goto(url, wait_until='domcontentloaded', timeout=90000)
    page.wait_for_timeout(8000)
    text = page.locator('body').inner_text()
    page.screenshot(path=f'{slug}-page.png', full_page=True)
    Path(f'{slug}-texte.txt').write_text(text, encoding='utf-8')
    page.close()
    return text


def badges(values, css, fallback='À vérifier'):
    if not values: return f'<span class="badge unknown">{fallback}</span>'
    return ''.join(f'<span class="badge {css}">{escape(v)}</span>' for v in values)


def filter_tokens(campaign):
    mapping = {
        'JEI': 'status-jei', 'JEIC': 'status-jeic', 'JEIR': 'status-jeir', 'JEII': 'status-jeii',
        'IR-PME': 'reduction-ir-pme', 'IR 2026': 'reduction-ir-2026',
        'PEA': 'envelope-pea', 'PEA-PME': 'envelope-pea-pme',
        '150-0 B ter': 'envelope-150', 'Apport-cession': 'envelope-apport',
    }
    result = []
    for value in campaign['status'] + campaign['reduction'] + campaign['envelope']:
        if value in mapping:
            result.append(mapping[value])
        if value.startswith('Réduction IR '):
            result.append('reduction-ir-rate')
    if not campaign['status']: result.append('status-unknown')
    if not campaign['reduction']: result.append('reduction-unknown')
    if not campaign['envelope']: result.append('envelope-unknown')
    return ' '.join(dict.fromkeys(result))


def create_report(items):
    sections = []
    for platform in SOURCES:
        cards = []
        platform_items = [value for value in items if value['platform'] == platform]
        for campaign in platform_items:
            cards.append(f'''<article class="card" data-filters="{filter_tokens(campaign)}">
<h3>{escape(campaign['title'])}</h3><p>{escape(campaign['description'])}</p>
<div class="cats">
<div><small>Statut de l'entreprise</small>{badges(campaign['status'],'status')}</div>
<div><small>Réduction d'impôt</small>{badges(campaign['reduction'],'reduction')}</div>
<div><small>Enveloppe / mécanisme</small>{badges(campaign['envelope'],'envelope')}</div>
</div>
<p><b>Type :</b> {escape(campaign['product'])} | <b>Statut :</b> {escape(campaign['state'])} | <b>Montant/ticket :</b> {escape(campaign['amount'])}</p>
<a href="{escape(campaign['url'])}" target="_blank" rel="noopener">Voir sur {platform}</a>
</article>''')
        content = ''.join(cards) or '<p>Aucun projet public détecté.</p>'
        sections.append(f'<section><h2>{platform} ({len(cards)})</h2>{content}</section>')

    now = datetime.now().strftime('%d/%m/%Y à %H:%M')
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Veille des investissements innovants</title><style>
body{{margin:0;background:#f3f6f9;font:15px Arial;color:#17202a}}main{{max-width:1050px;margin:auto;padding:28px}}
header{{background:#053f52;color:white;padding:26px;border-radius:14px}}.panel,.card{{background:white;border-radius:10px;padding:20px;margin:18px 0;box-shadow:0 3px 12px #0001}}.card{{border-left:5px solid #00af8a}}
h2,h3{{color:#053f52}}.group{{margin:12px 0}}.group strong{{display:block;margin-bottom:6px}}
button{{padding:8px 12px;margin:3px;border:1px solid #b8c7d1;border-radius:18px;background:white;cursor:pointer}}button.active{{background:#087f5b;color:white;border-color:#087f5b}}
.cats{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.cats>div{{background:#f5f8fa;padding:10px;border-radius:8px}}small{{display:block}}
.badge{{display:inline-block;padding:6px 9px;margin:4px;border-radius:14px;font-size:12px;font-weight:bold}}.status{{background:#315b7d;color:white}}.reduction{{background:#087f5b;color:white}}.envelope{{background:#e4ebf5}}.unknown{{background:#fff3cd}}
.hidden{{display:none}}#count{{font-weight:bold;color:#49616d}}@media(max-width:700px){{.cats{{grid-template-columns:1fr}}}}</style></head><body><main>
<header><h1>Veille des investissements innovants</h1><p>{now} - {len(items)} dossier(s) sur 5 plateformes</p></header>
<div class="panel">
<div class="group"><strong>Statut de l'entreprise</strong><button data-filter="status-jeir">JEIR</button><button data-filter="status-jeii">JEII</button><button data-filter="status-jeic">JEIC</button><button data-filter="status-jei">JEI</button><button data-filter="status-unknown">À vérifier</button></div>
<div class="group"><strong>Réduction d'impôt</strong><button data-filter="reduction-ir-pme">IR-PME</button><button data-filter="reduction-ir-2026">IR 2026</button><button data-filter="reduction-ir-rate">Taux IR publié</button><button data-filter="reduction-unknown">À vérifier</button></div>
<div class="group"><strong>Enveloppe / mécanisme</strong><button data-filter="envelope-pea">PEA</button><button data-filter="envelope-pea-pme">PEA-PME</button><button data-filter="envelope-150">150-0 B ter</button><button data-filter="envelope-apport">Apport-cession</button><button data-filter="envelope-unknown">À vérifier</button></div>
<button id="reset" class="active">Tous les dossiers</button><p id="count"></p></div>
{''.join(sections)}<footer>Vérifier la documentation fiscale et le type de titre avant toute souscription.</footer></main>
<script>
const buttons=document.querySelectorAll('button[data-filter]'),cards=document.querySelectorAll('.card'),active=new Set(),count=document.getElementById('count'),reset=document.getElementById('reset');
function applyFilters(){{let visible=0;cards.forEach(card=>{{const tags=card.dataset.filters.split(' ').filter(Boolean);const show=[...active].every(filter=>tags.includes(filter));card.style.display=show?'block':'none';if(show)visible++;}});document.querySelectorAll('section').forEach(section=>{{const anyVisible=[...section.querySelectorAll('.card')].some(card=>card.style.display!=='none');section.classList.toggle('hidden',!anyVisible);}});count.textContent=visible+' dossier(s) affiché(s)';reset.classList.toggle('active',active.size===0);}}
buttons.forEach(button=>button.addEventListener('click',()=>{{const filter=button.dataset.filter;if(active.has(filter))active.delete(filter);else active.add(filter);button.classList.toggle('active');applyFilters();}}));
reset.addEventListener('click',()=>{{active.clear();buttons.forEach(button=>button.classList.remove('active'));applyFilters();}});applyFilters();
</script></body></html>'''


def main():
    parsers = {'Sowefund':parse_sowefund,'WiSEED':parse_wiseed,'Lita':parse_lita,'Tudigo':parse_tudigo,'Crowdcube':parse_crowdcube}
    items = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for platform, url in SOURCES.items():
            try:
                found = parsers[platform](fetch(browser, platform, url))
                items.extend(found)
                print(f'{platform}: {len(found)} projet(s)')
            except Exception as error:
                print(f'ERREUR {platform}: {error}')
        browser.close()
    Path('report.html').write_text(create_report(items), encoding='utf-8')
    print(f'TOTAL: {len(items)} projet(s)')


if __name__ == '__main__':
    main()
