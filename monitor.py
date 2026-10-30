import re
from datetime import datetime
from html import escape

from playwright.sync_api import sync_playwright


URL = "https://sowefund.com/investir"

FISCAL_TAGS = {
    "JEI",
    "JEIR",
    "JEII",
    "IR PME",
    "IR-PME",
    "IR 2026",
}

OTHER_TAGS = {
    "PEA",
    "PEA-PME",
    "150 0 B Ter",
}

STAGES = {
    "Seed",
    "SerieA",
    "PreSerieA",
}


def clean_lines(text):
    """Nettoie les lignes extraites de la page."""

    lines = []

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split()).strip()

        if line:
            lines.append(line)

    return lines


def detect_title(sector, description):
    """Essaie de retrouver le nom de la société dans la description."""

    upper_description = description.upper()

    if upper_description.startswith("ANYOS"):
        return "ANYOS"

    if "CIRCUL" in upper_description and "EGG" in upper_description:
        return "Circul'egg"

    if upper_description.startswith("KEPPLAIR"):
        return "KEPPLAIR 72"

    if "NOTPARK" in upper_description:
        return "Notpark"

    if "TÉLÉPÉAGE DU STATIONNEMENT" in upper_description:
        return "Notpark"

    if "GAMBAS FRANÇAISES" in upper_description:
        return "Agriloops"

    if "CHOCOLAT" in upper_description:
        return "Le Chocolat des Français"

    if "WIND FISHER" in upper_description:
        return "Wind Fisher"

    if "LIMOVA" in upper_description:
        return "LIMOVA.ai"

    # Certaines descriptions commencent par le nom suivi de deux-points.
    if ":" in description:
        possible_name = description.split(":", 1)[0].strip()

        if 2 <= len(possible_name) <= 50:
            return possible_name

    fallback_titles = {
        "Medtech": "Diagnostic intestinal par capsule",
        "Services": "Solution numérique B2B",
        "Énergie": "Production d'énergie innovante",
        "Agroalimentaire": "Entreprise agroalimentaire",
        "Technologie": "Entreprise technologique",
        "Industrie": "Entreprise industrielle",
        "Économie circulaire": "Entreprise d'économie circulaire",
    }

    return fallback_titles.get(sector, sector)


def parse_campaigns(lines):
    """
    Détecte les campagnes selon la structure visible sur Sowefund :

    pourcentage
    secteur
    stade
    montant
    statut
    description
    dispositifs fiscaux
    """

    campaigns = []
    index = 0

    percentage_pattern = re.compile(r"^\d{1,3}%$")

    amount_pattern = re.compile(
        r"^[\d\s\u202f]+(?:,\d{2})?\s*€$"
    )

    while index < len(lines):
        current_line = lines[index]

        if not percentage_pattern.match(current_line):
            index += 1
            continue

        if index + 5 >= len(lines):
            break

        percentage = lines[index]
        sector = lines[index + 1]
        stage = lines[index + 2]
        amount = lines[index + 3]
        status = lines[index + 4]
        description = lines[index + 5]

        # Vérifie qu'il s'agit vraiment du début d'une campagne.
        if stage not in STAGES:
            index += 1
            continue

        if not amount_pattern.match(amount):
            index += 1
            continue

        if status.lower() != "campagne en cours":
            index += 1
            continue

        fiscal_tags = []
        other_tags = []

        cursor = index + 6

        while cursor < len(lines):
            candidate = lines[cursor]

            # Le pourcentage suivant correspond à la campagne suivante.
            if percentage_pattern.match(candidate):
                break

            # Fin de la section des campagnes ouvertes.
            if candidate.startswith("+150 sociétés"):
                break

            if candidate in FISCAL_TAGS:
                fiscal_tags.append(candidate)

            if candidate in OTHER_TAGS:
                other_tags.append(candidate)

            cursor += 1

        campaign = {
            "title": detect_title(sector, description),
            "percentage": percentage,
            "sector": sector,
            "stage": stage,
            "amount": amount,
            "status": status,
            "description": description,
            "fiscal": list(dict.fromkeys(fiscal_tags)),
            "envelopes": list(dict.fromkeys(other_tags)),
        }

        campaigns.append(campaign)
        index = cursor

    return campaigns


def fiscal_priority(campaign):
    """Classe les campagnes selon l'intérêt fiscal apparent."""

    tags = set(campaign["fiscal"])

    if "JEIR" in tags or "JEII" in tags:
        return 1

    if "JEI" in tags:
        return 2

    if "IR PME" in tags or "IR-PME" in tags:
        return 3

    if "IR 2026" in tags:
        return 4

    return 5


def create_badges(values, css_class):
    """Crée les badges HTML."""

    return "".join(
        f'<span class="badge {css_class}">{escape(value)}</span>'
        for value in values
    )


def create_report(campaigns):
    """Génère le rapport HTML final."""

    now = datetime.now().strftime("%d/%m/%Y à %H:%M")

    fiscal_campaigns = [
        campaign
        for campaign in campaigns
        if campaign["fiscal"]
    ]

    fiscal_campaigns.sort(
        key=lambda campaign: (
            fiscal_priority(campaign),
            campaign["title"].lower(),
        )
    )

    cards = ""

    for campaign in fiscal_campaigns:
        fiscal_badges = create_badges(
            campaign["fiscal"],
            "fiscal",
        )

        envelope_badges = create_badges(
            campaign["envelopes"],
            "envelope",
        )

        cards += f"""
        <article class="card">
            <div class="card-header">
                <div>
                    <h2>{escape(campaign["title"])}</h2>

                    <p class="subtitle">
                        {escape(campaign["sector"])}
                        · {escape(campaign["stage"])}
                    </p>
                </div>

                <span class="progress">
                    {escape(campaign["percentage"])}
                </span>
            </div>

            <div class="badges">
                {fiscal_badges}
                {envelope_badges}
            </div>

            <div class="information">
                <div>
                    <span class="label">Montant affiché</span>
                    <strong>{escape(campaign["amount"])}</strong>
                </div>

                <div>
                    <span class="label">Statut</span>
                    <strong>{escape(campaign["status"])}</strong>
                </div>
            </div>

            <p class="description">
                {escape(campaign["description"])}
            </p>
        </article>
        """

    if not cards:
        cards = """
        <article class="card warning">
            <h2>Aucune campagne fiscale détectée</h2>

            <p>
                La page a été chargée, mais aucune campagne contenant
                JEI, JEIR, JEII, IR PME ou IR 2026 n'a été identifiée.
            </p>
        </article>
        """

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Veille des investissements innovants</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            padding: 30px 18px;
            background: #f3f6f9;
            color: #17202a;
            font-family: Arial, sans-serif;
        }}

        main {{
            max-width: 1000px;
            margin: auto;
        }}

        header {{
            padding: 28px;
            margin-bottom: 24px;
            color: white;
            background: #053f52;
            border-radius: 14px;
        }}

        header h1 {{
            margin: 0 0 12px;
        }}

        header p {{
            margin: 6px 0;
        }}

        .summary {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 18px;
        }}

        .summary span {{
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.16);
            border-radius: 18px;
        }}

        .card {{
            padding: 23px;
            margin-bottom: 18px;
            background: white;
            border-left: 6px solid #00af8a;
            border-radius: 12px;
            box-shadow: 0 3px 12px rgba(25, 42, 60, 0.08);
        }}

        .warning {{
            border-left-color: #e58e26;
        }}

        .card-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 20px;
        }}

        h2 {{
            margin: 0;
            color: #053f52;
        }}

        .subtitle {{
            margin: 6px 0 0;
            color: #64748b;
        }}

        .progress {{
            min-width: 60px;
            padding: 9px;
            color: white;
            text-align: center;
            font-weight: bold;
            background: #00af8a;
            border-radius: 18px;
        }}

        .badges {{
            margin: 18px 0;
        }}

        .badge {{
            display: inline-block;
            padding: 6px 10px;
            margin: 3px 4px 3px 0;
            border-radius: 15px;
            font-size: 13px;
            font-weight: bold;
        }}

        .fiscal {{
            color: white;
            background: #087f5b;
        }}

        .envelope {{
            color: #253858;
            background: #e4ebf5;
        }}

        .information {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin: 16px 0;
        }}

        .information div {{
            padding: 12px;
            background: #f5f8fa;
            border-radius: 8px;
        }}

        .label {{
            display: block;
            margin-bottom: 5px;
            color: #64748b;
            font-size: 12px;
            text-transform: uppercase;
        }}

        .description {{
            margin-bottom: 0;
            line-height: 1.55;
        }}

        footer {{
            padding: 20px;
            color: #64748b;
            font-size: 13px;
            line-height: 1.5;
        }}

        @media (max-width: 600px) {{
            .information {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>

<body>
<main>
    <header>
        <h1>Veille des investissements innovants</h1>

        <p>Mise à jour : {escape(now)}</p>

        <div class="summary">
            <span>{len(campaigns)} campagnes en cours détectées</span>

            <span>
                {len(fiscal_campaigns)}
                avec dispositif fiscal
            </span>
        </div>
    </header>

    {cards}

    <footer>
        <p>
            Source analysée : Sowefund,
            page « Investissements du moment ».
        </p>

        <p>
            Les montants et pourcentages sont ceux affichés par la
            plateforme. Ils ne constituent ni une valorisation,
            ni une recommandation d'investissement.
        </p>

        <p>
            La mention JEI, JEIR, JEII, IR PME ou IR 2026 doit être
            vérifiée dans la documentation de chaque opération avant
            toute souscription. L'investissement non coté comporte
            notamment des risques de perte en capital et d'illiquidité.
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
            viewport={
                "width": 1440,
                "height": 1600,
            },
            locale="fr-FR",
        )

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=90000,
        )

        # Attente du chargement des campagnes en JavaScript.
        page.wait_for_timeout(8000)

        body_text = page.locator("body").inner_text()

        page.screenshot(
            path="sowefund-page.png",
            full_page=True,
        )

        browser.close()

    # Sauvegarde du texte brut pour faciliter les diagnostics.
    with open(
        "sowefund-texte.txt",
        "w",
        encoding="utf-8",
    ) as file:
        file.write(body_text)

    lines = clean_lines(body_text)
    campaigns = parse_campaigns(lines)

    report = create_report(campaigns)

    with open(
        "report.html",
        "w",
        encoding="utf-8",
    ) as file:
        file.write(report)

    print(f"{len(lines)} lignes extraites")
    print(f"{len(campaigns)} campagnes en cours détectées")

    for campaign in campaigns:
        fiscal = ", ".join(campaign["fiscal"])

        if not fiscal:
            fiscal = "aucun dispositif fiscal détecté"

        print(
            f"- {campaign['title']} | "
            f"{campaign['sector']} | "
            f"{campaign['amount']} | "
            f"{fiscal}"
        )

    print("Fichiers générés :")
    print("- report.html")
    print("- sowefund-page.png")
    print("- sowefund-texte.txt")


if __name__ == "__main__":
    main()
