import re
from datetime import datetime
from html import escape
from playwright.sync_api import sync_playwright

SOWEFUND_URL = 'https://sowefund.com/investir'
WISEED_URL = 'https://www.wiseed.com/projets/crowdfunding?statuts=EN_FINANCEMENT'
FISCAL_WORDS = ('JEI', 'JEIR', 'JEII', 'IR PME', 'IR-PME', 'IR 2026', 'REDUCTION IR', 'RÉDUCTION IR')
STAGES = {'Seed', 'SerieA', 'PreSerieA'}


def clean_lines(text):
    return [' '.join(x.split()).strip() for x in text.splitlines() if ' '.join(x.split()).strip()]


def title_from_description(sector, description):
    upper = description.upper()
    known = {'ANYOS': 'ANYOS', 'CIRCUL': "Circul'egg", 'KEPPLAIR': 'KEPPLAIR 72', 'NOTPARK': 'Notpark',
             'GAMBAS FRANÇAISES': 'Agriloops', 'CHOCOLAT': 'Le Chocolat des Français',
             'WIND FISHER': 'Wind Fisher', 'LIMOVA': 'LIMOVA.ai'}
    for needle, title in known.items():
        if needle in upper:
            return title
    if ':' in description:
        candidate = description.split(':', 1)[0].strip()
        if 2 <= len(candidate) <= 50:
            return candidate
    return sector


def parse_sowefund(text):
    lines = clean_lines(text)
    pct = re.compile(r'^\d{1,3}%$')
    amount = re.compile(r'^[\d\s\u202f]+(?:,\d{2})?\s*€$')
    campaigns, i = [], 0
    while i + 5 < len(lines):
        if not pct.match(lines[i]):
            i += 1
            continue
        percentage, sector, stage, money, status, description = lines[i:i + 6]
        if stage not in STAGES or not amount.match(money) or status.lower() != 'campagne en cours':
            i += 1
            continue
        tags, envelopes, j = [], [], i + 6
        while j < len(lines) and not pct.match(lines[j]) and not lines[j].startswith('+150 sociétés'):
            value = lines[j]
            if any(word in value.upper() for word in FISCAL_WORDS):
                tags.append(value)
            if value.upper() in {'PEA', 'PEA-PME', '150 0 B TER'}:
                envelopes.append(value)
            j += 1
        campaigns.append({'platform': 'Sowefund', 'title': title_from_description(sector, description),
            'sector': sector, 'description': description, 'amount': money, 'status': status,
            'detail': f'{stage} - {percentage}', 'tax': list(dict.fromkeys(tags)),
            'envelopes': list(dict.fromkeys(envelopes)), 'url': SOWEFUND_URL})
        i = j
    return campaigns


def parse_wiseed(text):
    lines = clean_lines(text)
    start = next((i for i, x in enumerate(lines) if re.match(r'^\d+ projets? trouv', x, re.I)), 0)
    end = next((i for i, x in enumerate(lines[start:], start) if re.match(r'^Page \d+ sur', x, re.I)), len(lines))
    lines = lines[start:end]
    statuses = {'Collecte en cours', 'Clôture en cours'}
    indices = [i for i, x in enumerate(lines) if x in statuses]
    campaigns = []
    for pos, i in enumerate(indices):
        j = indices[pos + 1] if pos + 1 < len(indices) else len(lines)
        block = lines[i:j]
        if len(block) < 4:
            continue
        title = block[1]
        amount_idx = next((k for k, x in enumerate(block) if re.match(r'^€[\d,.\s]+$', x)), None)
        money = block[amount_idx] if amount_idx is not None else 'Non détecté'
        description_end = amount_idx if amount_idx is not None else len(block)
        description = ' '.join(block[2:description_end]).strip()
        tail = block[(amount_idx + 1 if amount_idx is not None else description_end):]
        advantages = [x for x in block if any(w in x.upper() for w in ('IR', 'PEA', 'DÉFISCALISATION', 'DEFISCALISATION'))]
        detail = ' - '.join(x for x in tail if any(w in x.lower() for w in ('horizon', 'rendement', 'ans', 'mois')))
        campaigns.append({'platform': 'WiSEED', 'title': title, 'sector': 'À vérifier sur la fiche',
            'description': description, 'amount': money, 'status': block[0],
            'detail': detail or 'Projet en financement', 'tax': list(dict.fromkeys(advantages)),
            'envelopes': [], 'url': WISEED_URL})
    return campaigns


def fetch_page(browser, url, name):
    page = browser.new_page(viewport={'width': 1440, 'height': 1600}, locale='fr-FR')
    page.goto(url, wait_until='domcontentloaded', timeout=90000)
    page.wait_for_timeout(8000)
    text = page.locator('body').inner_text()
    page.screenshot(path=f'{name}-page.png', full_page=True)
    with open(f'{name}-texte.txt', 'w', encoding='utf-8') as handle:
        handle.write(text)
    page.close()
    return text


def badges(values, css):
    return ''.join(f'<span class="badge {css}">{escape(v)}</span>' for v in values)


def create_report(campaigns):
    now = datetime.now().strftime('%d/%m/%Y à %H:%M')
    sections = []
    for platform in ('Sowefund', 'WiSEED'):
        items = [c for c in campaigns if c['platform'] == platform]
        cards = []
        for c in items:
            tax = badges(c['tax'], 'tax') or '<span class="badge neutral">Fiscalité à vérifier</span>'
            env = badges(c['envelopes'], 'env')
            cards.append(f'''<article class="card"><h3>{escape(c['title'])}</h3>
<p class="sub">{escape(c['sector'])} - {escape(c['detail'])}</p><div>{tax}{env}</div>
<div class="grid"><div><small>Montant affiché</small><b>{escape(c['amount'])}</b></div>
<div><small>Statut</small><b>{escape(c['status'])}</b></div></div>
<p>{escape(c['description'])}</p><a href="{escape(c['url'])}" target="_blank" rel="noopener">Voir les projets sur {platform}</a></article>''')
        content = ''.join(cards) or '<p>Aucun projet détecté.</p>'
        sections.append(f'<section><h2>{platform} <span>{len(items)} projet(s)</span></h2>{content}</section>')
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Veille investissements innovants</title>
<style>body{{margin:0;background:#f3f6f9;color:#17202a;font:15px Arial}}main{{max-width:1050px;margin:auto;padding:28px}}header{{background:#053f52;color:white;padding:26px;border-radius:14px}}section h2{{margin-top:30px;color:#053f52}}section h2 span{{font-size:14px;color:#64748b}}.card{{background:white;border-left:5px solid #00af8a;border-radius:10px;padding:20px;margin:14px 0;box-shadow:0 3px 12px #00000012}}h3{{margin:0;color:#053f52}}.sub{{color:#64748b}}.badge{{display:inline-block;padding:6px 9px;border-radius:14px;margin:3px;font-size:12px;font-weight:bold}}.tax{{background:#087f5b;color:white}}.env{{background:#e4ebf5}}.neutral{{background:#fff3cd;color:#664d03}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0}}.grid div{{background:#f5f8fa;padding:11px;border-radius:8px}}small,b{{display:block}}a{{color:#0563c1}}footer{{color:#64748b;padding:20px 0;line-height:1.5}}@media(max-width:600px){{.grid{{grid-template-columns:1fr}}}}</style></head>
<body><main><header><h1>Veille des investissements innovants</h1><p>Mise à jour : {escape(now)}</p><p>{len(campaigns)} campagne(s) détectée(s) sur 2 plateformes</p></header>{''.join(sections)}<footer>Les mentions fiscales doivent être vérifiées dans la documentation de chaque opération. L'investissement non coté présente des risques de perte en capital et d'illiquidité.</footer></main></body></html>'''


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        sowefund_text = fetch_page(browser, SOWEFUND_URL, 'sowefund')
        wiseed_text = fetch_page(browser, WISEED_URL, 'wiseed')
        browser.close()
    campaigns = parse_sowefund(sowefund_text) + parse_wiseed(wiseed_text)
    with open('report.html', 'w', encoding='utf-8') as handle:
        handle.write(create_report(campaigns))
    print(f'{len(campaigns)} campagnes détectées')
    for c in campaigns:
        print(f"- {c['platform']} | {c['title']} | {c['amount']} | {', '.join(c['tax']) or 'fiscalité à vérifier'}")
    print('Rapport généré : report.html')


if __name__ == '__main__':
    main()
