"""Couvre les branches "facture introuvable" / entrees invalides des routes
personnel de facturation, qui n'etaient pas exercees par la suite existante.
Ecrit aussi comme filet de securite avant de factoriser le motif repete
`facture = db.session.get(Facture, id); if facture is None: ...` (cf.
`obtenir_facture_ou_rediriger` dans app.py) : ces tests doivent rester verts
a l'identique avant et apres la factorisation.
"""
from models import DetailFacture, Facture, db


ID_INEXISTANT = 999999


def test_detail_facture_introuvable_redirige(connecte):
    reponse = connecte.get(f"/factures/{ID_INEXISTANT}", follow_redirects=True)
    assert reponse.status_code == 200
    assert "Facture introuvable" in reponse.get_data(as_text=True)


def test_changer_statut_facture_introuvable_redirige(connecte):
    reponse = connecte.post(
        f"/factures/{ID_INEXISTANT}/statut",
        data={"statut": "payee"},
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert "Facture introuvable" in reponse.get_data(as_text=True)


def test_changer_statut_facture_valeur_invalide_refusee(connecte, une_facture):
    reponse = connecte.post(
        f"/factures/{une_facture.id}/statut",
        data={"statut": "statut-inconnu"},
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert "Statut invalide" in reponse.get_data(as_text=True)

    facture = db.session.get(Facture, une_facture.id)
    assert facture.statut == "attente"


def test_marquer_facture_envoyee_introuvable_redirige(connecte):
    reponse = connecte.post(f"/factures/{ID_INEXISTANT}/marquer-envoyee", follow_redirects=True)
    assert reponse.status_code == 200
    assert "Facture introuvable" in reponse.get_data(as_text=True)


def test_ajouter_paiement_facture_introuvable_redirige(connecte):
    reponse = connecte.post(
        f"/factures/{ID_INEXISTANT}/paiements/ajouter",
        data={"montant": "10", "methode": "espece", "reference": ""},
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert "Facture introuvable" in reponse.get_data(as_text=True)


def test_facture_pdf_introuvable_redirige(connecte):
    reponse = connecte.get(f"/factures/{ID_INEXISTANT}/pdf", follow_redirects=True)
    assert reponse.status_code == 200
    assert "Facture introuvable" in reponse.get_data(as_text=True)


def test_facture_imprimer_introuvable_redirige(connecte):
    reponse = connecte.get(f"/factures/{ID_INEXISTANT}/imprimer", follow_redirects=True)
    assert reponse.status_code == 200
    assert "Facture introuvable" in reponse.get_data(as_text=True)


def test_supprimer_ligne_facture_id_inexistant(connecte, une_facture):
    reponse = connecte.post(
        f"/factures/{une_facture.id}/lignes/supprimer/{ID_INEXISTANT}",
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert "Ligne introuvable" in reponse.get_data(as_text=True)


def test_supprimer_ligne_facture_appartenant_a_une_autre_facture_refuse(
    connecte, une_facture, un_produit
):
    # Deuxieme facture, avec sa propre ligne : on tente de la supprimer via
    # l'URL de la premiere facture (facture_id/ligne_id incoherents).
    autre_facture = Facture(client_id=une_facture.client_id)
    db.session.add(autre_facture)
    db.session.commit()

    connecte.post(
        f"/factures/{autre_facture.id}",
        data={"produit": un_produit.id, "quantite": 1},
        follow_redirects=True,
    )
    ligne_autre_facture = DetailFacture.query.filter_by(facture_id=autre_facture.id).first()
    assert ligne_autre_facture is not None

    reponse = connecte.post(
        f"/factures/{une_facture.id}/lignes/supprimer/{ligne_autre_facture.id}",
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert "Ligne introuvable" in reponse.get_data(as_text=True)

    # La ligne n'a pas ete touchee : elle appartient toujours a l'autre facture.
    assert db.session.get(DetailFacture, ligne_autre_facture.id) is not None
