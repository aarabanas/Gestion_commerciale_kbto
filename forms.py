from flask_wtf import FlaskForm

from wtforms import (
    BooleanField,
    FieldList,
    Form,
    FormField,
    PasswordField,
    StringField,
    SubmitField,
    DecimalField,
    IntegerField,
    TextAreaField,
    SelectField,
    RadioField,
)

from wtforms.validators import (
    DataRequired,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Email,
)

from models import METHODES_PAIEMENT, STATUTS_FACTURE

# Politique de mot de passe et d'identifiant : centralisees ici car reprises
# a la fois par plusieurs formulaires (inscription, comptes personnel/client,
# changement de mot de passe) et par la commande CLI `creer-admin` (app.py).
LONGUEUR_MIN_MOT_DE_PASSE = 8
LONGUEUR_MIN_NOM_UTILISATEUR = 3
LONGUEUR_MAX_NOM_UTILISATEUR = 80
# L'identifiant de connexion accepte aussi un email de client (plus long
# qu'un simple nom d'utilisateur) -> une borne max plus large que ci-dessus.
LONGUEUR_MAX_IDENTIFIANT_CONNEXION = 150
# Montant minimum accepte pour un reglement (strictement positif : un
# paiement de 0 DH n'a pas de sens metier).
MONTANT_MINIMUM_PAIEMENT = 0.01


# =====================================
# Formulaire de connexion
# =====================================
class ConnexionForm(FlaskForm):

    nom_utilisateur = StringField(
        "Identifiant (nom d'utilisateur ou email)",
        validators=[
            DataRequired(message="L'identifiant est obligatoire."),
            Length(
                min=LONGUEUR_MIN_NOM_UTILISATEUR,
                max=LONGUEUR_MAX_IDENTIFIANT_CONNEXION,
                message="L'identifiant doit contenir entre 3 et 150 caractères.",
            ),
        ],
    )

    mot_de_passe = PasswordField(
        "Mot de passe",
        validators=[
            DataRequired(message="Le mot de passe est obligatoire."),
            Length(min=LONGUEUR_MIN_MOT_DE_PASSE, message="Le mot de passe doit contenir au moins 8 caractères."),
        ],
    )

    se_souvenir = BooleanField("Se souvenir de moi")

    envoyer = SubmitField("Se connecter")


# =====================================
# Formulaire d'inscription (cree un compte Client pour le portail)
# =====================================
class InscriptionClientForm(FlaskForm):

    nom = StringField("Nom", validators=[DataRequired()])

    prenom = StringField("Prénom", validators=[DataRequired()])

    email = StringField(
        "Email",
        validators=[DataRequired(message="L'email est obligatoire."), Email(check_deliverability=False)],
    )

    telephone = StringField("Téléphone", validators=[Optional()])

    adresse = StringField("Adresse", validators=[Optional()])

    mot_de_passe = PasswordField(
        "Mot de passe",
        validators=[
            DataRequired(message="Le mot de passe est obligatoire."),
            Length(min=LONGUEUR_MIN_MOT_DE_PASSE, message="Le mot de passe doit contenir au moins 8 caractères."),
        ],
    )

    confirmer_mot_de_passe = PasswordField(
        "Confirmer le mot de passe",
        validators=[
            DataRequired(message="Veuillez confirmer le mot de passe."),
            EqualTo("mot_de_passe", message="Les mots de passe ne correspondent pas."),
        ],
    )

    envoyer = SubmitField("Créer mon compte")


# =====================================
# Formulaire Client
# =====================================
class ClientForm(FlaskForm):

    nom = StringField("Nom", validators=[DataRequired()])

    prenom = StringField("Prénom", validators=[DataRequired()])

    email = StringField("Email", validators=[Optional(), Email(check_deliverability=False)])

    telephone = StringField("Téléphone", validators=[Optional()])

    adresse = StringField("Adresse", validators=[Optional()])

    envoyer = SubmitField("Enregistrer")


# =====================================
# Formulaire Produit
# =====================================
CATEGORIES_PRODUIT = [
    "Comptabilité",
    "Fiscalité",
    "Social et paie",
    "Conseil aux entreprises",
    "Autre",
]


class ProduitForm(FlaskForm):

    nom = StringField("Nom du produit", validators=[DataRequired()])

    categorie = SelectField(
        "Catégorie",
        choices=[(c, c) for c in CATEGORIES_PRODUIT],
        validators=[DataRequired()],
    )

    # InputRequired (et non DataRequired) : DataRequired traite 0 comme une
    # valeur "manquante" (verifie la troncite de field.data), ce qui rejetait
    # a tort un prix ou un stock legitimement a 0 (prestation offerte,
    # rupture de stock a la creation). InputRequired verifie seulement qu'une
    # valeur a bien ete soumise, et laisse NumberRange juger de sa validite.
    prix = DecimalField(
        "Prix",
        places=2,
        validators=[InputRequired(), NumberRange(min=0, message="Le prix ne peut pas être négatif.")],
    )

    quantite = IntegerField(
        "Quantité",
        validators=[
            InputRequired(),
            NumberRange(min=0, message="La quantité en stock ne peut pas être négative."),
        ],
    )

    description = TextAreaField("Description", validators=[Optional()])

    envoyer = SubmitField("Enregistrer")


# =====================================
# Formulaire Facture
# =====================================
class LigneCreationForm(Form):
    """Sous-formulaire (sans CSRF propre) pour une ligne produit ajoutee
    directement lors de la creation d'une facture."""

    produit = SelectField(
        "Produit",
        coerce=int,
        default=0,
    )

    quantite = IntegerField(
        "Quantité",
        default=1,
    )


class FactureForm(FlaskForm):

    client = SelectField(
        "Client",
        coerce=int,
        validators=[DataRequired()],
    )

    statut = SelectField(
        "Statut",
        choices=list(STATUTS_FACTURE.items()),
        default="attente",
        validators=[DataRequired()],
    )

    lignes = FieldList(FormField(LigneCreationForm), min_entries=5, max_entries=5)

    envoyer = SubmitField("Créer la facture")


# =====================================
# Formulaire Commande (portail client : pas de choix de client ni de statut)
# =====================================
class CommandeClientForm(FlaskForm):

    mode_paiement = RadioField(
        "Mode de paiement souhaité",
        choices=[
            ("cheque", "Chèque"),
            ("espece", "Espèces"),
            ("carte", "Carte bancaire"),
        ],
        validators=[DataRequired(message="Merci de choisir un mode de paiement.")],
    )

    lignes = FieldList(FormField(LigneCreationForm), min_entries=5, max_entries=5)

    envoyer = SubmitField("Passer la commande")


# =====================================
# Formulaire Ligne de facture (ajouter un produit à une facture)
# =====================================
class LigneFactureForm(FlaskForm):

    produit = SelectField(
        "Produit",
        coerce=int,
        validators=[DataRequired()],
    )

    quantite = IntegerField(
        "Quantité",
        validators=[DataRequired()],
    )

    envoyer = SubmitField("Ajouter à la facture")


# =====================================
# Formulaire Utilisateur (creation, par un administrateur)
# =====================================
class UtilisateurForm(FlaskForm):

    nom_utilisateur = StringField(
        "Nom d'utilisateur",
        validators=[
            DataRequired(message="Le nom d'utilisateur est obligatoire."),
            Length(
                min=LONGUEUR_MIN_NOM_UTILISATEUR,
                max=LONGUEUR_MAX_NOM_UTILISATEUR,
                message="Le nom d'utilisateur doit contenir entre 3 et 80 caractères.",
            ),
        ],
    )

    nom = StringField("Nom", validators=[DataRequired()])

    prenom = StringField("Prénom", validators=[DataRequired()])

    telephone = StringField("Téléphone", validators=[Optional()])

    email = StringField(
        "Email",
        validators=[DataRequired(message="L'email est obligatoire."), Email(check_deliverability=False)],
    )

    role = SelectField(
        "Rôle",
        choices=[("employe", "Employé"), ("administrateur", "Administrateur")],
        validators=[DataRequired()],
    )

    mot_de_passe = PasswordField(
        "Mot de passe",
        validators=[
            DataRequired(message="Le mot de passe est obligatoire."),
            Length(min=LONGUEUR_MIN_MOT_DE_PASSE, message="Le mot de passe doit contenir au moins 8 caractères."),
        ],
    )

    confirmer_mot_de_passe = PasswordField(
        "Confirmer le mot de passe",
        validators=[
            DataRequired(message="Veuillez confirmer le mot de passe."),
            EqualTo("mot_de_passe", message="Les mots de passe ne correspondent pas."),
        ],
    )

    envoyer = SubmitField("Créer l'utilisateur")


# =====================================
# Formulaire Utilisateur (modification, par un administrateur)
# =====================================
class ModifierUtilisateurForm(FlaskForm):

    nom_utilisateur = StringField(
        "Nom d'utilisateur",
        validators=[
            DataRequired(message="Le nom d'utilisateur est obligatoire."),
            Length(
                min=LONGUEUR_MIN_NOM_UTILISATEUR,
                max=LONGUEUR_MAX_NOM_UTILISATEUR,
                message="Le nom d'utilisateur doit contenir entre 3 et 80 caractères.",
            ),
        ],
    )

    nom = StringField("Nom", validators=[DataRequired()])

    prenom = StringField("Prénom", validators=[DataRequired()])

    telephone = StringField("Téléphone", validators=[Optional()])

    email = StringField(
        "Email",
        validators=[DataRequired(message="L'email est obligatoire."), Email(check_deliverability=False)],
    )

    role = SelectField(
        "Rôle",
        choices=[("employe", "Employé"), ("administrateur", "Administrateur")],
        validators=[DataRequired()],
    )

    nouveau_mot_de_passe = PasswordField(
        "Nouveau mot de passe (laisser vide pour ne pas changer)",
        validators=[Optional(), Length(min=LONGUEUR_MIN_MOT_DE_PASSE, message="Le mot de passe doit contenir au moins 8 caractères.")],
    )

    confirmer_nouveau_mot_de_passe = PasswordField(
        "Confirmer le nouveau mot de passe",
        validators=[Optional(), EqualTo("nouveau_mot_de_passe", message="Les mots de passe ne correspondent pas.")],
    )

    envoyer = SubmitField("Enregistrer")


# =====================================
# Formulaire Statut de facture
# =====================================
class StatutFactureForm(FlaskForm):

    statut = SelectField(
        "Statut",
        choices=[
            ("attente", "En attente"),
            ("payee", "Payée"),
            ("annulee", "Annulée"),
        ],
        validators=[DataRequired()],
    )

    envoyer = SubmitField("Mettre à jour")


# =====================================
# Formulaire Paiement (enregistrement d'un reglement chèque/carte/espèces)
# =====================================
class PaiementForm(FlaskForm):

    # InputRequired : idem ProduitForm, pour que le message affiche en cas de
    # 0 soit bien "doit etre positif" (NumberRange) et non "est obligatoire"
    # (DataRequired traiterait 0 comme absent avant meme d'atteindre NumberRange).
    montant = DecimalField(
        "Montant réglé (DH)",
        places=2,
        validators=[
            InputRequired(message="Le montant est obligatoire."),
            NumberRange(min=MONTANT_MINIMUM_PAIEMENT, message="Le montant réglé doit être positif."),
        ],
    )

    methode = SelectField(
        "Moyen de paiement",
        choices=list(METHODES_PAIEMENT.items()),
        validators=[DataRequired()],
    )

    reference = StringField(
        "Référence (n° de chèque, reçu...)",
        validators=[Optional(), Length(max=100)],
    )

    envoyer = SubmitField("Enregistrer le paiement")


# =====================================
# Formulaire Profil client (portail)
# =====================================
class ProfilClientForm(FlaskForm):

    nom = StringField("Nom", validators=[DataRequired()])

    prenom = StringField("Prénom", validators=[DataRequired()])

    telephone = StringField("Téléphone", validators=[Optional()])

    email = StringField(
        "Email",
        validators=[DataRequired(message="L'email est obligatoire."), Email(check_deliverability=False)],
    )

    adresse = StringField("Adresse", validators=[Optional()])

    mot_de_passe_actuel = PasswordField("Mot de passe actuel", validators=[Optional()])

    nouveau_mot_de_passe = PasswordField(
        "Nouveau mot de passe (laisser vide pour ne pas changer)",
        validators=[Optional(), Length(min=LONGUEUR_MIN_MOT_DE_PASSE, message="Le mot de passe doit contenir au moins 8 caractères.")],
    )

    confirmer_nouveau_mot_de_passe = PasswordField(
        "Confirmer le nouveau mot de passe",
        validators=[Optional(), EqualTo("nouveau_mot_de_passe", message="Les mots de passe ne correspondent pas.")],
    )

    envoyer = SubmitField("Enregistrer mon profil")


# =====================================
# Formulaire Profil (mon compte)
# =====================================
class ProfilForm(FlaskForm):

    nom_utilisateur = StringField(
        "Nom d'utilisateur",
        validators=[
            DataRequired(message="Le nom d'utilisateur est obligatoire."),
            Length(
                min=LONGUEUR_MIN_NOM_UTILISATEUR,
                max=LONGUEUR_MAX_NOM_UTILISATEUR,
                message="Le nom d'utilisateur doit contenir entre 3 et 80 caractères.",
            ),
        ],
    )

    nom = StringField("Nom", validators=[DataRequired()])

    prenom = StringField("Prénom", validators=[DataRequired()])

    telephone = StringField("Téléphone", validators=[Optional()])

    email = StringField(
        "Email",
        validators=[DataRequired(message="L'email est obligatoire."), Email(check_deliverability=False)],
    )

    mot_de_passe_actuel = PasswordField(
        "Mot de passe actuel",
        validators=[Optional()],
    )

    nouveau_mot_de_passe = PasswordField(
        "Nouveau mot de passe (laisser vide pour ne pas changer)",
        validators=[Optional(), Length(min=LONGUEUR_MIN_MOT_DE_PASSE, message="Le mot de passe doit contenir au moins 8 caractères.")],
    )

    confirmer_nouveau_mot_de_passe = PasswordField(
        "Confirmer le nouveau mot de passe",
        validators=[Optional(), EqualTo("nouveau_mot_de_passe", message="Les mots de passe ne correspondent pas.")],
    )

    envoyer = SubmitField("Enregistrer mon profil")