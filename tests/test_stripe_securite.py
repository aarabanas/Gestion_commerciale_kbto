"""Tests de securite/metier autour de la confirmation de paiement Stripe
(`portail_paiement_succes`).

Contexte du correctif teste ici : avant correction, la route ne verifiait
que `payment_status == "paid"` sur la session Stripe recuperee via
`session_id`, sans jamais controler que cette session avait bien ete creee
pour LA facture demandee dans l'URL (le champ `metadata["facture_id"]" fixe
au moment de `portail_payer_facture`). De plus, la protection anti-rejeu
n'etait unique que par (facture_id, reference), pas par reference seule.

Un client possedant plusieurs factures pouvait donc payer une petite facture
A via Stripe (obtenant un session_id reel avec payment_status="paid"), puis
appeler manuellement `/portail/paiements/succes/<id_facture_B>?session_id=
<session_id_de_A>` pour une AUTRE facture B qu'il possede, et faire crediter
le montant de A comme paiement sur B -- potentiellement en repetant
l'operation sur plusieurs factures avec le meme session_id reel.

On simule ici Stripe via monkeypatch (aucun appel reseau reel) : le module
`stripe` est un singleton importe par `app.py`, donc patcher
`stripe.checkout.Session.retrieve` affecte directement le code de l'app.
"""
from decimal import Decimal

import stripe

import app as app_module
from models import Facture, Paiement, db


class FausseSessionStripe:
    """Imite l'objet renvoye par stripe.checkout.Session.retrieve()."""

    def __init__(self, payment_status="paid", amount_total=1000, facture_id=None):
        self.payment_status = payment_status
        self.amount_total = amount_total
        self.metadata = {"facture_id": str(facture_id)} if facture_id is not None else {}


def _activer_stripe(monkeypatch):
    monkeypatch.setattr(app_module, "STRIPE_SECRET_KEY", "sk_test_fausse_cle")


def _deux_factures(client_avec_compte):
    facture_a = Facture(client_id=client_avec_compte.id, statut="attente", total=Decimal("10.00"))
    facture_b = Facture(client_id=client_avec_compte.id, statut="attente", total=Decimal("500.00"))
    db.session.add_all([facture_a, facture_b])
    db.session.commit()
    return facture_a, facture_b


def test_paiement_stripe_confirme_credite_la_bonne_facture(
    connecte_client, client_avec_compte, monkeypatch
):
    _activer_stripe(monkeypatch)
    facture_a, _ = _deux_factures(client_avec_compte)

    monkeypatch.setattr(
        stripe.checkout.Session,
        "retrieve",
        lambda session_id, **kw: FausseSessionStripe(
            payment_status="paid", amount_total=1000, facture_id=facture_a.id
        ),
    )

    reponse = connecte_client.get(
        f"/portail/paiements/succes/{facture_a.id}?session_id=cs_test_a",
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert "confirmé" in reponse.get_data(as_text=True)

    facture_a = db.session.get(Facture, facture_a.id)
    assert facture_a.montant_paye == Decimal("10.00")
    assert facture_a.statut == "payee"
    assert Paiement.query.filter_by(facture_id=facture_a.id, reference="cs_test_a").count() == 1


def test_rejeu_session_stripe_sur_une_autre_facture_refuse(
    connecte_client, client_avec_compte, monkeypatch
):
    """Reproduit l'attaque : payer A, puis rejouer le meme session_id sur B."""
    _activer_stripe(monkeypatch)
    facture_a, facture_b = _deux_factures(client_avec_compte)

    # La session Stripe a ete creee (metadata) pour la facture A uniquement,
    # peu importe l'id demande dans l'URL par l'attaquant.
    monkeypatch.setattr(
        stripe.checkout.Session,
        "retrieve",
        lambda session_id, **kw: FausseSessionStripe(
            payment_status="paid", amount_total=1000, facture_id=facture_a.id
        ),
    )

    # 1) Paiement legitime de la facture A.
    connecte_client.get(f"/portail/paiements/succes/{facture_a.id}?session_id=cs_test_rejeu")
    facture_a = db.session.get(Facture, facture_a.id)
    assert facture_a.montant_paye == Decimal("10.00")

    # 2) Rejeu du MEME session_id sur la facture B, appartenant au meme client.
    # (La reference existe deja en base pour A -> c'est la verification
    # d'unicite globale qui bloque ici, avant meme un nouvel appel Stripe.)
    reponse = connecte_client.get(
        f"/portail/paiements/succes/{facture_b.id}?session_id=cs_test_rejeu",
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert "déjà été utilisée pour une autre facture" in reponse.get_data(as_text=True)

    facture_b = db.session.get(Facture, facture_b.id)
    assert facture_b.montant_paye == Decimal("0")
    assert facture_b.statut == "attente"
    assert Paiement.query.filter_by(facture_id=facture_b.id).count() == 0
    # La reference n'a servi qu'une seule fois, pour la bonne facture.
    assert Paiement.query.filter_by(reference="cs_test_rejeu").count() == 1


def test_rejeu_session_deja_enregistree_globalement_refuse_sans_appel_stripe(
    connecte_client, client_avec_compte, monkeypatch
):
    """Meme si l'appel a l'API Stripe echouait/n'etait pas mocke, la
    verification d'unicite globale de `reference` doit bloquer le rejeu
    avant meme d'aller interroger Stripe."""
    _activer_stripe(monkeypatch)
    facture_a, facture_b = _deux_factures(client_avec_compte)

    # Paiement en ligne deja enregistre sur A avec cette reference (simule un
    # paiement reel deja confirme precedemment).
    paiement_existant = Paiement(
        facture_id=facture_a.id, montant=Decimal("10.00"), methode="en_ligne", reference="cs_test_deja"
    )
    db.session.add(paiement_existant)
    db.session.commit()

    def _retrieve_ne_devrait_pas_etre_appele(session_id, **kw):
        raise AssertionError("stripe.checkout.Session.retrieve n'aurait pas dû être appelé")

    monkeypatch.setattr(stripe.checkout.Session, "retrieve", _retrieve_ne_devrait_pas_etre_appele)

    reponse = connecte_client.get(
        f"/portail/paiements/succes/{facture_b.id}?session_id=cs_test_deja",
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert "déjà été utilisée pour une autre facture" in reponse.get_data(as_text=True)

    facture_b = db.session.get(Facture, facture_b.id)
    assert facture_b.montant_paye == Decimal("0")


def test_confirmation_repetee_sur_la_meme_facture_ne_duplique_pas_le_paiement(
    connecte_client, client_avec_compte, monkeypatch
):
    _activer_stripe(monkeypatch)
    facture_a, _ = _deux_factures(client_avec_compte)

    paiement_existant = Paiement(
        facture_id=facture_a.id, montant=Decimal("10.00"), methode="en_ligne", reference="cs_test_idempotent"
    )
    db.session.add(paiement_existant)
    db.session.commit()

    def _retrieve_ne_devrait_pas_etre_appele(session_id, **kw):
        raise AssertionError("stripe.checkout.Session.retrieve n'aurait pas dû être appelé")

    monkeypatch.setattr(stripe.checkout.Session, "retrieve", _retrieve_ne_devrait_pas_etre_appele)

    reponse = connecte_client.get(
        f"/portail/paiements/succes/{facture_a.id}?session_id=cs_test_idempotent",
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert "déjà confirmé" in reponse.get_data(as_text=True)
    assert Paiement.query.filter_by(facture_id=facture_a.id).count() == 1


def test_paiement_succes_facture_dun_autre_client_refuse(connecte_client, une_facture):
    # `une_facture` appartient au fixture `un_client`, distinct du client
    # connecte (`client_avec_compte`) : la route doit renvoyer 404 avant meme
    # de regarder le session_id, sans avoir besoin de mocker Stripe.
    reponse = connecte_client.get(f"/portail/paiements/succes/{une_facture.id}?session_id=cs_peu_importe")
    assert reponse.status_code == 404


def test_paiement_annule_facture_dun_autre_client_refuse(connecte_client, une_facture):
    reponse = connecte_client.get(f"/portail/paiements/annule/{une_facture.id}")
    assert reponse.status_code == 404


def test_session_stripe_non_payee_ne_credite_rien(connecte_client, client_avec_compte, monkeypatch):
    _activer_stripe(monkeypatch)
    facture_a, _ = _deux_factures(client_avec_compte)

    monkeypatch.setattr(
        stripe.checkout.Session,
        "retrieve",
        lambda session_id, **kw: FausseSessionStripe(
            payment_status="unpaid", amount_total=1000, facture_id=facture_a.id
        ),
    )

    reponse = connecte_client.get(
        f"/portail/paiements/succes/{facture_a.id}?session_id=cs_test_impaye",
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    # Jinja echappe l'apostrophe (&#39;) : on verifie une sous-chaine sans
    # apostrophe pour ne pas dependre du rendu HTML exact.
    assert "pas pu être confirmé" in reponse.get_data(as_text=True)
    assert Paiement.query.filter_by(facture_id=facture_a.id).count() == 0
