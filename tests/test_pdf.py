def test_telechargement_pdf_facture(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 2},
        follow_redirects=True,
    )

    reponse = connecte.get(f"/factures/{une_facture.id}/pdf")

    assert reponse.status_code == 200
    assert reponse.mimetype == "application/pdf"
    assert reponse.data[:4] == b"%PDF"


def test_changement_statut_facture(connecte, une_facture):
    reponse = connecte.post(
        f"/factures/{une_facture.id}/statut",
        data={"statut": "payee"},
        follow_redirects=True,
    )

    assert reponse.status_code == 200

    from models import Facture, db
    facture = db.session.get(Facture, une_facture.id)
    assert facture.statut == "payee"
