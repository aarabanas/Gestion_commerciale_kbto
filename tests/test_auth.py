def test_page_protegee_redirige_sans_connexion(client):
    reponse = client.get("/clients")
    assert reponse.status_code == 302
    assert "/connexion" in reponse.headers["Location"]


def test_connexion_reussie(client, utilisateur):
    reponse = client.post(
        "/connexion",
        data={"nom_utilisateur": "admin", "mot_de_passe": "motdepasse123"},
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    # apres connexion, la page clients devient accessible
    assert client.get("/clients").status_code == 200


def test_connexion_echouee_mauvais_mot_de_passe(client, utilisateur):
    reponse = client.post(
        "/connexion",
        data={"nom_utilisateur": "admin", "mot_de_passe": "faux-mot-de-passe"},
    )
    assert reponse.status_code == 200
    # toujours non connecte : /clients doit rediriger
    assert client.get("/clients").status_code == 302


def test_deconnexion(connecte):
    assert connecte.get("/clients").status_code == 200
    connecte.post("/deconnexion", follow_redirects=True)
    assert connecte.get("/clients").status_code == 302
