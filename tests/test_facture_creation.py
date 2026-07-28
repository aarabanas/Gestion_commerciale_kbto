from decimal import Decimal

from models import DetailFacture, Facture, Produit, db


def _donnees_creation(client_id, statut="attente", produit_id=0, quantite=1):
    donnees = {
        "client": client_id,
        "statut": statut,
        "lignes-0-produit": produit_id,
        "lignes-0-quantite": quantite,
    }
    for i in range(1, 5):
        donnees[f"lignes-{i}-produit"] = 0
        donnees[f"lignes-{i}-quantite"] = 1
    return donnees


def test_creation_facture_avec_statut_et_ligne_produit(connecte, un_client, un_produit):
    donnees = _donnees_creation(un_client.id, statut="payee", produit_id=un_produit.id, quantite=2)
    reponse = connecte.post("/factures/ajouter", data=donnees, follow_redirects=True)
    assert reponse.status_code == 200

    facture = Facture.query.filter_by(client_id=un_client.id).first()
    assert facture is not None
    assert facture.statut == "payee"
    assert facture.total == Decimal("200.00")

    produit = db.session.get(Produit, un_produit.id)
    assert produit.quantite == 8

    ligne = DetailFacture.query.filter_by(facture_id=facture.id).first()
    assert ligne is not None
    assert ligne.quantite == 2


def test_creation_facture_sans_ligne(connecte, un_client):
    donnees = _donnees_creation(un_client.id)
    connecte.post("/factures/ajouter", data=donnees, follow_redirects=True)

    facture = Facture.query.filter_by(client_id=un_client.id).first()
    assert facture is not None
    assert facture.total == Decimal("0")
    assert DetailFacture.query.filter_by(facture_id=facture.id).count() == 0


def test_creation_facture_ligne_stock_insuffisant_facture_quand_meme_creee(connecte, un_client, un_produit):
    donnees = _donnees_creation(un_client.id, produit_id=un_produit.id, quantite=999)
    connecte.post("/factures/ajouter", data=donnees, follow_redirects=True)

    facture = Facture.query.filter_by(client_id=un_client.id).first()
    assert facture is not None
    assert facture.total == Decimal("0")

    produit = db.session.get(Produit, un_produit.id)
    assert produit.quantite == 10
    assert DetailFacture.query.filter_by(facture_id=facture.id).count() == 0


def test_facture_non_envoyee_par_defaut(une_facture):
    assert une_facture.envoyee is False
    assert une_facture.date_envoi is None


def test_marquer_facture_envoyee(connecte, une_facture):
    reponse = connecte.post(f"/factures/{une_facture.id}/marquer-envoyee", follow_redirects=True)
    assert reponse.status_code == 200

    facture = db.session.get(Facture, une_facture.id)
    assert facture.envoyee is True
    assert facture.date_envoi is not None
