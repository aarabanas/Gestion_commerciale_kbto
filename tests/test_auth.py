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


def _echouer_connexion(client, identifiant="admin"):
    return client.post(
        "/connexion",
        data={"nom_utilisateur": identifiant, "mot_de_passe": "faux-mot-de-passe"},
    )


def test_connexion_verrouillee_apres_trop_de_tentatives_echouees(client, utilisateur):
    from app import LIMITE_TENTATIVES_CONNEXION

    for _ in range(LIMITE_TENTATIVES_CONNEXION):
        _echouer_connexion(client)

    # Meme avec le BON mot de passe, le compte reste verrouille tant que la
    # fenetre de verrouillage n'est pas ecoulee.
    reponse = client.post(
        "/connexion",
        data={"nom_utilisateur": "admin", "mot_de_passe": "motdepasse123"},
        follow_redirects=True,
    )
    assert "Trop de tentatives" in reponse.get_data(as_text=True)
    assert client.get("/clients").status_code == 302  # toujours non connecte


def test_verrouillage_connexion_scope_par_identifiant(client, utilisateur, employe):
    from app import LIMITE_TENTATIVES_CONNEXION

    for _ in range(LIMITE_TENTATIVES_CONNEXION):
        _echouer_connexion(client, identifiant="admin")

    # Les echecs sur "admin" ne doivent pas verrouiller un identifiant different.
    reponse = client.post(
        "/connexion",
        data={"nom_utilisateur": "employe1", "mot_de_passe": "motdepasse123"},
        follow_redirects=True,
    )
    assert "Trop de tentatives" not in reponse.get_data(as_text=True)
    assert client.get("/clients").status_code == 200


def test_connexion_reussie_reinitialise_le_compteur_dechecs(client, utilisateur):
    from app import LIMITE_TENTATIVES_CONNEXION

    for _ in range(LIMITE_TENTATIVES_CONNEXION - 1):
        _echouer_connexion(client)

    # Une connexion reussie avant d'atteindre la limite reinitialise le compteur.
    client.post(
        "/connexion",
        data={"nom_utilisateur": "admin", "mot_de_passe": "motdepasse123"},
        follow_redirects=True,
    )
    client.post("/deconnexion")

    reponse = client.post(
        "/connexion",
        data={"nom_utilisateur": "admin", "mot_de_passe": "motdepasse123"},
        follow_redirects=True,
    )
    assert "Trop de tentatives" not in reponse.get_data(as_text=True)
    assert client.get("/clients").status_code == 200
