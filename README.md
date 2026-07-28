# KBTO — Gestion commerciale

Application web interne de gestion commerciale : clients, produits/stock,
facturation, rapports, et portail libre-service pour les clients externes.

Stack : Flask + Jinja2 + SQLAlchemy + SQLite (dev) / MySQL (prod prévue).

## Installation

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration (`.env`)

Crée un fichier `.env` à la racine (jamais commité, voir `.gitignore`) :

```
SECRET_KEY=change-moi-en-production
DATABASE_URL=sqlite:///gestion_commerciale.db

# Paiement en ligne (facultatif — sans ça, le bouton "Payer" affiche un message)
STRIPE_SECRET_KEY=sk_test_...

# Connexion Google (facultatif)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Connexion GitHub (facultatif)
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
```

Sans les clés Stripe/OAuth, l'application fonctionne normalement ; seuls le
paiement en ligne et la connexion sociale affichent un message indisponible.

## Base de données

```powershell
flask db upgrade          # applique les migrations
flask creer-admin         # crée le premier compte administrateur
```

Après toute modification d'un modèle (`models.py`) :

```powershell
flask db migrate -m "message"
flask db upgrade
```

## Lancer l'application

```powershell
python app.py
```

Puis ouvrir http://127.0.0.1:5000. Deux espaces :
- **Personnel** (employé/administrateur) : identifiant + mot de passe, créé via `flask creer-admin` ou par un administrateur.
- **Client** : inscription libre depuis la page de connexion, ou Google/GitHub une fois configuré.

## Tests

```powershell
pip install pytest
pytest
```

Les tests tournent sur une base SQLite en mémoire (jamais sur le fichier réel).

## Structure du projet

```
app.py                  # routes et logique métier
models.py                # modèles SQLAlchemy
forms.py                 # formulaires WTForms
graphiques.py             # génération des graphiques SVG du tableau de bord
migrations/               # migrations Alembic
static/css/style.css      # feuille de style unique
templates/                # templates Jinja2 (personnel + portail client)
tests/                    # suite pytest
```

## Documents

- `CAHIER_DES_CHARGES.pdf` — cahier des charges v2 (inclut le portail client
  et le paiement en ligne).
- `EXTENSION_PORTAIL_CLIENT.md` — détail du changement de périmètre par
  rapport à la version 1.

## Déploiement (à faire)

- Migrer `DATABASE_URL` vers MySQL (`mysql+pymysql://...`) et rejouer les
  migrations.
- Adapter la requête `strftime` des rapports (spécifique SQLite) vers
  l'équivalent MySQL (`DATE_FORMAT`).
- Servir l'application avec un serveur WSGI de production (pas
  `python app.py`, qui est un serveur de développement).
