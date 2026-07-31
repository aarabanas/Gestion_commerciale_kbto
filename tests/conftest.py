import os

# Doit etre fixe AVANT l'import de app.py : Flask-SQLAlchemy fige l'URI de la
# base au moment de db.init_app(app), une modification tardive de
# app.config["SQLALCHEMY_DATABASE_URI"] n'a aucun effet et les tests
# finiraient par utiliser (et vider) la vraie base du projet.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest

import app as app_module
from app import app as flask_app
from models import Client, Facture, Produit, Utilisateur, db


@pytest.fixture()
def app():
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SERVER_NAME="localhost",
    )

    with flask_app.app_context():
        assert "gestion_commerciale.db" not in str(db.engine.url), (
            "les tests ne doivent jamais tourner sur le fichier de base reel"
        )
        db.create_all()
        # Le compteur anti brute-force de /connexion vit en memoire de
        # processus (cf. app.py) : le reinitialiser avant chaque test evite
        # qu'un test qui enchaine des echecs de connexion sur un identifiant
        # ne fasse "deborder" un verrouillage sur un autre test independant.
        app_module._tentatives_echouees_connexion.clear()
        # Meme principe pour le compteur anti-abus du chatbot du portail.
        app_module._messages_chatbot_par_client.clear()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def utilisateur(app):
    u = Utilisateur(
        nom_utilisateur="admin",
        nom="Admin",
        prenom="Test",
        email="admin@example.com",
        role="administrateur",
    )
    u.definir_mot_de_passe("motdepasse123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def employe(app):
    u = Utilisateur(
        nom_utilisateur="employe1",
        nom="Employe",
        prenom="Test",
        email="employe1@example.com",
        role="employe",
    )
    u.definir_mot_de_passe("motdepasse123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def connecte_employe(app, employe):
    # Client dedie (et non le fixture `client` partage) : si un test utilise
    # a la fois `connecte` et `connecte_employe`, ils ne doivent pas ecraser
    # la meme session/cookie en se connectant tour a tour sur le meme client.
    client_employe = app.test_client()
    client_employe.post(
        "/connexion",
        data={"nom_utilisateur": "employe1", "mot_de_passe": "motdepasse123"},
        follow_redirects=True,
    )
    return client_employe


@pytest.fixture()
def connecte(app, utilisateur):
    client_admin = app.test_client()
    client_admin.post(
        "/connexion",
        data={"nom_utilisateur": "admin", "mot_de_passe": "motdepasse123"},
        follow_redirects=True,
    )
    return client_admin


@pytest.fixture()
def un_client(app):
    c = Client(nom="Bennani", prenom="Yassine", email="yassine@example.com")
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture()
def client_avec_compte(app):
    c = Client(nom="Fassi", prenom="Karim", email="karim@example.com")
    c.definir_mot_de_passe("motdepasse123")
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture()
def connecte_client(app, client_avec_compte):
    client_portail = app.test_client()
    client_portail.post(
        "/connexion",
        data={"nom_utilisateur": "karim@example.com", "mot_de_passe": "motdepasse123"},
        follow_redirects=True,
    )
    return client_portail


@pytest.fixture()
def un_produit(app):
    p = Produit(nom="Clavier", prix=100, quantite=10, description="Clavier mecanique", categorie="Périphériques")
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture()
def une_facture(app, un_client):
    f = Facture(client_id=un_client.id)
    db.session.add(f)
    db.session.commit()
    return f
