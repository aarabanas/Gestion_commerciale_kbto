"""Lance l'application avec un vrai serveur WSGI (waitress), accessible
depuis les autres postes du reseau interne -- contrairement a
`python app.py` (serveur de developpement Flask/Werkzeug), reserve a
127.0.0.1 et non concu pour plusieurs connexions simultanees.

Usage local (reseau interne) : venv\\Scripts\\python.exe serveur.py
Sur un hebergeur (Railway, Render...) : la plateforme fixe le port via la
variable d'environnement PORT et lance elle-meme cette commande.
"""
import os

from waitress import serve

from app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT") or os.getenv("SERVEUR_PORT", "5000"))
    print(f"Serveur KBTO demarre sur le port {port}.")
    serve(app, host="0.0.0.0", port=port)
