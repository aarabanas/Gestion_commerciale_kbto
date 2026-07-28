def test_connexion_google_non_configuree_redirige_avec_message(client):
    reponse = client.get("/connexion/google", follow_redirects=True)
    assert reponse.status_code == 200
    assert "pas encore configur" in reponse.get_data(as_text=True)


def test_connexion_github_non_configuree_redirige_avec_message(client):
    reponse = client.get("/connexion/github", follow_redirects=True)
    assert reponse.status_code == 200
    assert "pas encore configur" in reponse.get_data(as_text=True)


def test_fournisseur_inconnu_redirige_avec_message(client):
    reponse = client.get("/connexion/inconnu", follow_redirects=True)
    assert reponse.status_code == 200
    assert "pas encore configur" in reponse.get_data(as_text=True)


def test_callback_google_non_configuree_redirige(client):
    reponse = client.get("/connexion/google/callback", follow_redirects=True)
    assert reponse.status_code == 200
    assert "pas encore configur" in reponse.get_data(as_text=True)
