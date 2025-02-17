import discord
from discord import app_commands
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Fonctions d'accès à PostgreSQL ---
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

# --- Définition des catégories et statuts ---
CATEGORIES = ["webtoon", "série", "manga", "anime"]
STATUTS = ["à voir/lire", "en cours", "terminé"]

# --- Initialisation du bot Discord et de l'arbre des commandes slash ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# -----------------------------------------
# 1) Commande /add avec choix prédéfinis
# -----------------------------------------
@tree.command(name="add", description="Ajoute un contenu à ta liste.")
@app_commands.describe(
    title="Titre du contenu"
)
@app_commands.choices(
    category=[
        app_commands.Choice(name="Webtoon", value="webtoon"),
        app_commands.Choice(name="Série", value="série"),
        app_commands.Choice(name="Manga", value="manga"),
        app_commands.Choice(name="Anime", value="anime"),
    ],
    status=[
        app_commands.Choice(name="À voir/lire", value="à voir/lire"),
        app_commands.Choice(name="En cours", value="en cours"),
        app_commands.Choice(name="Terminé", value="terminé"),
    ]
)
async def add(
    interaction: discord.Interaction,
    title: str,
    category: app_commands.Choice[str],
    status: app_commands.Choice[str]
):
    # Les champs category et status sont de type app_commands.Choice
    # Pour récupérer la valeur réelle, on utilise category.value et status.value
    add_content(str(interaction.user.id), title, category.value, status.value)
    await interaction.response.send_message(
        f"Ajouté : **{title}** ({category.value}) avec le statut **{status.value}**."
    )

# -----------------------------------------
# 2) Commande /update avec choix prédéfinis
# -----------------------------------------
@tree.command(name="update", description="Modifie le statut d'un contenu dans ta liste.")
@app_commands.describe(
    title="Titre du contenu à mettre à jour"
)
@app_commands.choices(
    new_status=[
        app_commands.Choice(name="À voir/lire", value="à voir/lire"),
        app_commands.Choice(name="En cours", value="en cours"),
        app_commands.Choice(name="Terminé", value="terminé"),
    ]
)
async def update(
    interaction: discord.Interaction,
    title: str,
    new_status: app_commands.Choice[str]
):
    update_content_status(str(interaction.user.id), title, new_status.value)
    await interaction.response.send_message(
        f"Mise à jour : **{title}** est maintenant **{new_status.value}**."
    )

# -----------------------------------------
# 3) Commande /remove
# (pas de choix car c'est juste un titre)
# -----------------------------------------
@tree.command(name="remove", description="Supprime un contenu de ta liste.")
@app_commands.describe(
    title="Titre du contenu à supprimer"
)
async def remove(interaction: discord.Interaction, title: str):
    remove_content(str(interaction.user.id), title)
    await interaction.response.send_message(f"Supprimé : **{title}**.")

# -----------------------------------------
# 4) Commande /mylist (sans changement)
# -----------------------------------------
@tree.command(name="mylist", description="Affiche ta liste de contenus.")
@app_commands.describe(
    filter="(Optionnel) Filtre par une catégorie ou par un statut"
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

# -----------------------------------------
# 5) Commande /listuser (sans changement)
# -----------------------------------------
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
    grouped = {}
    if not filter:
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

# -----------------------------------------
# Événement on_ready pour synchroniser
# -----------------------------------------
@client.event
async def on_ready():
    await tree.sync()
    print(f"{client.user} est connecté et les commandes slash sont synchronisées.")

client.run(DISCORD_TOKEN)
