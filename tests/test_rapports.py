from decimal import Decimal

from models import Facture, db


def test_ca_total_egale_somme_des_factures(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 4},
        follow_redirects=True,
    )

    reponse = connecte.get("/rapports")
    assert reponse.status_code == 200

    somme_attendue = sum((f.total or Decimal("0")) for f in Facture.query.all())
    assert somme_attendue == Decimal("400.00")
