import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()  # Charge les variables d'environnement depuis le fichier .env

# Récupère l'URL de connexion à la base (DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def create_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_lists (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Table user_lists créée (si elle n'existait pas déjà).")

if __name__ == "__main__":
    create_table()
