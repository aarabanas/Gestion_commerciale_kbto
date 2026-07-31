"""Tests des routes de gestion des produits (jusqu'ici non couvertes par la
suite existante) : creation/modification, et validation des bornes
numeriques sur prix/quantite (ajoutees suite a l'audit de securite -- ces
champs ecrivent directement en base sans passer par le controle atomique de
`ajouter_ligne_facture`, contrairement aux lignes de facture)."""
from decimal import Decimal

from models import Produit, db


def _donnees_produit(**overrides):
    donnees = {
        "nom": "Bilan comptable",
        "categorie": "Comptabilité",
        "prix": "500.00",
        "quantite": "10",
        "description": "",
    }
    donnees.update(overrides)
    return donnees


def test_ajout_produit_reussi(connecte):
    reponse = connecte.post("/produits/ajouter", data=_donnees_produit(), follow_redirects=True)
    assert reponse.status_code == 200

    produit = Produit.query.filter_by(nom="Bilan comptable").first()
    assert produit is not None
    assert produit.prix == Decimal("500.00")
    assert produit.quantite == 10


def test_ajout_produit_prix_negatif_refuse(connecte):
    connecte.post("/produits/ajouter", data=_donnees_produit(prix="-10.00"), follow_redirects=True)
    assert Produit.query.filter_by(nom="Bilan comptable").first() is None


def test_ajout_produit_quantite_negative_refusee(connecte):
    connecte.post("/produits/ajouter", data=_donnees_produit(quantite="-5"), follow_redirects=True)
    assert Produit.query.filter_by(nom="Bilan comptable").first() is None


def test_ajout_produit_quantite_zero_autorise(connecte):
    # 0 reste une valeur legitime (rupture de stock a la creation).
    reponse = connecte.post(
        "/produits/ajouter", data=_donnees_produit(quantite="0"), follow_redirects=True
    )
    assert reponse.status_code == 200
    produit = Produit.query.filter_by(nom="Bilan comptable").first()
    assert produit is not None
    assert produit.quantite == 0


def test_ajout_produit_prix_zero_autorise(connecte):
    # Idem : une prestation ponctuellement offerte (prix 0) reste legitime,
    # DataRequired ne doit pas la confondre avec un champ vide (cf. le meme
    # correctif applique a quantite ci-dessus).
    reponse = connecte.post(
        "/produits/ajouter", data=_donnees_produit(prix="0"), follow_redirects=True
    )
    assert reponse.status_code == 200
    produit = Produit.query.filter_by(nom="Bilan comptable").first()
    assert produit is not None
    assert produit.prix == Decimal("0.00")


def test_modification_produit_prix_negatif_refusee(connecte, un_produit):
    connecte.post(
        f"/produits/modifier/{un_produit.id}",
        data=_donnees_produit(nom=un_produit.nom, prix="-1.00"),
        follow_redirects=True,
    )
    produit = db.session.get(Produit, un_produit.id)
    assert produit.prix == Decimal("100.00")  # valeur d'origine du fixture, inchangee


def test_modification_produit_introuvable_redirige(connecte):
    reponse = connecte.get("/produits/modifier/999999", follow_redirects=True)
    assert reponse.status_code == 200
    assert "Produit introuvable" in reponse.get_data(as_text=True)
