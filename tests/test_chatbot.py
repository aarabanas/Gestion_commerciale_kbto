"""Tests de l'assistant du portail client : un menu de boutons a choix
fermes (toujours gratuit, chaque bouton renvoie une reponse exacte sans
ambiguite de mots-cles), et un texte libre qui interroge l'API Claude quand
ANTHROPIC_API_KEY est configuree, avec repli automatique sur le moteur de
FAQ local a base de mots-cles sinon (aucun cout, aucune cle requise)."""
import app as app_module
from app import LIMITE_MESSAGES_CHATBOT, MENU_PRINCIPAL_CHATBOT, REPONSE_CHATBOT_PAR_DEFAUT


class FauxBlocTexte:
    type = "text"

    def __init__(self, texte):
        self.text = texte


class FauxReponseAnthropic:
    def __init__(self, texte, stop_reason="end_turn"):
        self.content = [FauxBlocTexte(texte)]
        self.stop_reason = stop_reason


class FauxMessages:
    def __init__(self, reponse=None, exception=None):
        self._reponse = reponse
        self._exception = exception
        self.appels = []

    def create(self, **kwargs):
        self.appels.append(kwargs)
        if self._exception:
            raise self._exception
        return self._reponse


class FauxClientAnthropic:
    def __init__(self, reponse=None, exception=None):
        self.messages = FauxMessages(reponse=reponse, exception=exception)


def test_chatbot_reconnait_une_question_sur_les_tarifs(connecte_client, un_produit):
    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Quels sont vos tarifs ?"})
    assert reponse.status_code == 200
    assert "DH" in reponse.get_json()["reponse"]


def test_chatbot_reconnait_une_question_sur_le_paiement(connecte_client):
    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Comment puis-je régler ma facture ?"})
    assert reponse.status_code == 200
    assert "chèque" in reponse.get_json()["reponse"].lower()


def test_chatbot_reconnait_une_question_sur_le_contact(connecte_client):
    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Quelle est votre adresse ?"})
    assert reponse.status_code == 200
    assert "contacter" in reponse.get_json()["reponse"].lower()


def test_chatbot_question_non_reconnue_renvoie_le_message_de_secours(connecte_client):
    reponse = connecte_client.post(
        "/portail/assistant/message",
        json={"message": "Combien pèse une girafe adulte ?"},
    )
    assert reponse.status_code == 200
    assert reponse.get_json()["reponse"] == REPONSE_CHATBOT_PAR_DEFAUT


def test_chatbot_message_vide_refuse(connecte_client):
    reponse = connecte_client.post("/portail/assistant/message", json={"message": "   "})
    assert reponse.status_code == 400


def test_chatbot_limite_anti_abus_atteinte(connecte_client):
    for _ in range(LIMITE_MESSAGES_CHATBOT):
        connecte_client.post("/portail/assistant/message", json={"message": "Bonjour"})

    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Encore une question"})
    assert "beaucoup de messages" in reponse.get_json()["reponse"]


def test_chatbot_reconnait_sans_accents(connecte_client):
    # Meme sujet (paiement) mais tape sans aucun accent : verifie que la
    # normalisation (accents retires des deux cotes) fonctionne, pas
    # seulement les variantes accentuees explicitement prevues.
    reponse = connecte_client.post("/portail/assistant/message", json={"message": "comment regler ma facture"})
    assert "cheque" in reponse.get_json()["reponse"].lower() or "chèque" in reponse.get_json()["reponse"].lower()


def test_chatbot_reconnait_une_question_sur_la_comptabilite(connecte_client):
    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Vous faites la comptabilité ?"})
    assert "comptab" in reponse.get_json()["reponse"].lower()


def test_chatbot_reconnait_une_question_sur_la_paie(connecte_client):
    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Vous gérez les bulletins de paie ?"})
    assert "paie" in reponse.get_json()["reponse"].lower()


def test_chatbot_reconnait_une_question_sur_le_compte(connecte_client):
    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Comment changer mon mot de passe ?"})
    assert "profil" in reponse.get_json()["reponse"].lower()


def test_chatbot_chaque_bouton_du_menu_renvoie_une_reponse_valide(connecte_client):
    # Garantit qu'aucun bouton du menu ne peut jamais tomber sur le message
    # de secours -- c'est tout l'interet du mode "boutons" par rapport au
    # texte libre.
    for option in MENU_PRINCIPAL_CHATBOT:
        reponse = connecte_client.post("/portail/assistant/message", json={"option_id": option["id"]})
        assert reponse.status_code == 200
        corps = reponse.get_json()
        assert corps["reponse"] != REPONSE_CHATBOT_PAR_DEFAUT
        assert corps["menu"] == MENU_PRINCIPAL_CHATBOT


def test_chatbot_option_id_inconnu_renvoie_le_message_de_secours(connecte_client):
    reponse = connecte_client.post("/portail/assistant/message", json={"option_id": "sujet-inexistant"})
    assert reponse.status_code == 200
    assert reponse.get_json()["reponse"] == REPONSE_CHATBOT_PAR_DEFAUT


def test_chatbot_reponse_inclut_toujours_le_menu(connecte_client):
    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Bonjour"})
    assert reponse.get_json()["menu"] == MENU_PRINCIPAL_CHATBOT


def test_chatbot_inaccessible_au_personnel(connecte):
    # Route reservee au portail client (nom de fonction prefixe "portail_") :
    # le garde-fou d'espace redirige tout compte personnel avant meme
    # d'atteindre la logique de la route.
    reponse = connecte.post("/portail/assistant/message", json={"message": "Test"})
    assert reponse.status_code == 302


def test_chatbot_texte_libre_utilise_ia_quand_configuree(monkeypatch, connecte_client):
    faux_client = FauxClientAnthropic(reponse=FauxReponseAnthropic("Réponse générée par l'IA."))
    monkeypatch.setattr(app_module, "client_anthropic", faux_client)

    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Question quelconque"})

    assert reponse.status_code == 200
    assert reponse.get_json()["reponse"] == "Réponse générée par l'IA."
    assert len(faux_client.messages.appels) == 1


def test_chatbot_texte_libre_repli_faq_si_ia_en_erreur(monkeypatch, connecte_client):
    # Toute erreur cote API (cle invalide, quota, panne reseau...) doit
    # retomber sur le moteur de mots-cles gratuit plutot que de faire
    # planter la requete ou de laisser le client sans reponse.
    faux_client = FauxClientAnthropic(exception=RuntimeError("panne simulee"))
    monkeypatch.setattr(app_module, "client_anthropic", faux_client)

    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Comment régler ma facture ?"})

    assert reponse.status_code == 200
    assert "chèque" in reponse.get_json()["reponse"].lower()


def test_chatbot_refus_ia_renvoie_le_message_de_secours(monkeypatch, connecte_client):
    faux_client = FauxClientAnthropic(reponse=FauxReponseAnthropic("", stop_reason="refusal"))
    monkeypatch.setattr(app_module, "client_anthropic", faux_client)

    reponse = connecte_client.post("/portail/assistant/message", json={"message": "Question quelconque"})

    assert reponse.get_json()["reponse"] == REPONSE_CHATBOT_PAR_DEFAUT


def test_chatbot_bouton_menu_najamais_appel_ia(monkeypatch, connecte_client):
    # Meme quand l'IA est configuree, un clic sur un bouton du menu doit
    # rester entierement gratuit : aucun appel a l'API ne doit partir.
    faux_client = FauxClientAnthropic(reponse=FauxReponseAnthropic("Ne devrait jamais etre utilise."))
    monkeypatch.setattr(app_module, "client_anthropic", faux_client)

    reponse = connecte_client.post("/portail/assistant/message", json={"option_id": "contact"})

    assert reponse.status_code == 200
    assert reponse.get_json()["reponse"] != "Ne devrait jamais etre utilise."
    assert len(faux_client.messages.appels) == 0
