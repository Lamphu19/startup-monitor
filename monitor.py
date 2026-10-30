from datetime import datetime
from html import escape
from playwright.sync_api import sync_playwright

URL = "https://sowefund.com/investir"

FISCAL_KEYWORDS = [
    "JEIR",
    "JEII",
    "JEI",
    "IR PME",
    "IR-PME",
    "IR 2026",
]

SECTOR_KEYWORDS = [
    "intelligence artificielle",
    "cyber",
    "deeptech",
    "deep tech",
    "technologie",
    "medtech",
    "énergie",
    "industrie",
    "économie circulaire",
    "défense",
    "aéronautique",
]

IGNORE_LINES = {
    "investir",
    "à propos",
    "ressources",
    "se connecter",
    "créer un compte",
    "voir plus",
    "campagne en cours",
}


def clean_lines(text):
    """Nettoie et déduplique les lignes extraites de la page."""
    results = []
    seen = set()

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split()).strip()

        if not line:
            continue

        if line.lower() in IGNORE_LINES:
            continue

        if line in seen:
            continue

        seen.add(line)
        results.append(line)

    return results


def build_opportunities(lines):
    """
    Repère chaque mention fiscale et récupère les lignes situées autour.
    Cela permet de conserver le secteur, le montant, la description
    et le dispositif fiscal même si Sowefund modifie légèrement ses cartes.
    """
    opportunities = []
    seen_blocks = set()

    for index, line in enumerate(lines):
        upper_line = line.upper()

        fiscal_tags = [
            keyword
            for keyword in FISCAL_KEYWORDS
            if keyword.upper() in upper_line
        ]

        if not fiscal_tags:
            continue

        start = max(0, index - 7)
        end = min(len(lines), index + 3)
        block_lines = lines[start:end]

        block_key = " | ".join(block_lines)

        if block_key in seen_blocks:
            continue

        seen_blocks.add(block_key)

        block_text = " ".join(block_lines).lower()

        sectors = [
            keyword
            for keyword in SECTOR_KEYWORDS
            if keyword.lower() in block_text
        ]

        opportunities.append({
            "fiscal_tags": sorted(set(fiscal_tags)),
            "sectors": sorted(set(sectors)),
            "lines": block_lines,
        })

    return opportunities


def create_report(opportunities, page_title):
    today = datetime.now().strftime("%d/%m/%Y à %H:%M")

    cards = ""

    for number, opportunity in enumerate(opportunities, start=1):
        fiscal_tags = " ".join(
            f'<span class="tag fiscal">{escape(tag)}</span>'
            for tag in opportunity["fiscal_tags"]
        )

        sector_tags = " ".join(
            f'<span class="tag sector">{escape(sector)}</span>'
            for sector in opportunity["sectors"]
        )

        details = "".join(
            f"<li>{escape(line)}</li>"
            for line in opportunity["lines"]
        )

        cards += f"""
        <article class="card">
            <h2>Opportunité fiscale {number}</h2>

            <div class="tags">
                {fiscal_tags}
                {sector_tags}
            </div>

            <ul>
                {details}
            </ul>
        </article>
        """

    if not cards:
        cards = """
        <article class="card warning">
            <h2>Aucune opportunité fiscale détectée</h2>
            <p>
                La page a bien été chargée, mais aucune mention JEI, JEIR,
                JEII, IR-PME ou IR 2026 n'a été trouvée.
            </p>
        </article>
        """

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Veille investissements innovants</title>

    <style>
        body {{
            margin: 0;
            padding: 30px;
            background: #f4f6f8;
            color: #17202a;
            font-family: Arial, sans-serif;
        }}

        main {{
            max-width: 1000px;
            margin: auto;
        }}

        header {{
            padding: 25px;
            margin-bottom: 25px;
            color: white;
            background: #172b4d;
            border-radius: 12px;
        }}

        header h1 {{
            margin-top: 0;
        }}

        .card {{
            margin-bottom: 20px;
            padding: 22px;
            background: white;
            border-left: 6px solid #00a878;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }}

        .card h2 {{
            margin-top: 0;
        }}

        .tags {{
            margin-bottom: 15px;
        }}

        .tag {{
            display: inline-block;
            padding: 6px 10px;
            margin: 3px;
            border-radius: 15px;
            font-size: 13px;
            font-weight: bold;
        }}

        .fiscal {{
            color: white;
            background: #007a5e;
        }}

        .sector {{
            color: #17202a;
            background: #dce6f1;
        }}

        li {{
            margin-bottom: 7px;
            line-height: 1.4;
        }}

        .warning {{
            border-left-color: #e58e26;
        }}

        footer {{
            margin-top: 30px;
            padding: 15px;
            color: #5d6d7e;
            font-size: 13px;
        }}

        a {{
            color: #005eb8;
        }}
    </style>
</head>

<body>
<main>
    <header>
        <h1>Veille investissements innovants</h1>
        <p>Mise à jour : {escape(today)}</p>
        <p>{len(opportunities)} opportunité(s) fiscale(s) détectée(s)</p>
    </header>

    {cards}

    <footer>
        <p>
            Source analysée :
            <a href="{escape(URL)}">{escape(page_title)}</a>
        </p>

        <p>
            Une mention JEI, JEIR ou IR-PME ne garantit pas à elle seule
            l'obtention d'une réduction d'impôt. Vérifier avant toute
            souscription l'attestation fiscale, le taux applicable,
            la date de souscription et les conditions de conservation
            des titres.
        </p>
    </footer>
</main>
</body>
</html>
"""


def main():
    print(f"Chargement de {URL}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1440, "height": 1600},
            locale="fr-FR",
        )

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=90000,
        )

        # Laisse le temps aux campagnes chargées en JavaScript d'apparaître.
        page.wait_for_timeout(8000)

        body_text = page.locator("body").inner_text()
        page_title = page.title()

        # Sauvegardes utiles pour diagnostiquer un éventuel changement du site.
        page.screenshot(
            path="sowefund-page.png",
            full_page=True,
        )

        with open("sowefund-texte.txt", "w", encoding="utf-8") as file:
            file.write(body_text)

        browser.close()

    lines = clean_lines(body_text)
    opportunities = build_opportunities(lines)
    report = create_report(opportunities, page_title)

    with open("report.html", "w", encoding="utf-8") as file:
        file.write(report)

    print(f"{len(lines)} lignes extraites")
    print(f"{len(opportunities)} opportunités fiscales détectées")
    print("Rapport généré : report.html")
    print("Capture générée : sowefund-page.png")
    print("Texte brut généré : sowefund-texte.txt")


if __name__ == "__main__":
    main()
