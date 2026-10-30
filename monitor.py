import re
from datetime import datetime
from html import escape
from playwright.sync_api import sync_playwright
from pathlib import Path

SOURCES = {
    "Sowefund": "https://sowefund.com/investir",
    "WiSEED": "https://www.wiseed.com/projets/crowdfunding?statuts=EN_FINANCEMENT",
}
STAGES = {"Seed", "SerieA", "PreSerieA"}


def clean_lines(text):
    return [" ".join(x.split()).strip() for x in text.splitlines() if " ".join(x.split()).strip()]


def unique(values):
    return list(dict.fromkeys(values))


def classify(values):
    text = " | ".join(values).upper()
    status, reduction, envelope = [], [], []
    if re.search(r"\bJEIR\b", text): status.append("JEIR")
    if re.search(r"\bJEII\b", text): status.append("JEII")
    if re.search(r"\bJEI\b", text): status.append("JEI")
    if "IR-PME" in text or "IR PME" in text: reduction.append("IR-PME")
    if "IR 2026" in text: reduction.append("IR 2026")
    if "RÉDUCTION IR" in text or "REDUCTION IR" in text: reduction.append("Réduction IR")
    if "PEA-PME" in text: envelope.append("PEA-PME")
    elif re.search(r"\bPEA\b", text): envelope.append("PEA")
    if "150 0 B TER" in text or "150-0 B TER" in text: envelope.append("150-0 B ter")
    return unique(status), unique(reduction), unique(envelope)


def sowefund_title(sector, description):
    upper = description.upper()
    known = {"ANYOS":"ANYOS", "CIRCUL":"Circul'egg", "KEPPLAIR":"KEPPLAIR 72",
             "NOTPARK":"Notpark", "GAMBAS FRANÇAISES":"Agriloops",
             "CHOCOLAT":"Le Chocolat des Français", "WIND FISHER":"Wind Fisher",
             "LIMOVA":"LIMOVA.ai"}
    for key, value in known.items():
        if key in upper: return value
    if ":" in description:
        candidate = description.split(":", 1)[0].strip()
        if 2 <= len(candidate) <= 50: return candidate
    return sector


def parse_sowefund(text):
    lines, campaigns, i = clean_lines(text), [], 0
    pct = re.compile(r"^\d{1,3}%$")
    amount_re = re.compile(r"^[\d\s\u202f]+(?:,\d{2})?\s*€$")
    while i + 5 < len(lines):
        if not pct.match(lines[i]): i += 1; continue
        percentage, sector, stage, amount, state, description = lines[i:i+6]
        if stage not in STAGES or not amount_re.match(amount) or state.lower() != "campagne en cours":
            i += 1; continue
        j = i + 6
        raw = []
        while j < len(lines) and not pct.match(lines[j]) and not lines[j].startswith("+150 sociétés"):
            raw.append(lines[j]); j += 1
        status, reduction, envelope = classify(raw)
        campaigns.append({"platform":"Sowefund", "title":sowefund_title(sector, description),
            "sector":sector, "description":description, "amount":amount, "state":state,
            "detail":f"{stage} - {percentage}", "status":status, "reduction":reduction,
            "envelope":envelope, "url":SOURCES["Sowefund"]})
        i = j
    return campaigns


def parse_wiseed(text):
    lines = clean_lines(text)
    states = {"Collecte en cours", "Clôture en cours"}
    indices = [i for i, x in enumerate(lines) if x in states]
    campaigns = []
    for pos, i in enumerate(indices):
        end = indices[pos+1] if pos+1 < len(indices) else len(lines)
        block = lines[i:end]
        if len(block) < 4: continue
        amount_i = next((k for k,x in enumerate(block) if re.match(r"^€[\d,.\s]+$", x)), None)
        amount = block[amount_i] if amount_i is not None else "Non détecté"
        description = " ".join(block[2:amount_i if amount_i is not None else len(block)]).strip()
        status, reduction, envelope = classify(block)
        campaigns.append({"platform":"WiSEED", "title":block[1], "sector":"À vérifier sur la fiche",
            "description":description, "amount":amount, "state":block[0], "detail":"Projet en financement",
            "status":status, "reduction":reduction, "envelope":envelope, "url":SOURCES["WiSEED"]})
    return campaigns


def fetch(browser, platform, url):
    slug = platform.lower()
    page = browser.new_page(viewport={"width":1440,"height":1600}, locale="fr-FR")
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(8000)
    text = page.locator("body").inner_text()
    page.screenshot(path=f"{slug}-page.png", full_page=True)
    Path(f"{slug}-texte.txt").write_text(text, encoding="utf-8")
    page.close()
    return text


def badge(values, css, fallback):
    if not values: return f'<span class="badge unknown">{fallback}</span>'
    return "".join(f'<span class="badge {css}">{escape(v)}</span>' for v in values)


def tokens(c):
    mapping = {"JEI":"s-jei", "JEIR":"s-jeir", "JEII":"s-jeii", "IR-PME":"r-ir-pme",
               "IR 2026":"r-ir-2026", "Réduction IR":"r-ir", "PEA":"e-pea",
               "PEA-PME":"e-pea-pme", "150-0 B ter":"e-150"}
    result = [mapping[x] for x in c["status"]+c["reduction"]+c["envelope"] if x in mapping]
    if not c["status"]: result.append("s-unknown")
    if not c["reduction"]: result.append("r-unknown")
    if not c["envelope"]: result.append("e-unknown")
    return " ".join(unique(result))


def report(campaigns):
    sections = []
    for platform in SOURCES:
        cards = []
        items = [c for c in campaigns if c["platform"] == platform]
        for c in items:
            cards.append(f'''<article class="card" data-filters="{tokens(c)}">
<h3>{escape(c['title'])}</h3><p class="sub">{escape(c['sector'])} - {escape(c['detail'])}</p>
<div class="cats"><div><small>Statut de l'entreprise</small>{badge(c['status'],'status','À vérifier')}</div>
<div><small>Réduction d'impôt</small>{badge(c['reduction'],'reduction','À vérifier')}</div>
<div><small>Enveloppe / mécanisme</small>{badge(c['envelope'],'envelope','À vérifier')}</div></div>
<div class="grid"><div><small>Montant affiché</small><b>{escape(c['amount'])}</b></div>
<div><small>Statut de campagne</small><b>{escape(c['state'])}</b></div></div>
<p>{escape(c['description'])}</p><a href="{escape(c['url'])}" target="_blank" rel="noopener">Voir sur {platform}</a></article>''')
        sections.append(f'<section><h2>{platform} <span>{len(items)} projet(s)</span></h2>{"".join(cards) or "<p>Aucun projet détecté.</p>"}</section>')
    now = datetime.now().strftime("%d/%m/%Y à %H:%M")
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Veille fiscale</title>
<style>body{{margin:0;background:#f3f6f9;color:#17202a;font:15px Arial}}main{{max-width:1050px;margin:auto;padding:28px}}header{{background:#053f52;color:white;padding:26px;border-radius:14px}}.panel,.card{{background:white;border-radius:10px;padding:20px;margin:18px 0;box-shadow:0 3px 12px #0001}}.card{{border-left:5px solid #00af8a}}h2,h3{{color:#053f52}}h3{{margin:0}}.sub,section h2 span{{color:#64748b}}.group{{margin:12px 0}}.group strong{{display:block}}button{{padding:8px 12px;margin:3px;border:1px solid #b8c7d1;border-radius:18px;background:white;cursor:pointer}}button.active{{background:#087f5b;color:white}}.cats{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:14px 0}}.cats>div,.grid>div{{background:#f5f8fa;padding:11px;border-radius:8px}}.badge{{display:inline-block;padding:6px 9px;border-radius:14px;margin:5px 4px 0 0;font-size:12px;font-weight:bold}}.status{{background:#315b7d;color:white}}.reduction{{background:#087f5b;color:white}}.envelope{{background:#e4ebf5}}.unknown{{background:#fff3cd;color:#664d03}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}small,b{{display:block}}.hidden{{display:none}}@media(max-width:700px){{.cats,.grid{{grid-template-columns:1fr}}}}</style></head><body><main>
<header><h1>Veille des investissements innovants</h1><p>Mise à jour : {escape(now)}</p><p>{len(campaigns)} campagne(s) détectée(s)</p></header>
<div class="panel"><div class="group"><strong>Statut de l'entreprise</strong><button data-filter="s-jeir">JEIR</button><button data-filter="s-jeii">JEII</button><button data-filter="s-jei">JEI</button><button data-filter="s-unknown">À vérifier</button></div>
<div class="group"><strong>Réduction d'impôt</strong><button data-filter="r-ir-pme">IR-PME</button><button data-filter="r-ir-2026">IR 2026</button><button data-filter="r-ir">Réduction IR</button><button data-filter="r-unknown">À vérifier</button></div>
<div class="group"><strong>Enveloppe / mécanisme</strong><button data-filter="e-pea">PEA</button><button data-filter="e-pea-pme">PEA-PME</button><button data-filter="e-150">150-0 B ter</button><button data-filter="e-unknown">À vérifier</button></div>
<button id="reset" class="active">Tous les dossiers</button><p id="count"></p></div>{''.join(sections)}
<footer>Catégories extraites des pages publiques. Vérifier la documentation fiscale avant toute souscription.</footer></main>
<script>const bs=document.querySelectorAll('button[data-filter]'),cs=document.querySelectorAll('.card'),active=new Set(),count=document.querySelector('#count'),reset=document.querySelector('#reset');function apply(){{let n=0;cs.forEach(c=>{{const f=c.dataset.filters.split(' '),show=[...active].every(x=>f.includes(x));c.style.display=show?'block':'none';if(show)n++}});document.querySelectorAll('section').forEach(s=>s.classList.toggle('hidden',![...s.querySelectorAll('.card')].some(c=>c.style.display!='none')));count.textContent=n+' dossier(s) affiché(s)';reset.classList.toggle('active',active.size===0)}}bs.forEach(b=>b.onclick=()=>{{active.has(b.dataset.filter)?active.delete(b.dataset.filter):active.add(b.dataset.filter);b.classList.toggle('active');apply()}});reset.onclick=()=>{{active.clear();bs.forEach(b=>b.classList.remove('active'));apply()}};apply();</script></body></html>'''


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        sowefund = fetch(browser, "Sowefund", SOURCES["Sowefund"])
        wiseed = fetch(browser, "WiSEED", SOURCES["WiSEED"])
        browser.close()
    campaigns = parse_sowefund(sowefund) + parse_wiseed(wiseed)
    Path("report.html").write_text(report(campaigns), encoding="utf-8")
    print(f"{len(campaigns)} campagnes détectées")
    for c in campaigns:
        print(f"- {c['platform']} | {c['title']} | statut={c['status'] or ['à vérifier']} | réduction={c['reduction'] or ['à vérifier']} | enveloppe={c['envelope'] or ['à vérifier']}")
    print("Rapport généré : report.html")


if __name__ == "__main__":
    main()
