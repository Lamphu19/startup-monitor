import requests
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://sowefund.com/investir"

response = requests.get(URL, timeout=30)

html_content = response.text

keywords = [
    "JEI",
    "JEIR",
    "IR",
    "IA",
    "CYBER"
]

matches = []

for line in html_content.splitlines():
    upper_line = line.upper()

    for keyword in keywords:
        if keyword in upper_line:
            matches.append(line.strip())
            break

today = datetime.now().strftime("%d/%m/%Y")

html = f"""
<html>
<head>
<meta charset="utf-8">
<title>Veille Investissement</title>
</head>
<body>

<h1>Veille investissement - {today}</h1>

<p>{len(matches)} correspondances trouvées</p>

<ul>
"""

for match in matches[:100]:
    html += f"<li>{match}</li>"

html += """
</ul>

</body>
</html>
"""

with open("report.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"{len(matches)} correspondances trouvées")
print("Rapport généré")
