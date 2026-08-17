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
# SQLite en developpement local. Pour un usage en reseau interne par
# plusieurs employes en meme temps, voir la section "Deploiement sur le
# reseau interne" plus bas (MySQL recommande).
DATABASE_URL=sqlite:///gestion_commerciale.db

# Mode debug local (recharge auto + traces d'erreur detaillees). Ne jamais
# mettre a 1 si l'app est un jour exposee publiquement.
FLASK_DEBUG=1

# A positionner sur "production" lors d'un vrai deploiement : force le cookie
# de session en HTTPS uniquement et refuse de demarrer si SECRET_KEY est
# resteee a sa valeur par defaut.
FLASK_ENV=

# Paiement en ligne (facultatif — sans ça, le bouton "Payer" affiche un message)
STRIPE_SECRET_KEY=sk_test_...

# Connexion Google (facultatif) — callback à enregistrer :
# http://127.0.0.1:5000/connexion/google/callback
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Connexion GitHub (facultatif) — callback à enregistrer :
# http://127.0.0.1:5000/connexion/github/callback
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

# Assistant IA du portail client (facultatif — clé sur console.anthropic.com)
ANTHROPIC_API_KEY=sk-ant-...
```

Sans les clés Stripe/OAuth, l'application fonctionne normalement ; seuls le
paiement en ligne et la connexion sociale affichent un message indisponible.

Le portail client dispose aussi d'un assistant (bulle de discussion en bas
à droite). Les boutons du menu proposé (tarifs, commandes, paiement,
factures, compte, contact) renvoient toujours une réponse à partir de
mots-clés locaux — gratuit, illimité, aucune clé requise. Le texte libre
tapé par le client est envoyé à l'API Claude (Anthropic) si
`ANTHROPIC_API_KEY` est configurée ; sinon il retombe automatiquement sur le
même moteur de mots-clés que les boutons.

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

`python app.py` est un serveur de **développement** (Werkzeug) : mono-utilisateur, pas adapté à plusieurs connexions simultanées. Pour un usage réel par l'équipe, voir la section suivante.

## Déploiement sur le réseau interne (plusieurs employés)

Configuration mise en place pour un usage par toute l'équipe du cabinet, **accessible uniquement depuis le réseau local** (pas depuis Internet) :

- **Base de données** : MySQL au lieu de SQLite (gère correctement plusieurs connexions simultanées). Base `gestion_commerciale`, utilisateur dédié `kbto_app` (pas `root`) avec des droits limités à cette seule base.
- **Serveur** : [`serveur.py`](serveur.py) lance l'application avec [waitress](https://docs.pylonsproject.org/projects/waitress/) (un vrai serveur WSGI, contrairement à `python app.py`), en écoute sur toutes les interfaces réseau (`0.0.0.0`) et non plus seulement `127.0.0.1`.
- **Démarrage automatique** : une tâche planifiée Windows (« KBTO Gestion Commerciale ») démarre `serveur.py` au démarrage de la machine, même sans session ouverte, et le relance automatiquement en cas d'arrêt inattendu.
- **Pare-feu** : le port 5000 n'est ouvert que pour les profils réseau **Privé** et **Domaine** — jamais **Public**. Le réseau Wi-Fi du cabinet a été reclassé en « Privé » dans Windows (nécessaire pour que la règle s'applique).

### Accès des employés

Depuis un autre poste du même réseau, ouvrir `http://<adresse-ip-du-serveur>:5000` (adresse IP locale de la machine qui héberge l'application, ex. `192.168.1.210` — visible via `ipconfig` sur cette machine). Chaque employé se connecte avec son propre compte personnel.

⚠️ Cette adresse IP est attribuée par le routeur (DHCP) et peut changer après un redémarrage du routeur ou de la machine. Pour une adresse stable dans la durée, réserver cette IP pour cette machine dans les paramètres du routeur (« DHCP reservation » / « bail statique »).

⚠️ Connexion en HTTP simple, sans certificat TLS (pas de `https://`) : adapté à un réseau interne de confiance, mais les identifiants et données transitent en clair sur ce réseau. Pour un chiffrement de bout en bout, il faudrait mettre en place un certificat (interne ou via un reverse-proxy) — non fait ici pour rester simple, à envisager si besoin.

### Administration du serveur

```powershell
# Voir l'état de la tâche planifiée
Get-ScheduledTask -TaskName "KBTO Gestion Commerciale" | Get-ScheduledTaskInfo

# Arrêter / redémarrer manuellement
Stop-ScheduledTask -TaskName "KBTO Gestion Commerciale"
Start-ScheduledTask -TaskName "KBTO Gestion Commerciale"
```

Après toute modification du code (`app.py`, templates, etc.), relancer la tâche pour appliquer les changements (`Stop-ScheduledTask` puis `Start-ScheduledTask`).

## Tests

```powershell
pip install pytest
pytest
```

Les tests tournent sur une base SQLite en mémoire (jamais sur le fichier réel).

## Structure du projet

```
app.py                  # routes et logique métier
serveur.py                # lancement en réseau interne (waitress)
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
