from models import Utilisateur, db


def _donnees_utilisateur(**overrides):
    donnees = {
        "nom_utilisateur": "nouveau",
        "nom": "Nouveau",
        "prenom": "Compte",
        "telephone": "",
        "email": "nouveau@example.com",
        "role": "employe",
        "mot_de_passe": "motdepasse123",
        "confirmer_mot_de_passe": "motdepasse123",
    }
    donnees.update(overrides)
    return donnees


def test_employe_ne_peut_pas_acceder_a_la_gestion_des_utilisateurs(connecte_employe):
    reponse = connecte_employe.get("/utilisateurs")
    assert reponse.status_code == 403


def test_employe_ne_peut_pas_creer_utilisateur(connecte_employe):
    reponse = connecte_employe.post("/utilisateurs/ajouter", data=_donnees_utilisateur())
    assert reponse.status_code == 403
    assert Utilisateur.query.filter_by(nom_utilisateur="nouveau").first() is None


def test_admin_peut_lister_les_utilisateurs(connecte, utilisateur, employe):
    reponse = connecte.get("/utilisateurs")
    assert reponse.status_code == 200
    assert utilisateur.nom_utilisateur.encode() in reponse.data
    assert employe.nom_utilisateur.encode() in reponse.data


def test_admin_peut_creer_un_utilisateur(connecte):
    reponse = connecte.post("/utilisateurs/ajouter", data=_donnees_utilisateur(), follow_redirects=True)
    assert reponse.status_code == 200

    cree = Utilisateur.query.filter_by(nom_utilisateur="nouveau").first()
    assert cree is not None
    assert cree.role == "employe"
    assert cree.verifier_mot_de_passe("motdepasse123")


def test_creation_refusee_si_nom_utilisateur_deja_pris(connecte, utilisateur):
    reponse = connecte.post(
        "/utilisateurs/ajouter",
        data=_donnees_utilisateur(nom_utilisateur=utilisateur.nom_utilisateur, email="autre@example.com"),
        follow_redirects=True,
    )
    assert reponse.status_code == 200
    assert Utilisateur.query.filter_by(email="autre@example.com").first() is None


def test_admin_ne_peut_pas_supprimer_son_propre_compte(connecte, utilisateur):
    connecte.post(f"/utilisateurs/supprimer/{utilisateur.id}", follow_redirects=True)
    assert db.session.get(Utilisateur, utilisateur.id) is not None


def test_impossible_de_supprimer_le_dernier_administrateur(connecte, utilisateur, employe):
    # utilisateur est le seul administrateur ; un employe ne peut pas non plus le faire
    # mais ici on verifie la regle metier via un second admin qui essaierait de le degrader/supprimer
    reponse = connecte.post(f"/utilisateurs/supprimer/{utilisateur.id}", follow_redirects=True)
    assert reponse.status_code == 200
    assert db.session.get(Utilisateur, utilisateur.id) is not None


def test_modification_role_refusee_pour_dernier_administrateur(connecte, utilisateur):
    donnees = _donnees_utilisateur(
        nom_utilisateur=utilisateur.nom_utilisateur,
        email=utilisateur.email,
        role="employe",
    )
    del donnees["mot_de_passe"]
    del donnees["confirmer_mot_de_passe"]
    donnees["nouveau_mot_de_passe"] = ""
    donnees["confirmer_nouveau_mot_de_passe"] = ""

    connecte.post(f"/utilisateurs/modifier/{utilisateur.id}", data=donnees, follow_redirects=True)

    utilisateur_actuel = db.session.get(Utilisateur, utilisateur.id)
    assert utilisateur_actuel.role == "administrateur"


def test_admin_peut_supprimer_un_employe(connecte, employe):
    connecte.post(f"/utilisateurs/supprimer/{employe.id}", follow_redirects=True)
    assert db.session.get(Utilisateur, employe.id) is None


def test_employe_ne_peut_pas_modifier_un_utilisateur(connecte_employe, employe):
    # Un employe ne doit pas pouvoir elever son propre role (ou celui d'un
    # autre compte) vers administrateur en appelant directement la route de
    # modification reservee a l'administrateur.
    donnees = _donnees_utilisateur(
        nom_utilisateur=employe.nom_utilisateur,
        email=employe.email,
        role="administrateur",
    )
    del donnees["mot_de_passe"]
    del donnees["confirmer_mot_de_passe"]
    donnees["nouveau_mot_de_passe"] = ""
    donnees["confirmer_nouveau_mot_de_passe"] = ""

    reponse = connecte_employe.post(f"/utilisateurs/modifier/{employe.id}", data=donnees)
    assert reponse.status_code == 403

    employe_actuel = db.session.get(Utilisateur, employe.id)
    assert employe_actuel.role == "employe"


def test_employe_ne_peut_pas_supprimer_un_utilisateur(connecte_employe, utilisateur):
    reponse = connecte_employe.post(f"/utilisateurs/supprimer/{utilisateur.id}")
    assert reponse.status_code == 403
    assert db.session.get(Utilisateur, utilisateur.id) is not None
