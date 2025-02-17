import discord
from discord import app_commands
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GUILD_ID = os.getenv("GUILD_ID")
if GUILD_ID:
    GUILD_ID = int(GUILD_ID)
else:
    GUILD_ID = None

# ------------------------------
# Fonctions d'accès à PostgreSQL
# ------------------------------
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

# ------------------------------
# Données globales
# ------------------------------
CATEGORIES = ["webtoon", "série", "manga", "anime"]
STATUTS = ["à voir/lire", "en cours", "terminé"]

# ------------------------------
# Initialisation du client et du CommandTree
# ------------------------------
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# -------------------------------------------------------
# Commandes slash individuelles avec choix prédéfinis
# -------------------------------------------------------

@tree.command(name="add", description="Ajoute un contenu à ta liste.")
@app_commands.describe(
    title="Titre du contenu"
)
@app_commands.choices(
    category=[
        app_commands.Choice(name="Webtoon", value="webtoon"),
        app_commands.Choice(name="Série", value="série"),
        app_commands.Choice(name="Manga", value="manga"),
        app_commands.Choice(name="Anime", value="anime")
    ],
    status=[
        app_commands.Choice(name="À voir/lire", value="à voir/lire"),
        app_commands.Choice(name="En cours", value="en cours"),
        app_commands.Choice(name="Terminé", value="terminé")
    ]
)
async def add(interaction: discord.Interaction, title: str, category: app_commands.Choice[str], status: app_commands.Choice[str]):
    add_content(str(interaction.user.id), title, category.value, status.value)
    await interaction.response.send_message(f"Ajouté : **{title}** ({category.value}) avec le statut **{status.value}**.")

@tree.command(name="remove", description="Supprime un contenu de ta liste.")
@app_commands.describe(
    title="Titre du contenu à supprimer"
)
async def remove(interaction: discord.Interaction, title: str):
    remove_content(str(interaction.user.id), title)
    await interaction.response.send_message(f"Supprimé : **{title}**.")

@tree.command(name="update", description="Modifie le statut d'un contenu dans ta liste.")
@app_commands.describe(
    title="Titre du contenu à mettre à jour"
)
@app_commands.choices(
    new_status=[
        app_commands.Choice(name="À voir/lire", value="à voir/lire"),
        app_commands.Choice(name="En cours", value="en cours"),
        app_commands.Choice(name="Terminé", value="terminé")
    ]
)
async def update(interaction: discord.Interaction, title: str, new_status: app_commands.Choice[str]):
    update_content_status(str(interaction.user.id), title, new_status.value)
    await interaction.response.send_message(f"Mise à jour : **{title}** est maintenant **{new_status.value}**.")

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

# -------------------------------------------------------
# Commandes multi via modales et vues interactives
# -------------------------------------------------------

# Stockage temporaire pour les opérations multi
pending_adds = {}      # user_id (str) -> list of (title, category, status)
pending_updates = {}   # user_id (str) -> list of (title, new_status)
pending_removes = {}   # user_id (str) -> list of titles

# Modal pour la saisie du titre (utilisé dans addmulti)
class TitleModal(discord.ui.Modal, title="Saisir un titre"):
    title_input = discord.ui.TextInput(label="Titre", placeholder="Ex: One Piece", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

# Vue interactive pour saisir titre, catégorie et statut
class TitleCategoryStatusView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.title_entered = None
        self.category_selected = None
        self.status_selected = None

    @discord.ui.button(label="Saisir Titre", style=discord.ButtonStyle.secondary)
    async def enter_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non autorisé.", ephemeral=True)
            return
        modal = TitleModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            await interaction.followup.send("Délai dépassé pour la saisie du titre.", ephemeral=True)
            return
        self.title_entered = modal.title_input.value
        await interaction.followup.send(f"Titre enregistré : **{self.title_entered}**", ephemeral=True)

    @discord.ui.select(
        placeholder="Choisir la catégorie",
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label=cat, description=f"Catégorie {cat}") for cat in CATEGORIES]
    )
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non autorisé.", ephemeral=True)
            return
        self.category_selected = select.values[0]
        await interaction.response.send_message(f"Catégorie sélectionnée : {self.category_selected}", ephemeral=True)

    @discord.ui.select(
        placeholder="Choisir le statut",
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label=stat, description=f"Statut {stat}") for stat in STATUTS]
    )
    async def status_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non autorisé.", ephemeral=True)
            return
        self.status_selected = select.values[0]
        await interaction.response.send_message(f"Statut sélectionné : {self.status_selected}", ephemeral=True)

    @discord.ui.button(label="Valider", style=discord.ButtonStyle.primary)
    async def validate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non autorisé.", ephemeral=True)
            return
        if not self.title_entered or not self.category_selected or not self.status_selected:
            await interaction.response.send_message("Veuillez remplir tous les champs.", ephemeral=True)
            return
        user_id_str = str(self.user_id)
        pending_adds.setdefault(user_id_str, []).append((self.title_entered, self.category_selected, self.status_selected))
        await interaction.response.send_message(
            f"Contenu enregistré en attente : **{self.title_entered}** ({self.category_selected}/{self.status_selected}).",
            ephemeral=True
        )
        self.disable_all_items()
        await interaction.edit_original_response(view=self)

# Vue pour la commande /addmulti
class AddMultiView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label="Ajouter un contenu", style=discord.ButtonStyle.primary)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non autorisé.", ephemeral=True)
            return
        view = TitleCategoryStatusView(self.user_id)
        await interaction.response.send_message("Veuillez saisir le contenu :", view=view, ephemeral=True)

    @discord.ui.button(label="Terminer", style=discord.ButtonStyle.success)
    async def finish_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non autorisé.", ephemeral=True)
            return
        user_id_str = str(self.user_id)
        if user_id_str not in pending_adds or not pending_adds[user_id_str]:
            await interaction.response.send_message("Aucun contenu en attente.", ephemeral=True)
            return
        items = pending_adds[user_id_str]
        for (title, cat, stat) in items:
            add_content(user_id_str, title, cat, stat)
        nb = len(items)
        pending_adds[user_id_str] = []
        await interaction.response.send_message(f"{nb} contenu(s) ajouté(s) en base !", ephemeral=True)
        self.disable_all_items()
        await interaction.edit_original_response(view=self)

@tree.command(name="addmulti", description="Ajoute plusieurs contenus via une interface interactive.")
async def addmulti(interaction: discord.Interaction):
    view = AddMultiView(interaction.user.id)
    await interaction.response.send_message(
        "Cliquez sur 'Ajouter un contenu' pour saisir vos entrées, puis sur 'Terminer' pour valider.",
        view=view,
        ephemeral=True
    )

# Modal pour multi update
class UpdateMultiModal(discord.ui.Modal, title="Mise à jour multiple"):
    updates = discord.ui.TextInput(
        label="Mises à jour",
        style=discord.TextStyle.long,
        placeholder="One Piece, terminé\nNaruto, en cours",
        required=True
    )
    async def on_submit(self, interaction: discord.Interaction):
        user_id_str = str(interaction.user.id)
        pending_updates.setdefault(user_id_str, [])
        lines = self.updates.value.splitlines()
        for line in lines:
            parts = [part.strip() for part in line.split(",")]
            if len(parts) != 2:
                continue
            title, new_status = parts
            if new_status.lower() not in STATUTS:
                continue
            pending_updates[user_id_str].append((title, new_status.lower()))
        await interaction.response.send_message("Mises à jour enregistrées en attente. Utilisez /updatemultifinish pour valider.", ephemeral=True)

@tree.command(name="updatemulti", description="Enregistre plusieurs mises à jour via une modal.")
async def updatemulti(interaction: discord.Interaction):
    modal = UpdateMultiModal()
    await interaction.response.send_modal(modal)

@tree.command(name="updatemultifinish", description="Valide les mises à jour multiples enregistrées.")
async def updatemultifinish(interaction: discord.Interaction):
    user_id_str = str(interaction.user.id)
    if user_id_str not in pending_updates or not pending_updates[user_id_str]:
        await interaction.response.send_message("Aucune mise à jour en attente.", ephemeral=True)
        return
    for title, new_status in pending_updates[user_id_str]:
        update_content_status(user_id_str, title, new_status)
    nb = len(pending_updates[user_id_str])
    pending_updates[user_id_str] = []
    await interaction.response.send_message(f"{nb} mise(s) à jour effectuée(s).", ephemeral=True)

# Modal pour multi remove
class RemoveMultiModal(discord.ui.Modal, title="Suppression multiple"):
    titles = discord.ui.TextInput(
        label="Titres à supprimer",
        style=discord.TextStyle.long,
        placeholder="One Piece\nNaruto\nDemon Slayer",
        required=True
    )
    async def on_submit(self, interaction: discord.Interaction):
        user_id_str = str(interaction.user.id)
        pending_removes.setdefault(user_id_str, [])
        lines = self.titles.value.splitlines()
        for line in lines:
            title = line.strip()
            if title:
                pending_removes[user_id_str].append(title)
        await interaction.response.send_message("Titres enregistrés en attente de suppression. Utilisez /removemultifinish pour valider.", ephemeral=True)

@tree.command(name="removemulti", description="Enregistre plusieurs suppressions via une modal.")
async def removemulti(interaction: discord.Interaction):
    modal = RemoveMultiModal()
    await interaction.response.send_modal(modal)

@tree.command(name="removemultifinish", description="Valide les suppressions multiples enregistrées.")
async def removemultifinish(interaction: discord.Interaction):
    user_id_str = str(interaction.user.id)
    if user_id_str not in pending_removes or not pending_removes[user_id_str]:
        await interaction.response.send_message("Aucun contenu en attente de suppression.", ephemeral=True)
        return
    for title in pending_removes[user_id_str]:
        remove_content(user_id_str, title)
    nb = len(pending_removes[user_id_str])
    pending_removes[user_id_str] = []
    await interaction.response.send_message(f"{nb} suppression(s) effectuée(s).", ephemeral=True)

# ------------------------------
# Événement on_ready avec synchronisation par guilde
# ------------------------------
@client.event
async def on_ready():
    if GUILD_ID:
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Commandes synchronisées sur la guilde {GUILD_ID}.")
    else:
        await tree.sync()
        print("Commandes synchronisées globalement.")
    print(f"{client.user} est connecté.")

client.run(DISCORD_TOKEN)
