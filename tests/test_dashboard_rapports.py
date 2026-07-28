from decimal import Decimal

from models import Facture, db


def test_tableau_de_bord_saffiche_avec_donnees(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 2},
        follow_redirects=True,
    )

    reponse = connecte.get("/tableau-de-bord")
    assert reponse.status_code == 200

    contenu = reponse.get_data(as_text=True)
    assert "Objectif du mois" in contenu
    assert un_produit.categorie in contenu


def test_tableau_de_bord_sans_donnees_ne_plante_pas(connecte):
    reponse = connecte.get("/tableau-de-bord")
    assert reponse.status_code == 200


def test_rapports_regroupe_les_factures_payees_par_mois(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 1},
        follow_redirects=True,
    )
    connecte.post(
        f"/factures/{une_facture.id}/statut",
        data={"statut": "payee"},
        follow_redirects=True,
    )

    reponse = connecte.get("/rapports")
    assert reponse.status_code == 200

    facture = db.session.get(Facture, une_facture.id)
    assert facture.statut == "payee"
    assert facture.total == Decimal("100.00")

    contenu = reponse.get_data(as_text=True)
    assert facture.numero in contenu
