from models import Client, Facture, db


def test_paiement_sans_cle_stripe_affiche_message(connecte_client, client_avec_compte):
    facture = Facture(client_id=client_avec_compte.id, statut="attente", total=100)
    db.session.add(facture)
    db.session.commit()

    reponse = connecte_client.post(f"/portail/paiements/payer/{facture.id}", follow_redirects=True)
    assert reponse.status_code == 200
    assert "pas encore configur" in reponse.get_data(as_text=True)

    facture_actuelle = db.session.get(Facture, facture.id)
    assert facture_actuelle.statut == "attente"


def test_paiement_facture_dun_autre_client_refuse(connecte_client, une_facture):
    reponse = connecte_client.post(f"/portail/paiements/payer/{une_facture.id}")
    assert reponse.status_code == 404


def test_profil_client_modification(connecte_client, client_avec_compte):
    donnees = {
        "nom": client_avec_compte.nom,
        "prenom": "Modifie",
        "email": client_avec_compte.email,
        "telephone": "",
        "adresse": "",
        "mot_de_passe_actuel": "",
        "nouveau_mot_de_passe": "",
        "confirmer_nouveau_mot_de_passe": "",
    }
    connecte_client.post("/portail/profil", data=donnees, follow_redirects=True)

    client_actuel = db.session.get(Client, client_avec_compte.id)
    assert client_actuel.prenom == "Modifie"


def test_profil_client_changement_mdp_refuse_si_mauvais_mdp_actuel(connecte_client, client_avec_compte):
    donnees = {
        "nom": client_avec_compte.nom,
        "prenom": client_avec_compte.prenom,
        "email": client_avec_compte.email,
        "telephone": "",
        "adresse": "",
        "mot_de_passe_actuel": "faux",
        "nouveau_mot_de_passe": "nouveaumdp123",
        "confirmer_nouveau_mot_de_passe": "nouveaumdp123",
    }
    connecte_client.post("/portail/profil", data=donnees, follow_redirects=True)

    client_actuel = db.session.get(Client, client_avec_compte.id)
    assert client_actuel.verifier_mot_de_passe("motdepasse123")
