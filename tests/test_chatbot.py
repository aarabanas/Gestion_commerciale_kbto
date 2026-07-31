"""Tests de l'assistant du portail client : un moteur de FAQ local a base de
mots-cles (aucun appel a une API externe, donc aucun cout d'utilisation)."""
from app import LIMITE_MESSAGES_CHATBOT, REPONSE_CHATBOT_PAR_DEFAUT


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


def test_chatbot_inaccessible_au_personnel(connecte):
    # Route reservee au portail client (nom de fonction prefixe "portail_") :
    # le garde-fou d'espace redirige tout compte personnel avant meme
    # d'atteindre la logique de la route.
    reponse = connecte.post("/portail/assistant/message", json={"message": "Test"})
    assert reponse.status_code == 302
