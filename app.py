import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from io import BytesIO

import click
import graphiques
import stripe
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    send_file,
    url_for,
    request,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet
from forms import (
    ConnexionForm,
    ClientForm,
    CommandeClientForm,
    ProduitForm,
    FactureForm,
    InscriptionClientForm,
    LigneFactureForm,
    LONGUEUR_MIN_MOT_DE_PASSE,
    LONGUEUR_MIN_NOM_UTILISATEUR,
    PaiementForm,
    StatutFactureForm,
    UtilisateurForm,
    ModifierUtilisateurForm,
    ProfilForm,
    ProfilClientForm,
)
from models import (
    Utilisateur,
    Client,
    Produit,
    Facture,
    DetailFacture,
    Paiement,
    Parametres,
    STATUTS_FACTURE,
    METHODES_PAIEMENT,
    db,
)

load_dotenv()

app = Flask(__name__)

# Valeur de repli utilisee uniquement en developpement local (jamais commitee
# comme vraie cle secrete). Si elle est encore active en production, les
# cookies de session ET les tokens CSRF seraient signes avec une valeur
# visible dans le code source -> garde-fou juste en dessous.
CLE_SECRETE_PAR_DEFAUT = "cle-developpement-gestion-commerciale"

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", CLE_SECRETE_PAR_DEFAUT)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///gestion_commerciale.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Securite des cookies de session (et du cookie "remember me" de Flask-Login) :
# HttpOnly + SameSite=Lax explicites (defense en profondeur), et Secure force
# des que l'app tourne en production (FLASK_ENV=production dans .env), pour
# ne jamais transmettre le cookie de session en clair sur HTTP. En local/tests
# (FLASK_ENV non defini), Secure reste desactive pour ne pas casser le
# developpement sur http://127.0.0.1.
MODE_PRODUCTION = os.getenv("FLASK_ENV", "").strip().lower() == "production"

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = MODE_PRODUCTION
app.config["REMEMBER_COOKIE_HTTPONLY"] = True
app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
app.config["REMEMBER_COOKIE_SECURE"] = MODE_PRODUCTION

# Garde-fou : on refuse de demarrer si la cle secrete par defaut (visible
# dans le code source) est encore active alors que l'app est declaree en
# production. Sans ce garde-fou, un deploiement en prod sans SECRET_KEY dans
# .env signerait sessions et CSRF avec une valeur connue de quiconque lit le
# depot -> sessions falsifiables et protection CSRF contournable.
if MODE_PRODUCTION and app.config["SECRET_KEY"] == CLE_SECRETE_PAR_DEFAUT:
    raise RuntimeError(
        "SECRET_KEY par défaut détectée alors que FLASK_ENV=production. "
        "Définissez une vraie valeur secrète (aléatoire, unique) dans le "
        "fichier .env avant de démarrer l'application en production."
    )

# Cle secrete Stripe (mode test). Tant qu'elle n'est pas fournie via .env,
# le paiement en ligne affiche un message explicite au lieu de planter.
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
stripe.api_key = STRIPE_SECRET_KEY

# Connexion Google / GitHub (OAuth). Tant que les cles ne sont pas fournies
# via .env, les boutons affichent un message explicite au lieu de planter.
oauth = OAuth(app)

if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
    oauth.register(
        name="google",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"):
    oauth.register(
        name="github",
        client_id=os.getenv("GITHUB_CLIENT_ID"),
        client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )

db.init_app(app)
Migrate(app, db)
CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = "connexion"
login_manager.login_message = "Veuillez vous connecter pour continuer."
login_manager.login_message_category = "info"


@login_manager.user_loader
def charger_utilisateur(identifiant):
    if identifiant.startswith("client-"):
        return db.session.get(Client, int(identifiant.split("-", 1)[1]))
    return db.session.get(Utilisateur, int(identifiant))


def administrateur_requis(vue):
    @wraps(vue)
    def enveloppe(*args, **kwargs):
        if current_user.role != "administrateur":
            abort(403)
        return vue(*args, **kwargs)
    return enveloppe


def redirection_apres_connexion():
    if isinstance(current_user, Client):
        return redirect(url_for("portail_tableau_de_bord"))
    return redirect(url_for("tableau_de_bord"))


# Routes accessibles sans distinction d'espace (avant meme la connexion, ou
# communes aux deux). Toute autre route est reservee soit au personnel
# (employe/administrateur), soit au portail client (prefixe "portail_"),
# et le garde ci-dessous redirige automatiquement en cas d'erreur d'espace.
ROUTES_PARTAGEES = {"accueil", "connexion", "inscription", "deconnexion", "static", None}


@app.before_request
def separer_espace_personnel_et_client():
    if not current_user.is_authenticated:
        return None
    if request.endpoint in ROUTES_PARTAGEES:
        return None

    est_client = isinstance(current_user, Client)
    dans_le_portail = (request.endpoint or "").startswith("portail_")

    if est_client and not dans_le_portail:
        return redirect(url_for("portail_tableau_de_bord"))
    if not est_client and dans_le_portail:
        return redirect(url_for("tableau_de_bord"))
    return None


@app.errorhandler(403)
def acces_interdit(erreur):
    return render_template("403.html"), 403


@app.route("/")
def accueil():
    if current_user.is_authenticated:
        return redirection_apres_connexion()
    return redirect(url_for("connexion"))


# Protection anti brute-force sur /connexion : compteur d'echecs en memoire
# du processus, par identifiant normalise (pas par IP, pour ne pas bloquer
# tout un reseau/proxy partage a cause d'un seul compte). Volontairement sans
# nouvelle dependance (pas de Redis/Flask-Limiter) : suffisant pour un seul
# worker de processus ; a remplacer par un stockage partage si l'app est un
# jour deployee derriere plusieurs workers/instances.
LIMITE_TENTATIVES_CONNEXION = 5
FENETRE_VERROUILLAGE_CONNEXION = timedelta(minutes=10)
_tentatives_echouees_connexion = {}


def _connexion_est_verrouillee(identifiant):
    entree = _tentatives_echouees_connexion.get(identifiant)
    if entree is None:
        return False
    nb_echecs, dernier_echec = entree
    if nb_echecs < LIMITE_TENTATIVES_CONNEXION:
        return False
    if datetime.now(timezone.utc) - dernier_echec > FENETRE_VERROUILLAGE_CONNEXION:
        _tentatives_echouees_connexion.pop(identifiant, None)
        return False
    return True


def _enregistrer_echec_connexion(identifiant):
    nb_echecs, _ = _tentatives_echouees_connexion.get(identifiant, (0, None))
    _tentatives_echouees_connexion[identifiant] = (nb_echecs + 1, datetime.now(timezone.utc))


def _reinitialiser_echecs_connexion(identifiant):
    _tentatives_echouees_connexion.pop(identifiant, None)


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if current_user.is_authenticated:
        return redirection_apres_connexion()

    form = ConnexionForm()

    if form.validate_on_submit():
        identifiant = form.nom_utilisateur.data.strip().lower()

        if _connexion_est_verrouillee(identifiant):
            flash(
                "Trop de tentatives de connexion échouées. Merci de réessayer "
                "dans quelques minutes.",
                "danger",
            )
            return render_template("login.html", form=form)

        utilisateur = Utilisateur.query.filter_by(nom_utilisateur=identifiant).first()
        if utilisateur and utilisateur.verifier_mot_de_passe(form.mot_de_passe.data):
            _reinitialiser_echecs_connexion(identifiant)
            login_user(utilisateur, remember=form.se_souvenir.data)
            flash("Connexion réussie.", "success")
            return redirect(url_for("tableau_de_bord"))

        client = Client.query.filter_by(email=identifiant).first()
        if client and client.a_un_compte() and client.verifier_mot_de_passe(form.mot_de_passe.data):
            _reinitialiser_echecs_connexion(identifiant)
            login_user(client, remember=form.se_souvenir.data)
            flash("Connexion réussie.", "success")
            return redirect(url_for("portail_tableau_de_bord"))

        _enregistrer_echec_connexion(identifiant)
        flash("Identifiant ou mot de passe incorrect.", "danger")

    return render_template("login.html", form=form)


FOURNISSEURS_OAUTH = ("google", "github")


@app.route("/connexion/<fournisseur>")
def connexion_oauth(fournisseur):
    client_oauth = getattr(oauth, fournisseur, None) if fournisseur in FOURNISSEURS_OAUTH else None
    if client_oauth is None:
        flash("Cette méthode de connexion n'est pas encore configurée.", "danger")
        return redirect(url_for("connexion"))

    redirect_uri = url_for("callback_oauth", fournisseur=fournisseur, _external=True)
    return client_oauth.authorize_redirect(redirect_uri)


@app.route("/connexion/<fournisseur>/callback")
def callback_oauth(fournisseur):
    client_oauth = getattr(oauth, fournisseur, None) if fournisseur in FOURNISSEURS_OAUTH else None
    if client_oauth is None:
        flash("Cette méthode de connexion n'est pas encore configurée.", "danger")
        return redirect(url_for("connexion"))

    try:
        jeton = client_oauth.authorize_access_token()
    except Exception:
        flash("La connexion a été annulée ou a échoué.", "danger")
        return redirect(url_for("connexion"))

    email = ""
    prenom = "Client"
    nom = ""

    if fournisseur == "google":
        profil = jeton.get("userinfo") or client_oauth.userinfo(token=jeton)
        email = (profil.get("email") or "").strip().lower()
        prenom = profil.get("given_name") or profil.get("name") or "Client"
        nom = profil.get("family_name") or ""
    else:  # github
        profil = client_oauth.get("user", token=jeton).json()
        email = (profil.get("email") or "").strip().lower()
        if not email:
            for e in client_oauth.get("user/emails", token=jeton).json():
                if e.get("primary"):
                    email = (e.get("email") or "").strip().lower()
                    break
        morceaux = (profil.get("name") or profil.get("login") or "Client").split(" ", 1)
        prenom = morceaux[0]
        nom = morceaux[1] if len(morceaux) > 1 else ""

    if not email:
        flash("Impossible de récupérer votre adresse email depuis ce fournisseur.", "danger")
        return redirect(url_for("connexion"))

    # Personnel : on se connecte a un compte existant, on n'en cree jamais un
    # nouveau par ce biais (les comptes employe/administrateur restent crees
    # par un administrateur, cf. F-03 du cahier des charges).
    utilisateur = Utilisateur.query.filter_by(email=email).first()
    if utilisateur:
        login_user(utilisateur)
        flash("Connexion réussie.", "success")
        return redirect(url_for("tableau_de_bord"))

    # Client : compte existant relie, ou nouveau compte cree automatiquement
    # (coherent avec l'inscription libre deja en place pour les clients).
    client_compte = Client.query.filter_by(email=email).first()
    if client_compte is None:
        client_compte = Client(nom=nom or "Client", prenom=prenom, email=email)
        db.session.add(client_compte)
        db.session.commit()
        flash("Compte créé avec succès. Bienvenue !", "success")
    else:
        flash("Connexion réussie.", "success")

    login_user(client_compte)
    return redirect(url_for("portail_tableau_de_bord"))


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    if current_user.is_authenticated:
        return redirection_apres_connexion()

    form = InscriptionClientForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        if Client.query.filter_by(email=email).first():
            flash("Un compte existe déjà avec cet email.", "danger")
        else:
            client = Client(
                nom=form.nom.data.strip(),
                prenom=form.prenom.data.strip(),
                email=email,
                telephone=form.telephone.data,
                adresse=form.adresse.data,
            )
            client.definir_mot_de_passe(form.mot_de_passe.data)
            db.session.add(client)
            db.session.commit()
            login_user(client)
            flash("Compte créé avec succès. Bienvenue !", "success")
            return redirect(url_for("portail_tableau_de_bord"))

    return render_template("inscription.html", form=form)


MOIS_FR = {
    "01": "Jan", "02": "Fév", "03": "Mar", "04": "Avr", "05": "Mai", "06": "Jun",
    "07": "Jul", "08": "Aoû", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Déc",
}
SEUIL_STOCK_FAIBLE = 5
JOURS_FACTURE_EN_RETARD = 7
# Nombre d'elements affiches dans les listes "top N" du tableau de bord
# (produits/clients recents, produits en stock critique, dernieres commandes
# du portail) : purement une limite d'affichage, pas une regle metier.
NB_ELEMENTS_TABLEAU_DE_BORD = 5
NB_TOP_CLIENTS_TABLEAU_DE_BORD = 3
# Nombre max de resultats retournes par la recherche globale (personnel),
# par categorie (clients / produits), pour eviter des pages de resultats
# demesurees sur une recherche large.
LIMITE_RESULTATS_RECHERCHE = 15
# Facteur de conversion DH <-> centimes attendu par l'API Stripe (les montants
# Stripe sont toujours exprimes dans la plus petite unite de la devise).
CENTIMES_PAR_DH = 100


def variation_pourcentage(actuel, precedent):
    """Variation en % entre deux montants, pour les badges de tendance des tableaux de bord."""
    actuel = float(actuel or 0)
    precedent = float(precedent or 0)
    if precedent == 0:
        return 100.0 if actuel > 0 else 0.0
    return round((actuel - precedent) / precedent * 100, 1)


@app.context_processor
def injecter_globales():
    return {"current_year": date.today().year}


@app.context_processor
def injecter_notifications():
    if not current_user.is_authenticated:
        return {}

    alertes = []

    if isinstance(current_user, Client):
        nb_en_attente = Facture.query.filter_by(client_id=current_user.id, statut="attente").count()
        if nb_en_attente:
            alertes.append({
                "texte": f"{nb_en_attente} facture(s) en attente de paiement",
                "url": url_for("portail_paiements"),
            })
    else:
        nb_stock_faible = Produit.query.filter(Produit.quantite <= SEUIL_STOCK_FAIBLE).count()
        if nb_stock_faible:
            alertes.append({
                "texte": f"{nb_stock_faible} produit(s) en stock faible ou en rupture",
                "url": url_for("liste_produits"),
            })

        seuil_date = date.today() - timedelta(days=JOURS_FACTURE_EN_RETARD)
        nb_en_retard = Facture.query.filter(
            Facture.statut == "attente", Facture.date < seuil_date
        ).count()
        if nb_en_retard:
            alertes.append({
                "texte": f"{nb_en_retard} facture(s) en attente depuis plus de {JOURS_FACTURE_EN_RETARD} jours",
                "url": url_for("liste_factures"),
            })

        nb_a_encaisser = Facture.query.filter(
            Facture.mode_paiement_prevu.isnot(None), Facture.statut == "attente"
        ).count()
        if nb_a_encaisser:
            alertes.append({
                "texte": f"{nb_a_encaisser} commande(s) client en attente de règlement (chèque/espèces)",
                "url": url_for("liste_factures"),
            })

    return {"notifications": alertes, "nb_notifications": len(alertes)}


@app.route("/tableau-de-bord")
@login_required
def tableau_de_bord():
    nb_clients = Client.query.count()
    nb_produits = Produit.query.count()
    nb_factures = Facture.query.count()

    total_stock = db.session.query(
        db.func.coalesce(db.func.sum(Produit.quantite), 0)
    ).scalar()

    ca_total = db.session.query(
        db.func.coalesce(db.func.sum(Facture.total), 0)
    ).scalar()

    alertes_stock = Produit.query.filter(Produit.quantite <= SEUIL_STOCK_FAIBLE).count()

    # --- Evolution du CA (6 derniers mois avec des factures) ---
    lignes_mois = db.session.query(
        db.func.strftime("%Y-%m", Facture.date).label("mois"),
        db.func.sum(Facture.total).label("total"),
    ).group_by("mois").order_by("mois").all()
    lignes_mois = lignes_mois[-6:]
    labels_mois = [MOIS_FR.get(l.mois[5:7], l.mois) if l.mois else "?" for l in lignes_mois]
    valeurs_mois = [float(l.total or 0) for l in lignes_mois]
    points_ca, points_ca_liste = graphiques.points_courbe(valeurs_mois)

    # --- Repartition du stock par categorie ---
    lignes_categorie = db.session.query(
        db.func.coalesce(Produit.categorie, "Sans catégorie").label("categorie"),
        db.func.sum(Produit.quantite).label("quantite"),
    ).group_by("categorie").order_by(db.desc("quantite")).all()
    repartition_stock = [(l.categorie, l.quantite or 0) for l in lignes_categorie if (l.quantite or 0) > 0]
    segments_stock, circonference_stock = graphiques.segments_donut(repartition_stock)

    # --- Top produits par chiffre d'affaires ---
    top_produits = db.session.query(
        Produit.nom,
        db.func.sum(DetailFacture.quantite * DetailFacture.prix_unitaire).label("total"),
    ).join(DetailFacture, DetailFacture.produit_id == Produit.id) \
     .group_by(Produit.id).order_by(db.desc("total")).limit(NB_ELEMENTS_TABLEAU_DE_BORD).all()

    # --- Top clients (avec mini-tendance de leurs factures) ---
    lignes_top_clients = db.session.query(
        Client.id, Client.nom, Client.prenom,
        db.func.count(Facture.id).label("nb_factures"),
        db.func.sum(Facture.total).label("total"),
    ).join(Facture, Facture.client_id == Client.id) \
     .group_by(Client.id).order_by(db.desc("total")).limit(NB_TOP_CLIENTS_TABLEAU_DE_BORD).all()

    top_clients = []
    for ligne in lignes_top_clients:
        montants = [
            float(f.total or 0)
            for f in Facture.query.filter_by(client_id=ligne.id).order_by(Facture.date).all()
        ]
        top_clients.append({
            "nom": f"{ligne.nom} {ligne.prenom}",
            "nb_factures": ligne.nb_factures,
            "total": ligne.total or Decimal("0"),
            "sparkline": graphiques.sparkline_points(montants),
        })

    produits_critiques = (
        Produit.query.filter(Produit.quantite <= SEUIL_STOCK_FAIBLE)
        .order_by(Produit.quantite)
        .limit(NB_ELEMENTS_TABLEAU_DE_BORD)
        .all()
    )

    # --- Objectif de chiffre d'affaires du mois en cours ---
    params = Parametres.obtenir()
    debut_mois = date.today().replace(day=1)
    ca_mois = db.session.query(
        db.func.coalesce(db.func.sum(Facture.total), 0)
    ).filter(Facture.date >= debut_mois).scalar()

    objectif = params.objectif_ca_mensuel or Decimal("0")
    pourcentage_objectif = (
        min(round(float(ca_mois) / float(objectif) * 100, 1), 100) if objectif else 0
    )

    # --- Variation du CA du mois vs le mois precedent (pour le badge de tendance) ---
    fin_mois_precedent = debut_mois - timedelta(days=1)
    debut_mois_precedent = fin_mois_precedent.replace(day=1)
    ca_mois_precedent = db.session.query(
        db.func.coalesce(db.func.sum(Facture.total), 0)
    ).filter(Facture.date >= debut_mois_precedent, Facture.date < debut_mois).scalar()
    variation_ca = variation_pourcentage(ca_mois, ca_mois_precedent)

    nb_clients_ce_mois = Client.query.filter(Client.id.in_(
        db.session.query(Facture.client_id).filter(Facture.date >= debut_mois)
    )).count()

    derniers_clients = Client.query.order_by(Client.id.desc()).limit(NB_ELEMENTS_TABLEAU_DE_BORD).all()

    return render_template(
        "dashboard.html",
        nb_clients=nb_clients,
        nb_produits=nb_produits,
        nb_factures=nb_factures,
        total_stock=total_stock,
        ca_total=ca_total,
        alertes_stock=alertes_stock,
        labels_mois=labels_mois,
        points_ca=points_ca,
        points_ca_liste=points_ca_liste,
        segments_stock=segments_stock,
        circonference_stock=circonference_stock,
        top_produits=top_produits,
        top_clients=top_clients,
        produits_critiques=produits_critiques,
        ca_mois=ca_mois,
        objectif=objectif,
        pourcentage_objectif=pourcentage_objectif,
        variation_ca=variation_ca,
        nb_clients_ce_mois=nb_clients_ce_mois,
        derniers_clients=derniers_clients,
    )


@app.route("/deconnexion", methods=["POST"])
@login_required
def deconnexion():
    logout_user()
    flash("Vous êtes maintenant déconnecté.", "success")
    return redirect(url_for("connexion"))


@app.cli.command("creer-admin")
@click.option("--nom-utilisateur", prompt="Nom d'utilisateur")
@click.option("--nom", prompt="Nom")
@click.option("--prenom", prompt="Prénom")
@click.option("--email", prompt="Adresse e-mail")
@click.option("--mot-de-passe", prompt="Mot de passe", hide_input=True, confirmation_prompt=True)
def creer_admin(nom_utilisateur, nom, prenom, email, mot_de_passe):
    nom_utilisateur = nom_utilisateur.strip().lower()
    email = email.strip().lower()

    if len(nom_utilisateur) < LONGUEUR_MIN_NOM_UTILISATEUR:
        click.echo("Le nom d'utilisateur doit contenir au moins 3 caractères.")
        return
    if len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        click.echo("Le mot de passe doit contenir au moins 8 caractères.")
        return
    if Utilisateur.query.filter_by(nom_utilisateur=nom_utilisateur).first():
        click.echo("Ce nom d'utilisateur existe déjà.")
        return
    if Utilisateur.query.filter_by(email=email).first():
        click.echo("Un utilisateur possède déjà cette adresse e-mail.")
        return

    administrateur = Utilisateur(
        nom_utilisateur=nom_utilisateur,
        nom=nom.strip(),
        prenom=prenom.strip(),
        email=email,
        role="administrateur",
    )
    administrateur.definir_mot_de_passe(mot_de_passe)

    db.session.add(administrateur)
    db.session.commit()
    click.echo("Administrateur créé avec succès.")


# ==========================
# Gestion des utilisateurs (reservee aux administrateurs)
# ==========================
@app.route("/utilisateurs")
@login_required
@administrateur_requis
def liste_utilisateurs():
    utilisateurs = Utilisateur.query.order_by(Utilisateur.nom_utilisateur).all()
    return render_template("utilisateurs.html", utilisateurs=utilisateurs)


@app.route("/utilisateurs/ajouter", methods=["GET", "POST"])
@login_required
@administrateur_requis
def ajouter_utilisateur():
    form = UtilisateurForm()

    if form.validate_on_submit():
        nom_utilisateur = form.nom_utilisateur.data.strip().lower()
        email = form.email.data.strip().lower()

        if Utilisateur.query.filter_by(nom_utilisateur=nom_utilisateur).first():
            flash("Ce nom d'utilisateur existe déjà.", "danger")
        elif Utilisateur.query.filter_by(email=email).first():
            flash("Un utilisateur possède déjà cette adresse email.", "danger")
        else:
            utilisateur = Utilisateur(
                nom_utilisateur=nom_utilisateur,
                nom=form.nom.data.strip(),
                prenom=form.prenom.data.strip(),
                telephone=form.telephone.data,
                email=email,
                role=form.role.data,
            )
            utilisateur.definir_mot_de_passe(form.mot_de_passe.data)
            db.session.add(utilisateur)
            db.session.commit()
            flash("Utilisateur créé avec succès.", "success")
            return redirect(url_for("liste_utilisateurs"))

    return render_template("ajouter_utilisateur.html", form=form)


@app.route("/utilisateurs/modifier/<int:id>", methods=["GET", "POST"])
@login_required
@administrateur_requis
def modifier_utilisateur(id):
    utilisateur = db.session.get(Utilisateur, id)
    if utilisateur is None:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for("liste_utilisateurs"))

    form = ModifierUtilisateurForm(obj=utilisateur)

    if form.validate_on_submit():
        nom_utilisateur = form.nom_utilisateur.data.strip().lower()
        email = form.email.data.strip().lower()

        conflit_nom = Utilisateur.query.filter_by(nom_utilisateur=nom_utilisateur).first()
        conflit_email = Utilisateur.query.filter_by(email=email).first()
        nb_administrateurs = Utilisateur.query.filter_by(role="administrateur").count()

        if conflit_nom and conflit_nom.id != utilisateur.id:
            flash("Ce nom d'utilisateur existe déjà.", "danger")
        elif conflit_email and conflit_email.id != utilisateur.id:
            flash("Un utilisateur possède déjà cette adresse email.", "danger")
        elif (
            utilisateur.role == "administrateur"
            and form.role.data != "administrateur"
            and nb_administrateurs <= 1
        ):
            flash("Impossible de rétrograder le dernier administrateur.", "danger")
        else:
            utilisateur.nom_utilisateur = nom_utilisateur
            utilisateur.nom = form.nom.data.strip()
            utilisateur.prenom = form.prenom.data.strip()
            utilisateur.telephone = form.telephone.data
            utilisateur.email = email
            utilisateur.role = form.role.data
            if form.nouveau_mot_de_passe.data:
                utilisateur.definir_mot_de_passe(form.nouveau_mot_de_passe.data)
            db.session.commit()
            flash("Utilisateur modifié avec succès.", "success")
            return redirect(url_for("liste_utilisateurs"))

    return render_template("modifier_utilisateur.html", form=form, utilisateur=utilisateur)


@app.route("/utilisateurs/supprimer/<int:id>", methods=["POST"])
@login_required
@administrateur_requis
def supprimer_utilisateur(id):
    utilisateur = db.session.get(Utilisateur, id)
    if utilisateur is None:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for("liste_utilisateurs"))

    if utilisateur.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
        return redirect(url_for("liste_utilisateurs"))

    if utilisateur.role == "administrateur" and Utilisateur.query.filter_by(role="administrateur").count() <= 1:
        flash("Impossible de supprimer le dernier administrateur.", "danger")
        return redirect(url_for("liste_utilisateurs"))

    db.session.delete(utilisateur)
    db.session.commit()
    flash("Utilisateur supprimé avec succès.", "success")
    return redirect(url_for("liste_utilisateurs"))


@app.route("/recherche")
@login_required
def recherche():
    q = request.args.get("q", "").strip()
    clients_trouves = []
    produits_trouves = []
    factures_trouvees = []

    if q:
        clients_trouves = Client.query.filter(
            Client.nom.contains(q) | Client.prenom.contains(q) | Client.email.contains(q)
        ).order_by(Client.nom).limit(LIMITE_RESULTATS_RECHERCHE).all()
        produits_trouves = (
            Produit.query.filter(Produit.nom.contains(q))
            .order_by(Produit.nom)
            .limit(LIMITE_RESULTATS_RECHERCHE)
            .all()
        )
        if q.upper().startswith("FA-"):
            try:
                factures_trouvees = [db.session.get(Facture, int(q.upper().removeprefix("FA-")))]
                factures_trouvees = [f for f in factures_trouvees if f is not None]
            except ValueError:
                factures_trouvees = []

    return render_template(
        "recherche.html",
        q=q,
        clients=clients_trouves,
        produits=produits_trouves,
        factures=factures_trouvees,
    )


@app.route("/clients")
@login_required
def liste_clients():
    recherche = request.args.get("recherche", "")
    clients = Client.query

    if recherche:
        clients = clients.filter(
            (Client.nom.contains(recherche))
            | (Client.prenom.contains(recherche))
            | (Client.email.contains(recherche))
        )

    clients = clients.order_by(Client.nom).all()
    return render_template("clients.html", clients=clients, recherche=recherche)


@app.route("/clients/ajouter", methods=["GET", "POST"])
@login_required
def ajouter_client():
    form = ClientForm()

    if form.validate_on_submit():
        if form.email.data and Client.query.filter_by(email=form.email.data).first():
            flash("Un client existe déjà avec cet email.", "danger")
        else:
            client = Client(
                nom=form.nom.data,
                prenom=form.prenom.data,
                email=form.email.data,
                telephone=form.telephone.data,
                adresse=form.adresse.data,
            )
            db.session.add(client)
            db.session.commit()
            flash("Le client a été ajouté avec succès.", "success")
            return redirect(url_for("liste_clients"))

    return render_template("ajouter_client.html", form=form)


@app.route("/clients/supprimer/<int:id>", methods=["POST"])
@login_required
@administrateur_requis
def supprimer_client(id):
    client = db.session.get(Client, id)
    if client is None:
        flash("Client introuvable.", "danger")
        return redirect(url_for("liste_clients"))

    if client.factures:
        flash(
            "Impossible de supprimer ce client : des factures lui sont rattachées.",
            "danger",
        )
        return redirect(url_for("liste_clients"))

    db.session.delete(client)
    db.session.commit()
    flash("Client supprimé avec succès.", "success")
    return redirect(url_for("liste_clients"))


@app.route("/clients/modifier/<int:id>", methods=["GET", "POST"])
@login_required
def modifier_client(id):
    client = db.session.get(Client, id)
    if client is None:
        flash("Client introuvable.", "danger")
        return redirect(url_for("liste_clients"))

    form = ClientForm(obj=client)

    if form.validate_on_submit():
        autre_client = Client.query.filter_by(email=form.email.data).first() if form.email.data else None
        if autre_client and autre_client.id != client.id:
            flash("Un autre client existe déjà avec cet email.", "danger")
        else:
            client.nom = form.nom.data
            client.prenom = form.prenom.data
            client.email = form.email.data
            client.telephone = form.telephone.data
            client.adresse = form.adresse.data
            db.session.commit()
            flash("Client modifié avec succès.", "success")
            return redirect(url_for("liste_clients"))

    return render_template("modifier_client.html", form=form)


@app.route("/produits")
@login_required
def liste_produits():
    produits = Produit.query.order_by(Produit.nom).all()
    return render_template("produits.html", produits=produits)


@app.route("/produits/ajouter", methods=["GET", "POST"])
@login_required
def ajouter_produit():
    form = ProduitForm()

    if form.validate_on_submit():
        produit = Produit(
            nom=form.nom.data,
            categorie=form.categorie.data,
            prix=form.prix.data,
            quantite=form.quantite.data,
            description=form.description.data,
        )
        db.session.add(produit)
        db.session.commit()
        flash("Produit ajouté avec succès.", "success")
        return redirect(url_for("liste_produits"))

    return render_template("ajouter_produit.html", form=form)


@app.route("/produits/modifier/<int:id>", methods=["GET", "POST"])
@login_required
def modifier_produit(id):
    produit = db.session.get(Produit, id)
    if produit is None:
        flash("Produit introuvable.", "danger")
        return redirect(url_for("liste_produits"))

    form = ProduitForm(obj=produit)

    if form.validate_on_submit():
        produit.nom = form.nom.data
        produit.categorie = form.categorie.data
        produit.prix = form.prix.data
        produit.quantite = form.quantite.data
        produit.description = form.description.data
        db.session.commit()
        flash("Produit modifié avec succès.", "success")
        return redirect(url_for("liste_produits"))

    return render_template("modifier_produit.html", form=form)


@app.route("/produits/supprimer/<int:id>", methods=["POST"])
@login_required
@administrateur_requis
def supprimer_produit(id):
    produit = db.session.get(Produit, id)
    if produit is None:
        flash("Produit introuvable.", "danger")
        return redirect(url_for("liste_produits"))

    deja_facture = DetailFacture.query.filter_by(produit_id=id).first()
    if deja_facture is not None:
        flash(
            "Impossible de supprimer ce produit : il apparaît sur au moins une facture.",
            "danger",
        )
        return redirect(url_for("liste_produits"))

    db.session.delete(produit)
    db.session.commit()
    flash("Produit supprimé.", "success")
    return redirect(url_for("liste_produits"))


@app.route("/factures")
@login_required
def liste_factures():
    toutes_les_factures = Facture.query.order_by(Facture.id.desc()).all()

    total_facture = sum((f.total or Decimal("0")) for f in toutes_les_factures)
    total_paye = sum((f.total or Decimal("0")) for f in toutes_les_factures if f.statut == "payee")
    nb_attente = sum(1 for f in toutes_les_factures if f.statut == "attente")
    nb_envoyees = sum(1 for f in toutes_les_factures if f.envoyee)
    nb_payees = sum(1 for f in toutes_les_factures if f.statut == "payee")

    filtre_statut = request.args.get("statut", "")
    if filtre_statut in STATUTS_FACTURE:
        factures = [f for f in toutes_les_factures if f.statut == filtre_statut]
    else:
        filtre_statut = ""
        factures = toutes_les_factures

    return render_template(
        "facture.html",
        factures=factures,
        total_facture=total_facture,
        total_paye=total_paye,
        nb_attente=nb_attente,
        nb_envoyees=nb_envoyees,
        nb_payees=nb_payees,
        nb_toutes=len(toutes_les_factures),
        filtre_statut=filtre_statut,
    )


def choix_produits():
    return [(0, "— Sélectionner un produit —")] + [
        (p.id, f"{p.nom} — {p.prix} DH (stock : {p.quantite})")
        for p in Produit.query.order_by(Produit.nom)
    ]


def ajouter_ligne_facture(facture, produit_id, quantite):
    """Ajoute une ligne produit a une facture en verifiant et decrementant le
    stock de maniere atomique. Retourne (succes, message)."""
    produit = db.session.get(Produit, produit_id)

    if produit is None:
        return False, "Produit introuvable."
    if quantite <= 0:
        return False, "La quantité doit être supérieure à 0."

    # Decrement conditionne au stock disponible dans la meme requete SQL,
    # pour eviter une survente en cas d'acces concurrent.
    resultat = db.session.execute(
        db.update(Produit)
        .where(Produit.id == produit.id, Produit.quantite >= quantite)
        .values(quantite=Produit.quantite - quantite)
    )

    if resultat.rowcount == 0:
        db.session.rollback()
        db.session.refresh(produit)
        return False, f"Stock insuffisant pour « {produit.nom} » (disponible : {produit.quantite})."

    ligne = DetailFacture(
        facture_id=facture.id,
        produit_id=produit.id,
        quantite=quantite,
        prix_unitaire=produit.prix,
    )
    db.session.add(ligne)
    facture.total = (facture.total or Decimal("0")) + (produit.prix * quantite)
    db.session.commit()
    return True, f"« {produit.nom} » ajouté à la facture."


@app.route("/factures/ajouter", methods=["GET", "POST"])
@login_required
def ajouter_facture():
    form = FactureForm()
    form.client.choices = [
        (c.id, f"{c.nom} {c.prenom}")
        for c in Client.query.order_by(Client.nom)
    ]
    for entree in form.lignes:
        entree.produit.choices = choix_produits()

    if form.validate_on_submit():
        facture = Facture(client_id=form.client.data, statut=form.statut.data)
        db.session.add(facture)
        db.session.commit()

        for entree in form.lignes.data:
            produit_id = entree.get("produit") or 0
            quantite = entree.get("quantite") or 0
            if produit_id and quantite:
                ok, message = ajouter_ligne_facture(facture, produit_id, quantite)
                if not ok:
                    flash(message, "danger")

        flash("Facture créée avec succès.", "success")
        return redirect(url_for("detail_facture", id=facture.id))

    return render_template("ajouter_facture.html", form=form)


@app.route("/rapports")
@login_required
def rapports():
    chiffre_affaires_total = db.session.query(
        db.func.coalesce(db.func.sum(Facture.total), 0)
    ).scalar()

    total_paye = db.session.query(
        db.func.coalesce(db.func.sum(Facture.total), 0)
    ).filter(Facture.statut == "payee").scalar()

    nb_factures = Facture.query.count()

    lignes_facture = db.session.query(
        db.func.strftime("%Y-%m", Facture.date).label("mois"),
        db.func.sum(Facture.total).label("total"),
    ).group_by("mois").order_by("mois").all()

    lignes_payee = db.session.query(
        db.func.strftime("%Y-%m", Facture.date).label("mois"),
        db.func.sum(Facture.total).label("total"),
    ).filter(Facture.statut == "payee").group_by("mois").order_by("mois").all()

    totaux_payee_par_mois = {l.mois: float(l.total or 0) for l in lignes_payee}
    maximum = max([float(l.total or 0) for l in lignes_facture], default=0) or 1

    barres = []
    for ligne in lignes_facture:
        valeur_facture = float(ligne.total or 0)
        valeur_payee = totaux_payee_par_mois.get(ligne.mois, 0)
        barres.append({
            "label": MOIS_FR.get(ligne.mois[5:7], ligne.mois) if ligne.mois else "?",
            "facture": valeur_facture,
            "payee": valeur_payee,
            "pct_facture": round(valeur_facture / maximum * 100, 1),
            "pct_payee": round(valeur_payee / maximum * 100, 1),
        })

    # Factures payees groupees par mois (repartition affichee en bas de page)
    factures_payees = Facture.query.filter_by(statut="payee").order_by(Facture.date.desc()).all()
    groupes = {}
    for f in factures_payees:
        cle = f.date.strftime("%Y-%m") if f.date else "?"
        groupes.setdefault(cle, []).append(f)

    repartition_payees = []
    for cle in sorted(groupes.keys(), reverse=True):
        factures_du_mois = groupes[cle]
        libelle = f"{MOIS_FR.get(cle[5:7], cle)} {cle[:4]}" if cle != "?" else "Date inconnue"
        repartition_payees.append({
            "mois": libelle,
            "factures": factures_du_mois,
            "total": sum((f.total or Decimal("0")) for f in factures_du_mois),
        })

    return render_template(
        "rapports.html",
        chiffre_affaires_total=chiffre_affaires_total,
        total_paye=total_paye,
        nb_factures=nb_factures,
        barres=barres,
        repartition_payees=repartition_payees,
    )


def obtenir_facture_ou_rediriger(id):
    """Recupere une facture (cote personnel) par id, ou renvoie directement
    une reponse de redirection avec un message "introuvable" vers la liste
    des factures. Usage : `facture, reponse = obtenir_facture_ou_rediriger(id)`
    puis `if reponse: return reponse`. Factorise un motif identique repete
    sur toutes les routes personnel qui operent sur une facture existante."""
    facture = db.session.get(Facture, id)
    if facture is None:
        flash("Facture introuvable.", "danger")
        return None, redirect(url_for("liste_factures"))
    return facture, None


@app.route("/factures/<int:id>", methods=["GET", "POST"])
@login_required
def detail_facture(id):
    facture, reponse = obtenir_facture_ou_rediriger(id)
    if reponse:
        return reponse

    form = LigneFactureForm()
    form.produit.choices = [
        (p.id, f"{p.nom} — {p.prix} DH (stock : {p.quantite})")
        for p in Produit.query.order_by(Produit.nom)
    ]

    if form.validate_on_submit():
        ok, message = ajouter_ligne_facture(facture, form.produit.data, form.quantite.data)
        flash(message, "success" if ok else "danger")
        return redirect(url_for("detail_facture", id=facture.id))

    statut_form = StatutFactureForm(statut=facture.statut)
    paiement_form = PaiementForm()

    return render_template(
        "facture_detail.html",
        facture=facture,
        form=form,
        statut_form=statut_form,
        paiement_form=paiement_form,
    )


@app.route("/factures/<int:facture_id>/lignes/supprimer/<int:ligne_id>", methods=["POST"])
@login_required
def supprimer_ligne_facture(facture_id, ligne_id):
    ligne = db.session.get(DetailFacture, ligne_id)

    if ligne is None or ligne.facture_id != facture_id:
        flash("Ligne introuvable.", "danger")
        return redirect(url_for("detail_facture", id=facture_id))

    facture = ligne.facture

    if ligne.produit_id is not None:
        db.session.execute(
            db.update(Produit)
            .where(Produit.id == ligne.produit_id)
            .values(quantite=Produit.quantite + ligne.quantite)
        )

    facture.total = (facture.total or Decimal("0")) - (ligne.prix_unitaire * ligne.quantite)
    if facture.total < 0:
        facture.total = Decimal("0")

    db.session.delete(ligne)
    db.session.commit()
    flash("Ligne supprimée de la facture.", "success")
    return redirect(url_for("detail_facture", id=facture_id))


@app.route("/factures/<int:id>/statut", methods=["POST"])
@login_required
def changer_statut_facture(id):
    facture, reponse = obtenir_facture_ou_rediriger(id)
    if reponse:
        return reponse

    form = StatutFactureForm()
    if form.validate_on_submit():
        facture.statut = form.statut.data
        db.session.commit()
        flash("Statut de la facture mis à jour.", "success")
    else:
        flash("Statut invalide.", "danger")

    return redirect(url_for("detail_facture", id=id))


@app.route("/factures/<int:id>/marquer-envoyee", methods=["POST"])
@login_required
def marquer_facture_envoyee(id):
    facture, reponse = obtenir_facture_ou_rediriger(id)
    if reponse:
        return reponse

    facture.envoyee = True
    facture.date_envoi = db.func.now()
    db.session.commit()
    flash(f"Facture {facture.numero} marquée comme envoyée au client.", "success")
    return redirect(url_for("detail_facture", id=id))


def enregistrer_paiement(facture, montant, methode, reference=None):
    """Enregistre un reglement sur une facture et met a jour son statut si le
    montant total est atteint. Retourne le Paiement cree."""
    paiement = Paiement(
        facture_id=facture.id,
        montant=montant,
        methode=methode,
        reference=reference or None,
    )
    db.session.add(paiement)
    db.session.commit()

    total_regle = sum((p.montant for p in facture.paiements), Decimal("0"))
    if facture.total and total_regle >= facture.total and facture.statut != "annulee":
        facture.statut = "payee"
        db.session.commit()

    return paiement


@app.route("/factures/<int:id>/paiements/ajouter", methods=["POST"])
@login_required
def ajouter_paiement(id):
    facture, reponse = obtenir_facture_ou_rediriger(id)
    if reponse:
        return reponse

    form = PaiementForm()
    if form.validate_on_submit():
        if form.montant.data <= 0:
            flash("Le montant réglé doit être supérieur à 0.", "danger")
        else:
            enregistrer_paiement(facture, form.montant.data, form.methode.data, form.reference.data)
            flash("Paiement enregistré avec succès.", "success")
    else:
        flash("Paiement invalide, merci de vérifier les champs.", "danger")

    return redirect(url_for("detail_facture", id=id))


# Mise en page du PDF de facture : marge haut/bas de la page, et taille
# (carree) du logo entreprise s'il est present.
MARGE_PAGE_PDF = 20 * mm
TAILLE_LOGO_PDF = 30 * mm


def generer_pdf_facture(facture):
    """Construit le PDF d'une facture et retourne un BytesIO pret a l'emploi."""
    params = Parametres.obtenir()

    montant_ht = facture.total or Decimal("0")
    taux_tva = Decimal(str(params.taux_tva or 0))
    montant_tva = (montant_ht * taux_tva / Decimal("100")).quantize(Decimal("0.01"))
    montant_ttc = montant_ht + montant_tva

    tampon = BytesIO()
    document = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        topMargin=MARGE_PAGE_PDF,
        bottomMargin=MARGE_PAGE_PDF,
    )
    styles = getSampleStyleSheet()
    elements = []

    if params.logo:
        chemin_logo = os.path.join(app.root_path, "static", "uploads", params.logo)
        if os.path.exists(chemin_logo):
            elements.append(Image(chemin_logo, width=TAILLE_LOGO_PDF, height=TAILLE_LOGO_PDF))
            elements.append(Spacer(1, 8))

    elements.append(Paragraph(f"<b>{params.nom_entreprise or 'KBTO'}</b>", styles["Title"]))
    infos_entreprise = " · ".join(filter(None, [
        f"IF : {params.identifiant_fiscal}" if params.identifiant_fiscal else None,
        params.adresse,
        params.telephone,
        params.email,
    ]))
    if infos_entreprise:
        elements.append(Paragraph(infos_entreprise, styles["Normal"]))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph(f"<b>Facture {facture.numero}</b>", styles["Heading2"]))
    elements.append(Paragraph(
        f"Date : {facture.date.strftime('%d/%m/%Y') if facture.date else '-'}",
        styles["Normal"],
    ))
    if facture.client:
        infos_client = f"Client : {facture.client.nom} {facture.client.prenom}"
        if facture.client.email:
            infos_client += f" — {facture.client.email}"
        elements.append(Paragraph(infos_client, styles["Normal"]))
    elements.append(Spacer(1, 16))

    donnees = [["Produit", "Quantité", "Prix unitaire", "Sous-total"]]
    for ligne in facture.details:
        donnees.append([
            ligne.produit.nom if ligne.produit else "-",
            str(ligne.quantite),
            f"{ligne.prix_unitaire:.2f} DH",
            f"{(ligne.prix_unitaire * ligne.quantite):.2f} DH",
        ])

    tableau = Table(donnees, colWidths=[70 * mm, 25 * mm, 35 * mm, 35 * mm])
    tableau.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F1B2D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
    ]))
    elements.append(tableau)
    elements.append(Spacer(1, 16))

    totaux = [
        ["Total HT", f"{montant_ht:.2f} DH"],
        [f"TVA ({params.taux_tva or 0:.2f} %)", f"{montant_tva:.2f} DH"],
        ["Total TTC", f"{montant_ttc:.2f} DH"],
    ]
    tableau_totaux = Table(totaux, colWidths=[130 * mm, 35 * mm])
    tableau_totaux.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(tableau_totaux)

    document.build(elements)
    tampon.seek(0)
    return tampon


def envoyer_pdf_facture(facture):
    """Reponse Flask de telechargement du PDF d'une facture (factorise
    l'appel identique fait cote personnel et cote portail client)."""
    return send_file(
        generer_pdf_facture(facture),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{facture.numero}.pdf",
    )


@app.route("/factures/<int:id>/pdf")
@login_required
def facture_pdf(id):
    facture, reponse = obtenir_facture_ou_rediriger(id)
    if reponse:
        return reponse

    return envoyer_pdf_facture(facture)


# ==========================
# Profil (compte + parametres entreprise pour l'admin)
# ==========================
@app.route("/profil", methods=["GET", "POST"])
@login_required
def profil():
    compte_form = ProfilForm(obj=current_user)

    if compte_form.validate_on_submit():
        nom_utilisateur = compte_form.nom_utilisateur.data.strip().lower()
        email = compte_form.email.data.strip().lower()

        conflit_nom = Utilisateur.query.filter_by(nom_utilisateur=nom_utilisateur).first()
        conflit_email = Utilisateur.query.filter_by(email=email).first()

        if conflit_nom and conflit_nom.id != current_user.id:
            flash("Ce nom d'utilisateur existe déjà.", "danger")
        elif conflit_email and conflit_email.id != current_user.id:
            flash("Un utilisateur possède déjà cette adresse email.", "danger")
        elif compte_form.nouveau_mot_de_passe.data and not current_user.verifier_mot_de_passe(
            compte_form.mot_de_passe_actuel.data or ""
        ):
            flash("Mot de passe actuel incorrect.", "danger")
        else:
            current_user.nom_utilisateur = nom_utilisateur
            current_user.nom = compte_form.nom.data.strip()
            current_user.prenom = compte_form.prenom.data.strip()
            current_user.telephone = compte_form.telephone.data
            current_user.email = email
            if compte_form.nouveau_mot_de_passe.data:
                current_user.definir_mot_de_passe(compte_form.nouveau_mot_de_passe.data)
            db.session.commit()
            flash("Profil mis à jour avec succès.", "success")
            return redirect(url_for("profil"))

    return render_template("profil.html", compte_form=compte_form)


# ==========================================================
# PORTAIL CLIENT
# ==========================================================
@app.route("/portail/tableau-de-bord")
@login_required
def portail_tableau_de_bord():
    commandes = Facture.query.filter_by(client_id=current_user.id).order_by(Facture.date.desc()).all()

    nb_commandes = len(commandes)
    montant_total = sum((c.total or Decimal("0")) for c in commandes)
    nb_en_cours = sum(1 for c in commandes if c.statut == "attente")
    nb_impayees = sum(1 for c in commandes if c.statut != "annulee" and c.montant_restant > 0)

    return render_template(
        "portail_dashboard.html",
        nb_commandes=nb_commandes,
        montant_total=montant_total,
        nb_en_cours=nb_en_cours,
        nb_impayees=nb_impayees,
        dernieres_commandes=commandes[:NB_ELEMENTS_TABLEAU_DE_BORD],
    )


@app.route("/portail/produits")
@login_required
def portail_produits():
    recherche = request.args.get("recherche", "")
    produits = Produit.query

    if recherche:
        produits = produits.filter(Produit.nom.contains(recherche))

    produits = produits.order_by(Produit.nom).all()
    return render_template("portail_produits.html", produits=produits, recherche=recherche)


@app.route("/portail/commandes")
@login_required
def portail_commandes():
    commandes = Facture.query.filter_by(client_id=current_user.id).order_by(Facture.date.desc()).all()
    return render_template("portail_commandes.html", commandes=commandes)


@app.route("/portail/commandes/ajouter", methods=["GET", "POST"])
@login_required
def portail_ajouter_commande():
    form = CommandeClientForm()
    for entree in form.lignes:
        entree.produit.choices = choix_produits()

    if form.validate_on_submit():
        if form.mode_paiement.data == "carte":
            flash(
                "Le paiement par carte bancaire n'est pas encore disponible. "
                "Merci de choisir « Chèque » ou « Espèces » pour cette commande, "
                "ou contactez-nous directement.",
                "danger",
            )
            return render_template("portail_ajouter_commande.html", form=form)

        lignes_valides = [
            (entree.get("produit") or 0, entree.get("quantite") or 0)
            for entree in form.lignes.data
        ]
        lignes_valides = [(p, q) for p, q in lignes_valides if p and q]

        if not lignes_valides:
            flash("Veuillez sélectionner au moins un produit.", "danger")
        else:
            commande = Facture(
                client_id=current_user.id,
                statut="attente",
                mode_paiement_prevu=form.mode_paiement.data,
            )
            db.session.add(commande)
            db.session.commit()

            for produit_id, quantite in lignes_valides:
                ok, message = ajouter_ligne_facture(commande, produit_id, quantite)
                if not ok:
                    flash(message, "danger")

            flash(
                f"Commande passée avec succès. Mode de paiement choisi : "
                f"{METHODES_PAIEMENT[form.mode_paiement.data]}. "
                "Notre équipe a été informée.",
                "success",
            )
            return redirect(url_for("portail_detail_facture", id=commande.id))

    return render_template("portail_ajouter_commande.html", form=form)


@app.route("/portail/factures")
@login_required
def portail_factures():
    factures = Facture.query.filter_by(client_id=current_user.id).order_by(Facture.date.desc()).all()
    total_paye = sum((f.total or Decimal("0")) for f in factures if f.statut == "payee")
    total_impaye = sum((f.total or Decimal("0")) for f in factures if f.statut != "payee")

    return render_template(
        "portail_factures.html",
        factures=factures,
        total_paye=total_paye,
        total_impaye=total_impaye,
    )


def obtenir_facture_client_ou_404(id):
    """Recupere une facture appartenant au client connecte, ou leve un 404.
    Facture inexistante et facture d'un autre client renvoient volontairement
    la meme erreur 404 (jamais un message explicite), pour ne pas laisser un
    client deviner quelles factures existent chez d'autres clients. Factorise
    un motif identique repete sur toutes les routes du portail qui operent
    sur une facture existante."""
    facture = db.session.get(Facture, id)
    if facture is None or facture.client_id != current_user.id:
        abort(404)
    return facture


@app.route("/portail/factures/<int:id>")
@login_required
def portail_detail_facture(id):
    facture = obtenir_facture_client_ou_404(id)
    return render_template("portail_facture_detail.html", facture=facture, cle_stripe_configuree=bool(STRIPE_SECRET_KEY))


@app.route("/portail/factures/<int:id>/pdf")
@login_required
def portail_facture_pdf(id):
    facture = obtenir_facture_client_ou_404(id)
    return envoyer_pdf_facture(facture)


def contexte_impression_facture(facture):
    params = Parametres.obtenir()
    montant_ht = facture.total or Decimal("0")
    taux_tva = Decimal(str(params.taux_tva or 0))
    montant_tva = (montant_ht * taux_tva / Decimal("100")).quantize(Decimal("0.01"))
    montant_ttc = montant_ht + montant_tva
    return {
        "facture": facture,
        "params": params,
        "montant_ht": montant_ht,
        "montant_tva": montant_tva,
        "montant_ttc": montant_ttc,
    }


@app.route("/factures/<int:id>/imprimer")
@login_required
def facture_imprimer(id):
    facture, reponse = obtenir_facture_ou_rediriger(id)
    if reponse:
        return reponse
    return render_template("facture_imprimer.html", **contexte_impression_facture(facture))


@app.route("/portail/factures/<int:id>/imprimer")
@login_required
def portail_facture_imprimer(id):
    facture = obtenir_facture_client_ou_404(id)
    return render_template("facture_imprimer.html", **contexte_impression_facture(facture))


@app.route("/portail/paiements")
@login_required
def portail_paiements():
    factures = Facture.query.filter_by(client_id=current_user.id).order_by(Facture.date.desc()).all()
    impayees = [f for f in factures if f.montant_restant > 0 and f.statut != "annulee"]

    paiements = (
        Paiement.query.join(Facture)
        .filter(Facture.client_id == current_user.id)
        .order_by(Paiement.date_paiement.desc())
        .all()
    )

    return render_template(
        "portail_paiements.html",
        impayees=impayees,
        paiements=paiements,
        cle_stripe_configuree=bool(STRIPE_SECRET_KEY),
    )


@app.route("/portail/paiements/payer/<int:id>", methods=["POST"])
@login_required
def portail_payer_facture(id):
    facture = obtenir_facture_client_ou_404(id)

    if facture.montant_restant <= 0:
        flash("Cette facture est déjà payée.", "info")
        return redirect(url_for("portail_paiements"))

    if not STRIPE_SECRET_KEY:
        flash(
            "Le paiement en ligne n'est pas encore configuré. Merci de contacter l'entreprise.",
            "danger",
        )
        return redirect(url_for("portail_paiements"))

    montant_centimes = int(facture.montant_restant * CENTIMES_PAR_DH)

    session_stripe = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "mad",
                "unit_amount": montant_centimes,
                "product_data": {"name": f"Facture {facture.numero}"},
            },
            "quantity": 1,
        }],
        success_url=url_for("portail_paiement_succes", id=facture.id, _external=True)
        + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("portail_paiement_annule", id=facture.id, _external=True),
        metadata={"facture_id": str(facture.id)},
    )
    return redirect(session_stripe.url, code=303)


@app.route("/portail/paiements/succes/<int:id>")
@login_required
def portail_paiement_succes(id):
    facture = obtenir_facture_client_ou_404(id)

    session_id = request.args.get("session_id")
    if session_id and STRIPE_SECRET_KEY:
        # L'unicite de la reference Stripe est verifiee GLOBALEMENT (et non
        # plus seulement pour cette facture) : un session_id Stripe reel et
        # "paid" ne doit jamais pouvoir etre credite plus d'une fois, meme sur
        # des factures differentes appartenant au meme client (rejeu).
        deja_enregistre = Paiement.query.filter_by(reference=session_id, methode="en_ligne").first()
        if deja_enregistre:
            if deja_enregistre.facture_id == facture.id:
                flash(f"Paiement de la facture {facture.numero} déjà confirmé. Merci !", "success")
            else:
                flash(
                    "Cette session de paiement a déjà été utilisée pour une autre facture.",
                    "danger",
                )
        else:
            session_stripe = stripe.checkout.Session.retrieve(session_id)
            # La session Stripe est creee avec metadata={"facture_id": ...} au
            # moment du paiement (cf. portail_payer_facture) : on verifie ici
            # qu'elle correspond bien a la facture demandee dans l'URL, sinon
            # un client pourrait payer une facture A puis rejouer le meme
            # session_id "paid" sur une facture B pour la faire crediter sans
            # paiement reel correspondant.
            facture_id_attendu = (session_stripe.metadata or {}).get("facture_id")
            if facture_id_attendu != str(facture.id):
                flash(
                    "Cette session de paiement ne correspond pas à cette facture.",
                    "danger",
                )
            elif session_stripe.payment_status == "paid":
                montant = Decimal(str(session_stripe.amount_total)) / Decimal(str(CENTIMES_PAR_DH))
                enregistrer_paiement(facture, montant, "en_ligne", session_id)
                flash(f"Paiement de la facture {facture.numero} confirmé. Merci !", "success")
            else:
                flash("Le paiement n'a pas pu être confirmé.", "danger")

    return redirect(url_for("portail_paiements"))


@app.route("/portail/paiements/annule/<int:id>")
@login_required
def portail_paiement_annule(id):
    facture = obtenir_facture_client_ou_404(id)
    flash("Paiement annulé.", "info")
    return redirect(url_for("portail_paiements"))


@app.route("/portail/profil", methods=["GET", "POST"])
@login_required
def portail_profil():
    form = ProfilClientForm(obj=current_user)

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        conflit = Client.query.filter_by(email=email).first()

        if conflit and conflit.id != current_user.id:
            flash("Un autre compte existe déjà avec cet email.", "danger")
        elif form.nouveau_mot_de_passe.data and not current_user.verifier_mot_de_passe(
            form.mot_de_passe_actuel.data or ""
        ):
            flash("Mot de passe actuel incorrect.", "danger")
        else:
            current_user.nom = form.nom.data.strip()
            current_user.prenom = form.prenom.data.strip()
            current_user.telephone = form.telephone.data
            current_user.adresse = form.adresse.data
            current_user.email = email
            if form.nouveau_mot_de_passe.data:
                current_user.definir_mot_de_passe(form.nouveau_mot_de_passe.data)
            db.session.commit()
            flash("Profil mis à jour avec succès.", "success")
            return redirect(url_for("portail_profil"))

    return render_template("portail_profil.html", form=form)


# ==========================================================
# ASSISTANT DU PORTAIL CLIENT (FAQ locale a base de mots-cles)
# ==========================================================
# Aucun appel a une API externe : le moteur cherche un mot-cle dans le
# message et renvoie la reponse associee, construite a partir des vraies
# donnees de l'entreprise (catalogue, coordonnees). Gratuit et illimite,
# mais limite aux sujets prevus ci-dessous -- contrairement a une IA
# generative, il ne comprend pas les questions formulees autrement.
LONGUEUR_MAX_MESSAGE_CHATBOT = 500

# Anti-abus (protection basique contre le spam, meme structure que le
# verrouillage anti brute-force de /connexion plus haut) : scope par client
# connecte plutot que par identifiant de connexion.
LIMITE_MESSAGES_CHATBOT = 20
FENETRE_CHATBOT = timedelta(minutes=10)
_messages_chatbot_par_client = {}


def _chatbot_est_limite(client_id):
    entree = _messages_chatbot_par_client.get(client_id)
    if entree is None:
        return False
    nb_messages, premier_message = entree
    if datetime.now(timezone.utc) - premier_message > FENETRE_CHATBOT:
        _messages_chatbot_par_client.pop(client_id, None)
        return False
    return nb_messages >= LIMITE_MESSAGES_CHATBOT


def _enregistrer_message_chatbot(client_id):
    maintenant = datetime.now(timezone.utc)
    entree = _messages_chatbot_par_client.get(client_id)
    if entree is None or maintenant - entree[1] > FENETRE_CHATBOT:
        _messages_chatbot_par_client[client_id] = (1, maintenant)
    else:
        _messages_chatbot_par_client[client_id] = (entree[0] + 1, entree[1])


REPONSE_CHATBOT_PAR_DEFAUT = (
    "Désolé, je n'ai pas compris votre question. Voici les sujets que je "
    "connais : tarifs, prestations, paiement, commandes, factures, contact."
)


def _entrees_faq_chatbot():
    """Construit les entrees de la FAQ a partir des vraies donnees de
    l'entreprise (catalogue, coordonnees) : uniquement des informations
    generales et publiques, jamais des donnees personnelles de client."""
    params = Parametres.obtenir()
    produits = Produit.query.all()
    categories = sorted({p.categorie for p in produits if p.categorie})
    prix = [p.prix for p in produits if p.prix is not None]
    fourchette_prix = (
        f"de {min(prix):.0f} DH à {max(prix):.0f} DH selon la prestation"
        if prix else "détaillés dans notre catalogue"
    )
    liste_categories = ", ".join(categories) if categories else (
        "comptabilité, fiscalité, social et paie, conseil aux entreprises"
    )

    return [
        {
            "mots_cles": ["bonjour", "salut", "bonsoir", "hello", "coucou"],
            "reponse": (
                "Bonjour ! Je peux répondre à vos questions sur nos tarifs, nos "
                "prestations, le paiement, les commandes ou nos coordonnées."
            ),
        },
        {
            "mots_cles": ["merci", "parfait", "super"],
            "reponse": "Avec plaisir ! N'hésitez pas si vous avez d'autres questions.",
        },
        {
            # "combien" seul est trop generique (declenche sur "combien de
            # temps", "combien pese"...) : on ne le garde que combine avec
            # une notion de cout.
            "mots_cles": [
                "tarif", "prix", "coute", "coûte", "cout", "coût",
                "combien ça coûte", "combien ca coute", "combien coûte", "combien coute",
            ],
            "reponse": (
                f"Nos tarifs varient {fourchette_prix}. Vous trouverez le détail "
                "complet et à jour dans l'onglet Catalogue."
            ),
        },
        {
            "mots_cles": ["service", "prestation", "catalogue", "propose", "offre", "offrez"],
            "reponse": (
                f"Nous proposons des prestations en {liste_categories}. Le détail "
                "complet est disponible dans l'onglet Catalogue."
            ),
        },
        {
            "mots_cles": [
                "paiement", "payer", "regler", "régler",
                "cheque", "chèque", "espece", "espèce", "carte",
            ],
            "reponse": (
                "Vous pouvez régler par chèque ou en espèces en choisissant votre "
                "mode de paiement lors de votre commande. Le paiement par carte "
                "bancaire n'est pas encore disponible en ligne. L'historique de vos "
                "règlements est visible dans l'onglet Paiements."
            ),
        },
        {
            "mots_cles": ["commande", "commander", "reserver", "réserver"],
            "reponse": (
                "Pour passer une commande, rendez-vous dans l'onglet Commandes > "
                "Nouvelle commande, sélectionnez les prestations souhaitées et "
                "choisissez votre mode de paiement."
            ),
        },
        {
            "mots_cles": ["facture", "recu", "reçu"],
            "reponse": (
                "Vous pouvez consulter, télécharger ou imprimer vos factures depuis "
                "l'onglet Factures de votre espace client."
            ),
        },
        {
            "mots_cles": [
                "contact", "telephone", "téléphone", "email",
                "adresse", "joindre", "horaire",
            ],
            "reponse": (
                f"Vous pouvez nous contacter au "
                f"{params.telephone or 'numéro indiqué sur notre site'}, par email à "
                f"{params.email or 'notre adresse de contact'}, ou à notre adresse : "
                f"{params.adresse or 'voir nos coordonnées'}."
            ),
        },
    ]


def repondre_chatbot_faq(message_utilisateur):
    """Cherche la premiere entree de la FAQ dont un mot-cle apparait dans le
    message (normalise en minuscules), ou renvoie un message de secours si
    aucune entree ne correspond."""
    message_normalise = message_utilisateur.lower()
    for entree in _entrees_faq_chatbot():
        if any(mot in message_normalise for mot in entree["mots_cles"]):
            return entree["reponse"]
    return REPONSE_CHATBOT_PAR_DEFAUT


@app.route("/portail/assistant/message", methods=["POST"])
@login_required
def portail_assistant_message():
    if _chatbot_est_limite(current_user.id):
        return jsonify({
            "reponse": "Vous avez envoyé beaucoup de messages récemment. Merci de "
                       "patienter quelques minutes avant de continuer la conversation.",
        })

    donnees = request.get_json(silent=True) or {}
    message_utilisateur = (donnees.get("message") or "").strip()
    if not message_utilisateur:
        return jsonify({"erreur": "Message vide."}), 400
    message_utilisateur = message_utilisateur[:LONGUEUR_MAX_MESSAGE_CHATBOT]

    _enregistrer_message_chatbot(current_user.id)

    return jsonify({"reponse": repondre_chatbot_faq(message_utilisateur)})


if __name__ == "__main__":
    # Mode debug desactive par defaut (fail-safe) : le debogueur Werkzeug
    # permet l'execution de code arbitraire (RCE) et affiche le code source
    # et les variables d'environnement dans les tracebacks s'il est expose
    # publiquement. Pour le developpement local, ajouter FLASK_DEBUG=1 dans
    # .env. Rappel (voir README) : `python app.py` est un serveur de
    # developpement, jamais a utiliser tel quel en production (serveur WSGI
    # requis, ex. gunicorn/waitress).
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")