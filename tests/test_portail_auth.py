from models import Client, db


def test_inscription_cree_un_client_et_connecte(client):
    donnees = {
        "nom": "Nouveau",
        "prenom": "Client",
        "email": "nouveauclient@example.com",
        "telephone": "",
        "adresse": "",
        "mot_de_passe": "motdepasse123",
        "confirmer_mot_de_passe": "motdepasse123",
    }
    reponse = client.post("/inscription", data=donnees, follow_redirects=True)
    assert reponse.status_code == 200

    cree = Client.query.filter_by(email="nouveauclient@example.com").first()
    assert cree is not None
    assert cree.a_un_compte()
    assert cree.verifier_mot_de_passe("motdepasse123")

    # session ouverte automatiquement -> le tableau de bord client est accessible
    assert client.get("/portail/tableau-de-bord").status_code == 200


def test_inscription_refusee_si_email_deja_utilise(client, un_client):
    donnees = {
        "nom": "Autre",
        "prenom": "Personne",
        "email": un_client.email,
        "telephone": "",
        "adresse": "",
        "mot_de_passe": "motdepasse123",
        "confirmer_mot_de_passe": "motdepasse123",
    }
    client.post("/inscription", data=donnees, follow_redirects=True)

    assert Client.query.filter_by(email=un_client.email).count() == 1
    assert db.session.get(Client, un_client.id).mot_de_passe_hash is None


def test_connexion_client_par_email(connecte_client):
    assert connecte_client.get("/portail/tableau-de-bord").status_code == 200


def test_client_sans_compte_ne_peut_pas_se_connecter(client, un_client):
    reponse = client.post(
        "/connexion",
        data={"nom_utilisateur": un_client.email, "mot_de_passe": "peu-importe123"},
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert client.get("/portail/tableau-de-bord").status_code == 302


def test_client_redirige_hors_de_lespace_personnel(connecte_client):
    reponse = connecte_client.get("/clients", follow_redirects=False)
    assert reponse.status_code == 302
    assert "/portail/tableau-de-bord" in reponse.headers["Location"]


def test_personnel_redirige_hors_du_portail(connecte):
    reponse = connecte.get("/portail/tableau-de-bord", follow_redirects=False)
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/tableau-de-bord")


def test_client_ne_peut_pas_gerer_les_utilisateurs(connecte_client):
    reponse = connecte_client.get("/utilisateurs", follow_redirects=False)
    assert reponse.status_code == 302
