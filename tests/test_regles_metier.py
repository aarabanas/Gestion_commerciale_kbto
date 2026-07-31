from decimal import Decimal

from models import DetailFacture, Facture, Produit, db


def _ajouter_ligne(client, facture_id, produit_id, quantite):
    return client.post(
        f"/factures/{facture_id}",
        data={"produit": produit_id, "quantite": quantite},
        follow_redirects=True,
    )


def test_stock_refuse_survente(connecte, une_facture, un_produit):
    _ajouter_ligne(connecte, une_facture.id, un_produit.id, 50)

    produit = db.session.get(Produit, un_produit.id)
    facture = db.session.get(Facture, une_facture.id)

    assert produit.quantite == 10
    assert facture.total == Decimal("0")
    assert DetailFacture.query.count() == 0


def test_stock_decrement_a_l_ajout(connecte, une_facture, un_produit):
    _ajouter_ligne(connecte, une_facture.id, un_produit.id, 3)

    produit = db.session.get(Produit, un_produit.id)
    facture = db.session.get(Facture, une_facture.id)

    assert produit.quantite == 7
    assert facture.total == Decimal("300.00")


def test_stock_restitution_au_retrait(connecte, une_facture, un_produit):
    _ajouter_ligne(connecte, une_facture.id, un_produit.id, 3)
    ligne = DetailFacture.query.filter_by(facture_id=une_facture.id).first()

    connecte.post(
        f"/factures/{une_facture.id}/lignes/supprimer/{ligne.id}",
        follow_redirects=True,
    )

    produit = db.session.get(Produit, un_produit.id)
    facture = db.session.get(Facture, une_facture.id)

    assert produit.quantite == 10
    assert facture.total == Decimal("0.00")


def test_prix_fige_sur_facture_emise(connecte, une_facture, un_produit):
    _ajouter_ligne(connecte, une_facture.id, un_produit.id, 2)

    produit = db.session.get(Produit, un_produit.id)
    produit.prix = Decimal("150.00")
    db.session.commit()

    ligne = DetailFacture.query.filter_by(facture_id=une_facture.id).first()
    assert ligne.prix_unitaire == Decimal("100.00")


def test_stock_ne_peut_pas_etre_survendu_sur_deux_factures_successives(
    connecte, une_facture, un_produit
):
    """Verifie la limite du controle atomique deja en place dans
    `ajouter_ligne_facture` : le decrement de stock est fait par un seul
    UPDATE ... WHERE quantite >= quantite_demandee, donc deux ventes qui se
    partagent le meme stock ne peuvent jamais, ensemble, le faire passer sous
    zero -- meme si chacune, prise isolement, semble avoir assez de stock au
    moment de la lecture initiale (stock=10)."""
    autre_facture = Facture(client_id=une_facture.client_id)
    db.session.add(autre_facture)
    db.session.commit()

    # Premiere vente : prend exactement tout le stock disponible (10).
    _ajouter_ligne(connecte, une_facture.id, un_produit.id, 10)
    produit = db.session.get(Produit, un_produit.id)
    assert produit.quantite == 0

    # Deuxieme vente (facture differente) : il ne reste plus rien -> refusee,
    # meme pour une quantite de 1 seule unite.
    _ajouter_ligne(connecte, autre_facture.id, un_produit.id, 1)

    produit = db.session.get(Produit, un_produit.id)
    autre_facture = db.session.get(Facture, autre_facture.id)
    assert produit.quantite == 0  # jamais negatif
    assert autre_facture.total == Decimal("0")
    assert DetailFacture.query.filter_by(facture_id=autre_facture.id).count() == 0


def test_total_facture_plusieurs_lignes(connecte, une_facture, un_produit):
    autre_produit = Produit(nom="Souris", prix=Decimal("50.00"), quantite=5)
    db.session.add(autre_produit)
    db.session.commit()

    _ajouter_ligne(connecte, une_facture.id, un_produit.id, 2)
    _ajouter_ligne(connecte, une_facture.id, autre_produit.id, 1)

    facture = db.session.get(Facture, une_facture.id)
    lignes = DetailFacture.query.filter_by(facture_id=une_facture.id).all()
    total_attendu = sum(l.prix_unitaire * l.quantite for l in lignes)

    assert facture.total == total_attendu
    assert facture.total == Decimal("250.00")
