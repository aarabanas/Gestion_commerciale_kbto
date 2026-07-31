from decimal import Decimal

from models import Facture, Paiement, db


def test_paiement_partiel_ne_solde_pas_la_facture(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 4},
        follow_redirects=True,
    )
    facture = db.session.get(Facture, une_facture.id)
    assert facture.total == Decimal("400.00")

    connecte.post(
        f"/factures/{facture.id}/paiements/ajouter",
        data={"montant": "150.00", "methode": "espece", "reference": ""},
        follow_redirects=True,
    )

    facture = db.session.get(Facture, une_facture.id)
    assert facture.statut == "attente"
    assert facture.montant_paye == Decimal("150.00")
    assert facture.montant_restant == Decimal("250.00")


def test_paiement_complet_passe_la_facture_a_payee(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 2},
        follow_redirects=True,
    )
    facture = db.session.get(Facture, une_facture.id)
    assert facture.total == Decimal("200.00")

    connecte.post(
        f"/factures/{facture.id}/paiements/ajouter",
        data={"montant": "120.00", "methode": "cheque", "reference": "CHQ-001"},
        follow_redirects=True,
    )
    connecte.post(
        f"/factures/{facture.id}/paiements/ajouter",
        data={"montant": "80.00", "methode": "carte", "reference": ""},
        follow_redirects=True,
    )

    facture = db.session.get(Facture, une_facture.id)
    assert facture.statut == "payee"
    assert facture.montant_paye == Decimal("200.00")
    assert facture.montant_restant == Decimal("0")
    assert Paiement.query.filter_by(facture_id=facture.id).count() == 2


def test_paiement_montant_negatif_refuse(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 1},
        follow_redirects=True,
    )
    connecte.post(
        f"/factures/{une_facture.id}/paiements/ajouter",
        data={"montant": "-50.00", "methode": "espece", "reference": ""},
        follow_redirects=True,
    )
    facture = db.session.get(Facture, une_facture.id)
    assert facture.montant_paye == Decimal("0")


def test_client_voit_lhistorique_de_ses_paiements(connecte_client, client_avec_compte, un_produit):
    facture = Facture(client_id=client_avec_compte.id, statut="attente", total=Decimal("300.00"))
    db.session.add(facture)
    db.session.commit()

    paiement = Paiement(facture_id=facture.id, montant=Decimal("300.00"), methode="cheque", reference="CHQ-42")
    db.session.add(paiement)
    db.session.commit()

    reponse = connecte_client.get("/portail/paiements")
    assert reponse.status_code == 200
    contenu = reponse.get_data(as_text=True)
    assert "Chèque" in contenu
    assert "300.00" in contenu


def test_methode_de_paiement_invalide_refusee(connecte, une_facture):
    reponse = connecte.post(
        f"/factures/{une_facture.id}/paiements/ajouter",
        data={"montant": "10", "methode": "especes-invalide", "reference": ""},
    )
    # methode hors choix valides -> formulaire invalide, aucun paiement cree
    assert Paiement.query.count() == 0


def test_paiement_superieur_au_montant_restant_est_accepte_et_solde_la_facture(
    connecte, une_facture, un_produit
):
    # Documente le comportement actuel (aucun plafond) : un reglement du
    # personnel superieur au solde restant est accepte tel quel (utile pour
    # des ajustements/arrondis geres manuellement) et fait passer la facture
    # a "payee". Cote portail, ce risque n'existe pas : le montant envoye a
    # Stripe est toujours calcule par le serveur (facture.montant_restant),
    # jamais fourni par le client.
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 1},
        follow_redirects=True,
    )
    facture = db.session.get(Facture, une_facture.id)
    assert facture.total == Decimal("100.00")

    connecte.post(
        f"/factures/{facture.id}/paiements/ajouter",
        data={"montant": "500.00", "methode": "espece", "reference": ""},
        follow_redirects=True,
    )

    facture = db.session.get(Facture, une_facture.id)
    assert facture.montant_paye == Decimal("500.00")
    assert facture.statut == "payee"
    assert facture.montant_restant == Decimal("0")


def test_paiement_montant_zero_refuse(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 1},
        follow_redirects=True,
    )
    connecte.post(
        f"/factures/{une_facture.id}/paiements/ajouter",
        data={"montant": "0", "methode": "espece", "reference": ""},
        follow_redirects=True,
    )
    facture = db.session.get(Facture, une_facture.id)
    assert facture.montant_paye == Decimal("0")
    assert facture.statut == "attente"
