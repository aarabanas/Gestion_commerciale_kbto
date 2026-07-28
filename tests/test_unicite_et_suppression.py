from models import Client, DetailFacture, Produit, Utilisateur, db


def test_email_client_unique(connecte):
    donnees = {
        "nom": "Alami",
        "prenom": "Sara",
        "email": "sara@example.com",
        "telephone": "",
        "adresse": "",
    }
    connecte.post("/clients/ajouter", data=donnees, follow_redirects=True)
    connecte.post("/clients/ajouter", data=donnees, follow_redirects=True)

    assert Client.query.filter_by(email="sara@example.com").count() == 1


def test_email_utilisateur_unique_via_creer_admin(app):
    runner = app.test_cli_runner()
    args = [
        "creer-admin",
        "--nom-utilisateur", "jdupont",
        "--nom", "Dupont",
        "--prenom", "Jean",
        "--email", "jean@example.com",
        "--mot-de-passe", "motdepasse123",
    ]
    runner.invoke(args=args)
    runner.invoke(args=[
        "creer-admin",
        "--nom-utilisateur", "jdupont2",
        "--nom", "Dupont",
        "--prenom", "Jean",
        "--email", "jean@example.com",
        "--mot-de-passe", "autremotdepasse",
    ])

    assert Utilisateur.query.filter_by(email="jean@example.com").count() == 1


def test_creer_admin_force_le_role_administrateur(app):
    runner = app.test_cli_runner()
    runner.invoke(args=[
        "creer-admin",
        "--nom-utilisateur", "chef",
        "--nom", "Chef",
        "--prenom", "Grand",
        "--email", "chef@example.com",
        "--mot-de-passe", "motdepasse123",
    ])

    utilisateur = Utilisateur.query.filter_by(nom_utilisateur="chef").first()
    assert utilisateur is not None
    assert utilisateur.role == "administrateur"


def test_suppression_client_avec_facture_refusee(connecte, une_facture, un_client):
    reponse = connecte.post(f"/clients/supprimer/{un_client.id}", follow_redirects=True)

    assert reponse.status_code == 200
    assert db.session.get(Client, un_client.id) is not None


def test_suppression_produit_reference_refusee(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 1},
        follow_redirects=True,
    )
    assert DetailFacture.query.filter_by(produit_id=un_produit.id).count() == 1

    connecte.post(f"/produits/supprimer/{un_produit.id}", follow_redirects=True)

    assert db.session.get(Produit, un_produit.id) is not None


def test_suppression_produit_non_reference_autorisee(connecte, un_produit):
    connecte.post(f"/produits/supprimer/{un_produit.id}", follow_redirects=True)

    assert db.session.get(Produit, un_produit.id) is None


def test_suppression_en_get_refusee(connecte, un_client):
    reponse = connecte.get(f"/clients/supprimer/{un_client.id}")
    assert reponse.status_code == 405

