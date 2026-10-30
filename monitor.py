import feedparser
from datetime import datetime

RSS_URLS = [
    "https://news.google.com/rss/search?q=IR-PME+startup",
    "https://news.google.com/rss/search?q=crowdfunding+equity+startup+france",
    "https://news.google.com/rss/search?q=WiSEED",
    "https://news.google.com/rss/search?q=Sowefund",
    "https://news.google.com/rss/search?q=JEI+levee+fonds",
]

items = []

for url in RSS_URLS:
    feed = feedparser.parse(url)

    for entry in feed.entries[:5]:
        items.append({
            "title": entry.title,
            "link": entry.link
        })

today = datetime.now().strftime("%d/%m/%Y")

html = f"""
<html>
<head>
<meta charset="utf-8">
<title>Veille Investissement</title>
</head>
<body>

<h1>Veille investissement - {today}</h1>

<p>{len(items)} actualités trouvées</p>

<ul>
"""

for item in items:
    html += f"""
    <li>
        <a href="{item['link']}">{item['title']}</a>
    </li>
    """

html += """
</ul>

</body>
</html>
"""

with open("report.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"{len(items)} actualités trouvées")
print("Rapport généré : report.html")
