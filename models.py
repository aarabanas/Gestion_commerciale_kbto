from decimal import Decimal

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

db = SQLAlchemy()

# Statuts possibles d'une facture : code stocke en base -> libelle affiche
STATUTS_FACTURE = {
    "attente": "En attente",
    "payee": "Payée",
    "annulee": "Annulée",
}

# Moyens de paiement acceptes : code stocke en base -> libelle affiche
METHODES_PAIEMENT = {
    "cheque": "Chèque",
    "carte": "Carte bancaire",
    "espece": "Espèces",
    "en_ligne": "Paiement en ligne",
}


# ===========================
# UTILISATEUR
# ===========================
class Utilisateur(UserMixin, db.Model):
    __tablename__ = "utilisateurs"

    id = db.Column(db.Integer, primary_key=True)
    nom_utilisateur = db.Column(db.String(80), unique=True, nullable=True, index=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="employe")

    def definir_mot_de_passe(self, mot_de_passe):
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe):
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)

    def __repr__(self):
        return f"<Utilisateur {self.nom_utilisateur}>"


# ===========================
# CLIENT
# ===========================
class Client(UserMixin, db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True)
    telephone = db.Column(db.String(20))
    adresse = db.Column(db.String(255))
    mot_de_passe_hash = db.Column(db.String(255), nullable=True)

    factures = db.relationship("Facture", back_populates="client", lazy=True)

    # Un Client authentifie n'est jamais confondu avec un Utilisateur (employe/
    # administrateur) : get_id() est prefixe pour que le user_loader sache
    # dans quelle table chercher, et `role` permet aux templates partages de
    # distinguer les deux sans lever d'AttributeError.
    role = "client"

    def get_id(self):
        return f"client-{self.id}"

    def a_un_compte(self):
        return self.mot_de_passe_hash is not None

    def definir_mot_de_passe(self, mot_de_passe):
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe):
        if not self.mot_de_passe_hash:
            return False
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)

    def __repr__(self):
        return f"<Client {self.nom} {self.prenom}>"


# ===========================
# PRODUIT
# ===========================
class Produit(db.Model):
    __tablename__ = "produits"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prix = db.Column(db.Numeric(10, 2), nullable=False)
    quantite = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text)
    categorie = db.Column(db.String(80), nullable=True)

    def __repr__(self):
        return f"<Produit {self.nom}>"


# ===========================
# FACTURE
# ===========================
class Facture(db.Model):
    __tablename__ = "factures"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, server_default=db.func.now())
    total = db.Column(db.Numeric(10, 2), default=Decimal("0"))
    statut = db.Column(db.String(30), default="attente")
    envoyee = db.Column(db.Boolean, nullable=False, default=False)
    date_envoi = db.Column(db.DateTime, nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"))

    client = db.relationship("Client", back_populates="factures")
    details = db.relationship(
        "DetailFacture",
        back_populates="facture",
        lazy=True,
        cascade="all, delete-orphan",
    )
    paiements = db.relationship(
        "Paiement",
        back_populates="facture",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Paiement.date_paiement",
    )

    @property
    def numero(self):
        return f"FA-{self.id:04d}"

    @property
    def statut_libelle(self):
        return STATUTS_FACTURE.get(self.statut, self.statut)

    @property
    def montant_paye(self):
        return sum((p.montant for p in self.paiements), Decimal("0"))

    @property
    def montant_restant(self):
        reste = (self.total or Decimal("0")) - self.montant_paye
        return reste if reste > 0 else Decimal("0")

    def __repr__(self):
        return f"<Facture #{self.id}>"


# ===========================
# DETAIL FACTURE
# ===========================
class DetailFacture(db.Model):
    __tablename__ = "details_facture"

    id = db.Column(db.Integer, primary_key=True)
    facture_id = db.Column(db.Integer, db.ForeignKey("factures.id"))
    produit_id = db.Column(db.Integer, db.ForeignKey("produits.id"))
    quantite = db.Column(db.Integer, nullable=False)
    prix_unitaire = db.Column(db.Numeric(10, 2), nullable=False)

    facture = db.relationship("Facture", back_populates="details")
    produit = db.relationship("Produit")

    def __repr__(self):
        return f"<DetailFacture facture={self.facture_id} produit={self.produit_id}>"


# ===========================
# PAIEMENT
# ===========================
class Paiement(db.Model):
    __tablename__ = "paiements"

    id = db.Column(db.Integer, primary_key=True)
    facture_id = db.Column(db.Integer, db.ForeignKey("factures.id"), nullable=False)
    montant = db.Column(db.Numeric(10, 2), nullable=False)
    methode = db.Column(db.String(20), nullable=False)
    reference = db.Column(db.String(100), nullable=True)
    date_paiement = db.Column(db.DateTime, server_default=db.func.now())

    facture = db.relationship("Facture", back_populates="paiements")

    @property
    def methode_libelle(self):
        return METHODES_PAIEMENT.get(self.methode, self.methode)

    def __repr__(self):
        return f"<Paiement {self.montant} DH ({self.methode}) facture={self.facture_id}>"


# ===========================
# PARAMETRES DE L'ENTREPRISE
# ===========================
class Parametres(db.Model):
    __tablename__ = "parametres"

    id = db.Column(db.Integer, primary_key=True)
    nom_entreprise = db.Column(db.String(150), default="KBTO")
    identifiant_fiscal = db.Column(db.String(50))
    adresse = db.Column(db.String(255))
    telephone = db.Column(db.String(30))
    email = db.Column(db.String(150))
    taux_tva = db.Column(db.Float, default=20.0)
    logo = db.Column(db.String(255))
    objectif_ca_mensuel = db.Column(db.Numeric(10, 2), default=Decimal("50000"))

    @staticmethod
    def obtenir():
        """Renvoie l'unique ligne de parametres, en la creant si besoin."""
        p = Parametres.query.first()
        if p is None:
            p = Parametres(nom_entreprise="KBTO", taux_tva=20.0, objectif_ca_mensuel=Decimal("50000"))
            db.session.add(p)
            db.session.commit()
        return p

    def __repr__(self):
        return f"<Parametres {self.nom_entreprise}>"