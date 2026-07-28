from models import Utilisateur, db


def _donnees_profil(utilisateur, **overrides):
    donnees = {
        "nom_utilisateur": utilisateur.nom_utilisateur,
        "nom": utilisateur.nom,
        "prenom": utilisateur.prenom,
        "telephone": "",
        "email": utilisateur.email,
        "mot_de_passe_actuel": "",
        "nouveau_mot_de_passe": "",
        "confirmer_nouveau_mot_de_passe": "",
    }
    donnees.update(overrides)
    return donnees


def test_profil_accessible_a_tous_les_roles_connectes(connecte, connecte_employe):
    assert connecte.get("/profil").status_code == 200
    assert connecte_employe.get("/profil").status_code == 200


def test_modification_infos_de_base(connecte, utilisateur):
    donnees = _donnees_profil(utilisateur, prenom="Modifie")
    connecte.post("/profil", data=donnees, follow_redirects=True)

    utilisateur_actuel = db.session.get(Utilisateur, utilisateur.id)
    assert utilisateur_actuel.prenom == "Modifie"


def test_changement_mot_de_passe_refuse_si_mauvais_mot_de_passe_actuel(connecte, utilisateur):
    donnees = _donnees_profil(
        utilisateur,
        mot_de_passe_actuel="faux-mot-de-passe",
        nouveau_mot_de_passe="nouveaumdp123",
        confirmer_nouveau_mot_de_passe="nouveaumdp123",
    )
    connecte.post("/profil", data=donnees, follow_redirects=True)

    utilisateur_actuel = db.session.get(Utilisateur, utilisateur.id)
    assert utilisateur_actuel.verifier_mot_de_passe("motdepasse123")
    assert not utilisateur_actuel.verifier_mot_de_passe("nouveaumdp123")


def test_changement_mot_de_passe_reussi(connecte, utilisateur):
    donnees = _donnees_profil(
        utilisateur,
        mot_de_passe_actuel="motdepasse123",
        nouveau_mot_de_passe="nouveaumdp123",
        confirmer_nouveau_mot_de_passe="nouveaumdp123",
    )
    connecte.post("/profil", data=donnees, follow_redirects=True)

    utilisateur_actuel = db.session.get(Utilisateur, utilisateur.id)
    assert utilisateur_actuel.verifier_mot_de_passe("nouveaumdp123")
