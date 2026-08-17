"""Lance l'application avec un vrai serveur WSGI (waitress), accessible
depuis les autres postes du reseau interne -- contrairement a
`python app.py` (serveur de developpement Flask/Werkzeug), reserve a
127.0.0.1 et non concu pour plusieurs connexions simultanees.

Usage : venv\\Scripts\\python.exe serveur.py
"""
import os

from waitress import serve

from app import app

if __name__ == "__main__":
    port = int(os.getenv("SERVEUR_PORT", "5000"))
    print(f"Serveur KBTO demarre sur le port {port} (accessible depuis le reseau local).")
    serve(app, host="0.0.0.0", port=port)
