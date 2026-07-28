from decimal import Decimal

from models import DetailFacture, Facture, Produit, db


def _donnees_commande(produit_id, quantite):
    donnees = {
        "lignes-0-produit": produit_id,
        "lignes-0-quantite": quantite,
    }
    for i in range(1, 5):
        donnees[f"lignes-{i}-produit"] = 0
        donnees[f"lignes-{i}-quantite"] = 1
    return donnees


def test_client_passe_une_commande(connecte_client, client_avec_compte, un_produit):
    reponse = connecte_client.post(
        "/portail/commandes/ajouter",
        data=_donnees_commande(un_produit.id, 2),
        follow_redirects=True,
    )
    assert reponse.status_code == 200

    commande = Facture.query.filter_by(client_id=client_avec_compte.id).first()
    assert commande is not None
    assert commande.statut == "attente"
    assert commande.total == Decimal("200.00")

    produit = db.session.get(Produit, un_produit.id)
    assert produit.quantite == 8


def test_commande_sans_ligne_refusee(connecte_client, client_avec_compte):
    donnees = {}
    for i in range(5):
        donnees[f"lignes-{i}-produit"] = 0
        donnees[f"lignes-{i}-quantite"] = 1

    connecte_client.post("/portail/commandes/ajouter", data=donnees, follow_redirects=True)

    assert Facture.query.filter_by(client_id=client_avec_compte.id).count() == 0


def test_client_ne_voit_pas_les_factures_dun_autre_client(connecte_client, une_facture):
    # `une_facture` appartient au fixture `un_client`, pas a `client_avec_compte`
    reponse = connecte_client.get(f"/portail/factures/{une_facture.id}")
    assert reponse.status_code == 404


def test_client_voit_sa_propre_facture(connecte_client, client_avec_compte, un_produit):
    connecte_client.post(
        "/portail/commandes/ajouter",
        data=_donnees_commande(un_produit.id, 1),
        follow_redirects=True,
    )
    commande = Facture.query.filter_by(client_id=client_avec_compte.id).first()

    reponse = connecte_client.get(f"/portail/factures/{commande.id}")
    assert reponse.status_code == 200
    assert un_produit.nom in reponse.get_data(as_text=True)


def test_client_ne_peut_pas_telecharger_pdf_dun_autre(connecte_client, une_facture):
    reponse = connecte_client.get(f"/portail/factures/{une_facture.id}/pdf")
    assert reponse.status_code == 404


def test_client_ne_peut_pas_imprimer_facture_dun_autre(connecte_client, une_facture):
    reponse = connecte_client.get(f"/portail/factures/{une_facture.id}/imprimer")
    assert reponse.status_code == 404
