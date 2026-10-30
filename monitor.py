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

GENERIC_TITLES = {
    "Medtech": "Diagnostic intestinal par capsule",
    "Services": "OS des entreprises européennes",
    "Énergie": "Électricité par vents d’altitude",
    "Agroalimentaire": "Gambas françaises responsables",
    "Technologie": "Technologie innovante",
}


def clean_lines(text):
    """Transforme le texte de la page en lignes propres."""

    return [
        " ".join(line.split()).strip()
        for line in text.splitlines()
        if " ".join(line.split()).strip()
    ]


def campaign_title(sector, description):
    """
    Extrait le nom de la société quand il se trouve au début
    de la description, avant un deux-points.
    """

    if ":" in description:
        possible_name = description.split(":", 1)[0].strip()

        if 2 <= len(possible_name) <= 50:
            return possible_name

    upper_description = description.upper()

    if upper_description.startswith("ANYOS "):
        return "ANYOS"

    if upper_description.startswith("KEPPLAIR 72"):
        return "KEPPLAIR 72"

    if "TÉLÉPÉAGE DU STATIONNEMENT" in upper_description:
        return "Notpark"

    if "GAMBAS FRANÇAISES" in upper_description:
        return "Agriloops"

    if "CHOCOLAT" in upper_description:
        return "Le Chocolat des Français"

    return GENERIC_TITLES.get(sector, sector)


def parse_campaigns(lines):
    """
    Une campagne commence par un pourcentage, puis contient :
    secteur, stade, montant, statut, description et dispositifs.
    """

    campaigns = []
    index = 0

    percentage_pattern = re.compile(r"^\d{1,3}%$")
    amount_pattern = re.compile(
        r"^[\d\s\u202f]+(?:,\d{2})?\s*€$"
    )

    while index < len(lines):
        if not percentage_pattern.match(lines[index]):
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

        # Vérification pour éviter de traiter d’autres pour
