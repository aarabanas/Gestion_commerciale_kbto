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
)

from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    Optional,
    Email,
)

from models import STATUTS_FACTURE


# =====================================
# Formulaire de connexion
# =====================================
class ConnexionForm(FlaskForm):

    nom_utilisateur = StringField(
        "Identifiant (nom d'utilisateur ou email)",
        validators=[
            DataRequired(message="L'identifiant est obligatoire."),
            Length(min=3, max=150, message="L'identifiant doit contenir entre 3 et 150 caractères."),
        ],
    )

    mot_de_passe = PasswordField(
        "Mot de passe",
        validators=[
            DataRequired(message="Le mot de passe est obligatoire."),
            Length(min=8, message="Le mot de passe doit contenir au moins 8 caractères."),
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
            Length(min=8, message="Le mot de passe doit contenir au moins 8 caractères."),
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
    "Processeurs",
    "Cartes graphiques",
    "Mémoire RAM",
    "Stockage",
    "Cartes mères",
    "Alimentations",
    "Boîtiers",
    "Refroidissement",
    "Périphériques",
    "Autre",
]


class ProduitForm(FlaskForm):

    nom = StringField("Nom du produit", validators=[DataRequired()])

    categorie = SelectField(
        "Catégorie",
        choices=[(c, c) for c in CATEGORIES_PRODUIT],
        validators=[DataRequired()],
    )

    prix = DecimalField("Prix", places=2, validators=[DataRequired()])

    quantite = IntegerField("Quantité", validators=[DataRequired()])

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
            Length(min=3, max=80, message="Le nom d'utilisateur doit contenir entre 3 et 80 caractères."),
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
            Length(min=8, message="Le mot de passe doit contenir au moins 8 caractères."),
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
            Length(min=3, max=80, message="Le nom d'utilisateur doit contenir entre 3 et 80 caractères."),
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
        validators=[Optional(), Length(min=8, message="Le mot de passe doit contenir au moins 8 caractères.")],
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
        validators=[Optional(), Length(min=8, message="Le mot de passe doit contenir au moins 8 caractères.")],
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
            Length(min=3, max=80, message="Le nom d'utilisateur doit contenir entre 3 et 80 caractères."),
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
        validators=[Optional(), Length(min=8, message="Le mot de passe doit contenir au moins 8 caractères.")],
    )

    confirmer_nouveau_mot_de_passe = PasswordField(
        "Confirmer le nouveau mot de passe",
        validators=[Optional(), EqualTo("nouveau_mot_de_passe", message="Les mots de passe ne correspondent pas.")],
    )

    envoyer = SubmitField("Enregistrer mon profil")