import discord
from discord import app_commands
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Fonctions de connexion à PostgreSQL ---
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def add_content(user_id: str, title: str, category: str, status: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_lists (user_id, title, category, status)
        VALUES (%s, %s, %s, %s);
    """, (user_id, title, category, status))
    conn.commit()
    cur.close()
    conn.close()

def remove_content(user_id: str, title: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM user_lists
        WHERE user_id = %s AND LOWER(title) = LOWER(%s);
    """, (user_id, title))
    conn.commit()
    cur.close()
    conn.close()

def update_content_status(user_id: str, title: str, new_status: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE user_lists
        SET status = %s
        WHERE user_id = %s AND LOWER(title) = LOWER(%s);
    """, (new_status, user_id, title))
    conn.commit()
    cur.close()
    conn.close()

def get_user_list(user_id: str, filter_value: str = None):
    conn = get_connection()
    cur = conn.cursor()
    if filter_value:
        cur.execute("""
            SELECT title, category, status FROM user_lists
            WHERE user_id = %s AND (LOWER(category) = LOWER(%s) OR LOWER(status) = LOWER(%s))
            ORDER BY category;
        """, (user_id, filter_value, filter_value))
    else:
        cur.execute("""
            SELECT title, category, status FROM user_lists
            WHERE user_id = %s
            ORDER BY category;
        """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# --- Définition des catégories et statuts possibles ---
CATEGORIES = ["webtoon", "série", "manga", "anime"]
STATUTS = ["à voir/lire", "en cours", "terminé"]

# --- Initialisation du bot Discord et de l'arbre des commandes slash ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Commande : /add
@tree.command(name="add", description="Ajoute un contenu à ta liste.")
@app_commands.describe(
    title="Titre du contenu",
    category="Catégorie (webtoon, série, manga, anime)",
    status="Statut (à voir/lire, en cours, terminé)"
)
async def add(interaction: discord.Interaction, title: str, category: str, status: str):
    if category.lower() not in CATEGORIES:
        await interaction.response.send_message(f"Catégorie invalide. Choisis parmi : {', '.join(CATEGORIES)}.")
        return
    if status.lower() not in STATUTS:
        await interaction.response.send_message(f"Statut invalide. Choisis parmi : {', '.join(STATUTS)}.")
        return
    add_content(str(interaction.user.id), title, category.lower(), status.lower())
    await interaction.response.send_message(f"Ajouté : **{title}** ({category.lower()}) avec le statut **{status.lower()}**.")

# Commande : /remove
@tree.command(name="remove", description="Supprime un contenu de ta liste.")
@app_commands.describe(
    title="Titre du contenu à supprimer"
)
async def remove(interaction: discord.Interaction, title: str):
    remove_content(str(interaction.user.id), title)
    await interaction.response.send_message(f"Supprimé : **{title}**.")

# Commande : /update
@tree.command(name="update", description="Modifie le statut d'un contenu dans ta liste.")
@app_commands.describe(
    title="Titre du contenu à mettre à jour",
    status="Nouveau statut (à voir/lire, en cours, terminé)"
)
async def update(interaction: discord.Interaction, title: str, status: str):
    if status.lower() not in STATUTS:
        await interaction.response.send_message(f"Statut invalide. Choisis parmi : {', '.join(STATUTS)}.")
        return
    update_content_status(str(interaction.user.id), title, status.lower())
    await interaction.response.send_message(f"Mise à jour : **{title}** est maintenant **{status.lower()}**.")

# Commande : /mylist
@tree.command(name="mylist", description="Affiche ta liste de contenus.")
@app_commands.describe(
    filter="(Optionnel) Filtre par une catégorie (webtoon, série, manga, anime) ou par un statut (à voir/lire, en cours, terminé)"
)
async def mylist(interaction: discord.Interaction, filter: str = None):
    rows = get_user_list(str(interaction.user.id), filter)
    if not rows:
        await interaction.response.send_message("Aucun contenu trouvé.")
        return
    message = ""
    if not filter:
        grouped = {}
        for title, category, status in rows:
            grouped.setdefault(category, []).append((title, status))
        for cat in CATEGORIES:
            if cat in grouped:
                message += f"**{cat.capitalize()}**:\n"
                for title, status in grouped[cat]:
                    message += f"- **{title}** | {status}\n"
    else:
        message = f"Résultats pour le filtre **{filter}** :\n"
        for title, category, status in rows:
            message += f"- **{title}** | {category} | {status}\n"
    await interaction.response.send_message(message)

# Commande : /listuser
@tree.command(name="listuser", description="Affiche la liste d'un autre utilisateur.")
@app_commands.describe(
    user="Mentionne l'utilisateur",
    filter="(Optionnel) Filtre par une catégorie ou par un statut"
)
async def listuser(interaction: discord.Interaction, user: discord.User, filter: str = None):
    rows = get_user_list(str(user.id), filter)
    if not rows:
        await interaction.response.send_message(f"Aucun contenu trouvé pour {user.display_name}.")
        return
    message = f"Liste de **{user.display_name}** :\n"
    if not filter:
        grouped = {}
        for title, category, status in rows:
            grouped.setdefault(category, []).append((title, status))
        for cat in CATEGORIES:
            if cat in grouped:
                message += f"**{cat.capitalize()}**:\n"
                for title, status in grouped[cat]:
                    message += f"- **{title}** | {status}\n"
    else:
        message += f"(Filtre : {filter})\n"
        for title, category, status in rows:
            message += f"- **{title}** | {category} | {status}\n"
    await interaction.response.send_message(message)

# --- Nouvelles commandes pour opérations multiples avec séparation par virgules et point-virgule ---

# Commande : /addmulti
@tree.command(name="addmulti", description="Ajoute plusieurs contenus en une fois. Chaque entrée doit être au format: titre, catégorie, statut. Sépare les entrées par un point-virgule (;).")
@app_commands.describe(
    entries="Liste des contenus, par exemple: One Piece, manga, en cours; Naruto, manga, terminé"
)
async def addmulti(interaction: discord.Interaction, entries: str):
    # Sépare les entrées par le point-virgule
    items = [item.strip() for item in entries.split(";") if item.strip()]
    added = []
    errors = []
    for item in items:
        parts = [part.strip() for part in item.split(",")]
        if len(parts) != 3:
            errors.append(f"L'entrée invalide (doit contenir 3 champs): {item}")
            continue
        title, category, status = parts
        if category.lower() not in CATEGORIES:
            errors.append(f"Catégorie invalide pour '{title}': {category}")
            continue
        if status.lower() not in STATUTS:
            errors.append(f"Statut invalide pour '{title}': {status}")
            continue
        try:
            add_content(str(interaction.user.id), title, category.lower(), status.lower())
            added.append(title)
        except Exception as e:
            errors.append(f"Erreur pour '{title}': {str(e)}")
    msg = ""
    if added:
        msg += "Ajoutés: " + ", ".join(added) + ".\n"
    if errors:
        msg += "Erreurs:\n" + "\n".join(errors)
    await interaction.response.send_message(msg)

# Commande : /updatemulti
@tree.command(name="updatemulti", description="Met à jour le statut de plusieurs contenus en une fois. Chaque entrée doit être au format: titre, nouveau statut. Sépare les entrées par un point-virgule (;).")
@app_commands.describe(
    updates="Liste des mises à jour, par exemple: One Piece, terminé; Naruto, en cours"
)
async def updatemulti(interaction: discord.Interaction, updates: str):
    items = [item.strip() for item in updates.split(";") if item.strip()]
    updated = []
    errors = []
    for item in items:
        parts = [part.strip() for part in item.split(",")]
        if len(parts) != 2:
            errors.append(f"L'entrée invalide (doit contenir 2 champs): {item}")
            continue
        title, new_status = parts
        if new_status.lower() not in STATUTS:
            errors.append(f"Statut invalide pour '{title}': {new_status}")
            continue
        try:
            update_content_status(str(interaction.user.id), title, new_status.lower())
            updated.append(title)
        except Exception as e:
            errors.append(f"Erreur pour '{title}': {str(e)}")
    msg = ""
    if updated:
        msg += "Mises à jour effectuées pour: " + ", ".join(updated) + ".\n"
    if errors:
        msg += "Erreurs:\n" + "\n".join(errors)
    await interaction.response.send_message(msg)

# Commande : /removemulti
@tree.command(name="removemulti", description="Supprime plusieurs contenus en une fois. Fournis une liste de titres séparés par des virgules.")
@app_commands.describe(
    titles="Liste des titres à supprimer, par exemple: One Piece, Naruto, Demon Slayer"
)
async def removemulti(interaction: discord.Interaction, titles: str):
    # Sépare les titres par des virgules
    items = [item.strip() for item in titles.split(",") if item.strip()]
    removed = []
    errors = []
    for title in items:
        try:
            remove_content(str(interaction.user.id), title)
            removed.append(title)
        except Exception as e:
            errors.append(f"Erreur pour '{title}': {str(e)}")
    msg = ""
    if removed:
        msg += "Supprimés: " + ", ".join(removed) + ".\n"
    if errors:
        msg += "Erreurs:\n" + "\n".join(errors)
    await interaction.response.send_message(msg)

@client.event
async def on_ready():
    await tree.sync()
    print(f"{client.user} est connecté et les commandes slash sont synchronisées.")

client.run(DISCORD_TOKEN)
