from datetime import datetime

today = datetime.now().strftime("%d/%m/%Y")

opportunities = [
    {
        "nom": "Exemple IA",
        "secteur": "IA",
        "type": "JEIR",
        "score": 82
    },
    {
        "nom": "Exemple Cyber",
        "secteur": "Cybersécurité",
        "type": "JEII",
        "score": 78
    }
]

html = f"""
<html>
<head>
    <title>Veille Startup</title>
</head>
<body>
    <h1>Veille du {today}</h1>

    <h2>Opportunités détectées</h2>

    <ul>
"""

for opp in opportunities:
    html += f"""
    <li>
      <b>{opp['nom']}</b>
      ({opp['secteur']})
      - {opp['type']}
      - score {opp['score']}/100
    </li>
    """

html += """
    </ul>
</body>
</html>
"""

with open("report.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Rapport généré : report.html")
