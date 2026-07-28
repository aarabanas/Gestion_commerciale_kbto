from models import Client, Produit, db


def test_impression_facture_personnel(connecte, une_facture, un_produit):
    connecte.post(
        f"/factures/{une_facture.id}",
        data={"produit": un_produit.id, "quantite": 1},
        follow_redirects=True,
    )
    reponse = connecte.get(f"/factures/{une_facture.id}/imprimer")
    assert reponse.status_code == 200
    contenu = reponse.get_data(as_text=True)
    assert un_produit.nom in contenu
    assert une_facture.client.nom in contenu


def test_employe_ne_peut_pas_supprimer_un_client(connecte_employe, un_client):
    reponse = connecte_employe.post(f"/clients/supprimer/{un_client.id}")
    assert reponse.status_code == 403
    assert db.session.get(Client, un_client.id) is not None


def test_employe_ne_peut_pas_supprimer_un_produit(connecte_employe, un_produit):
    reponse = connecte_employe.post(f"/produits/supprimer/{un_produit.id}")
    assert reponse.status_code == 403
    assert db.session.get(Produit, un_produit.id) is not None


def test_admin_peut_toujours_supprimer_un_produit_non_reference(connecte, un_produit):
    connecte.post(f"/produits/supprimer/{un_produit.id}", follow_redirects=True)
    assert db.session.get(Produit, un_produit.id) is None
