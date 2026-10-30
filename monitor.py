import requests
from bs4 import BeautifulSoup
from datetime import datetime
from html import escape

SITEMAP_URLS = [
    "https://sowefund.com/sitemap.xml",
    "https://www.sowefund.com/sitemap.xml",
]

headers = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; StartupMonitor/1.0; "
        "+https://github.com)"
    )
}

project_urls = []
sitemap_used = None
errors = []

for sitemap_url in SITEMAP_URLS:
    try:
        response = requests.get(
            sitemap_url,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "xml")

        urls = [
            loc.get_text(strip=True)
            for loc in soup.find_all("loc")
        ]

        project_urls = sorted({
            url
            for url in urls
            if "/investir/" in url
            and url.rstrip("/").split("/")[-1] != "investir"
        })

        if project_urls:
            sitemap_used = sitemap_url
            break

    except requests.RequestException as error:
        errors.append(f"{sitemap_url} : {error}")

today = datetime.now().strftime("%d/%m/%Y")

html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Veille investissement</title>
</head>
<body>
    <h1>Veille investissement - {today}</h1>
"""

if project_urls:
    html += f"""
    <p>
        {len(project_urls)} pages de campagnes trouvées
        dans le sitemap Sowefund.
    </p>
    <ul>
    """

    for url in project_urls:
        slug = url.rstrip("/").split("/")[-1]
        name = slug.replace("-", " ").title()

        html += f"""
        <li>
            <a href="{escape(url)}" target="_blank">
                {escape(name)}
            </a>
        </li>
        """

    html += "</ul>"

else:
    html += """
    <p>Aucune page de campagne trouvée.</p>
    <p>Le sitemap est peut-être absent, protégé ou organisé en sous-sitemaps.</p>
    """

    if errors:
        html += "<h2>Erreurs</h2><ul>"

        for error in errors:
            html += f"<li>{escape(error)}</li>"

        html += "</ul>"

html += """
</body>
</html>
"""

with open("report.html", "w", encoding="utf-8") as file:
    file.write(html)

print(f"Sitemap utilisé : {sitemap_used}")
print(f"{len(project_urls)} pages de campagnes trouvées")
print("Rapport généré : report.html")
