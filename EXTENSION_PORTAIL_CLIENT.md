# Addendum au cahier des charges — Portail client

> Ce document complète le cahier des charges initial (PARTIE 1). Il documente
> une extension de périmètre décidée après la livraison initiale, à présenter
> telle quelle en soutenance : ce qui a changé, pourquoi, et comment.

## 1. Changement de périmètre

Le cahier des charges initial (§3, tableau des exclusions) excluait
explicitement :

- « Portail libre-service pour les clients externes »
- « Paiement en ligne et suivi des encaissements »

**Ces deux exclusions sont levées** à la demande du porteur de projet : les
clients de KBTO disposent désormais d'un espace personnel pour suivre leurs
commandes et régler leurs factures en ligne.

Le reste du périmètre initial (§3) est inchangé : toujours un seul
établissement (pas de multi-entrepôts), pas de génération de devis, pas de
comptabilité générale.

## 2. Nouveaux besoins fonctionnels (portail client)

| Réf | Besoin | Statut |
|---|---|---|
| P-01 | Un client peut créer un compte depuis la page de connexion | Fait |
| P-02 | Un client se connecte avec son email + mot de passe (même page que le personnel) | Fait |
| P-03 | Un client voit un tableau de bord : résumé des achats, montant total des factures, commandes en cours | Fait |
| P-04 | Un client consulte le catalogue produits (prix, disponibilité), avec recherche | Fait |
| P-05 | Un client passe une nouvelle commande (sélection de produits + quantités) | Fait |
| P-06 | Un client consulte l'historique de ses commandes et leur statut | Fait |
| P-07 | Un client consulte ses factures, les télécharge en PDF ou les imprime | Fait |
| P-08 | Un client distingue ses factures payées / impayées | Fait |
| P-09 | Un client consulte l'historique de ses paiements | Fait |
| P-10 | Un client paie une facture en ligne | Fait (Stripe, mode test) |
| P-11 | Un client modifie ses informations personnelles et son mot de passe | Fait |
| P-12 | Un espace personnel (employé/administrateur) et un espace client sont strictement séparés | Fait |

## 3. Choix techniques et simplifications assumées

- **« Commande » = « Facture », vue côté client.** Plutôt que de créer un
  nouveau modèle `Commande` avec son propre cycle de vie (en attente →
  validée → livrée), le portail réutilise le modèle `Facture` existant et ses
  statuts (`attente` / `payée` / `annulée`). C'est un choix de simplicité
  assumé : pas de suivi de livraison physique dans cette version, la
  distinction entre « passer une commande » et « émettre une facture »
  disparaît côté client.
- **Paiement en ligne : Stripe Checkout, mode test.** Aucune vraie
  transaction bancaire n'a lieu. La clé secrète (`STRIPE_SECRET_KEY`, à
  fournir via variable d'environnement) est une clé de *test* Stripe ; tant
  qu'elle n'est pas configurée, le bouton « Payer » affiche un message
  explicite au lieu de planter. Le paiement est confirmé via l'API Stripe au
  retour de la redirection (pas de webhook exposé publiquement, ce qui
  suffit en développement local).
- **Séparation des espaces.** Un `Client` authentifié (nouveau : mot de passe
  optionnel ajouté au modèle `Client`) et un `Utilisateur` (employé/admin)
  ne peuvent jamais accéder aux routes de l'autre espace : un garde
  applicatif redirige automatiquement en cas d'erreur d'aiguillage, et
  chaque facture consultée côté client est vérifiée comme lui appartenant
  (sinon 404).
- **Compte client existant vs nouveau compte.** Un client déjà enregistré par
  un employé (sans mot de passe) n'est pas automatiquement rattaché à une
  inscription portant le même email ; ce cas (« réclamer » un compte
  existant) n'est pas couvert par cette version.

## 4. Ce qui n'a pas changé

- Le personnel (employé/administrateur) continue de créer/gérer clients,
  produits et factures exactement comme avant.
- La facture PDF (F-21) reste inchangée dans son contenu (en-tête, HT/TVA/TTC).
