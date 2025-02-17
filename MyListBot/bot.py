import discord
from discord import app_commands
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------------------------------------------------------------
# 1) Fonctions PostgreSQL
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# 2) Données globales (catégories, statuts, stockage temporaire)
# ---------------------------------------------------------------------
CATEGORIES = ["webtoon", "série", "manga", "anime"]
STATUTS = ["à voir/lire", "en cours", "terminé"]

# Stockage en mémoire des contenus en attente d'ajout
# Clé : user_id (int), Valeur : liste de tuples (title, category, status)
pending_adds = {}

# ---------------------------------------------------------------------
# 3) Création du client et du CommandTree
# ---------------------------------------------------------------------
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ---------------------------------------------------------------------
# 4) Classes pour les Vues et les Modals
# ---------------------------------------------------------------------

class TitleModal(discord.ui.Modal, title="Saisir un titre"):
    title_input = discord.ui.TextInput(
        label="Titre",
        placeholder="Ex: One Piece",
        required=True
    )
    async def on_submit(self, interaction: discord.Interaction):
        # On ne répond rien ici, la vue parent va récupérer la valeur
        await interaction.response.defer(ephemeral=True)

class TitleCategoryStatusView(discord.ui.View):
    """
    Vue pour saisir un Titre, choisir la Catégorie et le Statut.
    """
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.title_entered = None
        self.category_selected = None
        self.status_selected = None

    @discord.ui.button(label="Saisir Titre", style=discord.ButtonStyle.secondary)
    async def enter_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Vous n'êtes pas l'utilisateur concerné.", ephemeral=True)
            return
        modal = TitleModal()
        await interaction.response.send_modal(modal)
        # On attend la fin du Modal
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
        options=[
            discord.SelectOption(label="webtoon", description="Catégorie webtoon"),
            discord.SelectOption(label="série", description="Catégorie série"),
            discord.SelectOption(label="manga", description="Catégorie manga"),
            discord.SelectOption(label="anime", description="Catégorie anime"),
        ]
    )
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Vous n'êtes pas l'utilisateur concerné.", ephemeral=True)
            return
        self.category_selected = select.values[0]
        await interaction.response.send_message(f"Catégorie sélectionnée : {self.category_selected}", ephemeral=True)

    @discord.ui.select(
        placeholder="Choisir le statut",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="à voir/lire", description="Statut à voir/lire"),
            discord.SelectOption(label="en cours", description="Statut en cours"),
            discord.SelectOption(label="terminé", description="Statut terminé"),
        ]
    )
    async def status_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Vous n'êtes pas l'utilisateur concerné.", ephemeral=True)
            return
        self.status_selected = select.values[0]
        await interaction.response.send_message(f"Statut sélectionné : {self.status_selected}", ephemeral=True)

    @discord.ui.button(label="Valider", style=discord.ButtonStyle.primary)
    async def validate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Vous n'êtes pas l'utilisateur concerné.", ephemeral=True)
            return

        if not self.title_entered or not self.category_selected or not self.status_selected:
            await interaction.response.send_message(
                "Veuillez saisir le titre, la catégorie et le statut avant de valider.",
                ephemeral=True
            )
            return

        user_id_str = str(self.user_id)
        pending_adds.setdefault(user_id_str, []).append(
            (self.title_entered, self.category_selected, self.status_selected)
        )

        await interaction.response.send_message(
            f"Contenu en attente : **{self.title_entered}** ({self.category_selected}/{self.status_selected}).\n"
            "Vous pouvez fermer cette fenêtre ou ajouter d'autres contenus via le bouton «Ajouter un contenu».",
            ephemeral=True
        )
        self.disable_all_items()
        await interaction.edit_original_response(view=self)

class AddMultiView(discord.ui.View):
    """
    Vue affichée après la commande /addmulti.
    Propose 2 boutons : "Ajouter un contenu" et "Terminer".
    """
    def __init__(self, user_id: int):
        super().__init__(timeout=300)  # 5 minutes
        self.user_id = user_id

    @discord.ui.button(label="Ajouter un contenu", style=discord.ButtonStyle.primary)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Vous n'êtes pas l'utilisateur qui a lancé la commande.", ephemeral=True)
            return

        view = TitleCategoryStatusView(self.user_id)
        await interaction.response.send_message("Veuillez renseigner le contenu :", view=view, ephemeral=True)

    @discord.ui.button(label="Terminer", style=discord.ButtonStyle.success)
    async def finish_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Vous n'êtes pas l'utilisateur qui a lancé la commande.", ephemeral=True)
            return

        user_id_str = str(self.user_id)
        if user_id_str not in pending_adds or not pending_adds[user_id_str]:
            await interaction.response.send_message("Aucun contenu en attente.", ephemeral=True)
            return

        items = pending_adds[user_id_str]
        for (title, cat, stat) in items:
            add_content(user_id_str, title, cat, stat)

        nb = len(items)
        pending_adds[user_id_str] = []  # on vide la liste

        await interaction.response.send_message(f"{nb} contenu(s) ajouté(s) en base !", ephemeral=True)
        self.disable_all_items()
        await interaction.edit_original_response(view=self)

# ---------------------------------------------------------------------
# 5) Commande /addmulti
# ---------------------------------------------------------------------
@tree.command(name="addmulti", description="Ajoute plusieurs contenus (un par un) avec choix pour catégorie/statut.")
async def addmulti(interaction: discord.Interaction):
    user_id = interaction.user.id
    view = AddMultiView(user_id)
    await interaction.response.send_message(
        "Cliquez sur «Ajouter un contenu» pour saisir vos entrées, puis «Terminer» pour valider.",
        view=view,
        ephemeral=True
    )

# ---------------------------------------------------------------------
# 6) Événement on_ready
# ---------------------------------------------------------------------
@client.event
async def on_ready():
    await tree.sync()
    print(f"{client.user} est connecté et les commandes slash sont synchronisées.")

# ---------------------------------------------------------------------
# 7) Lancement du bot
# ---------------------------------------------------------------------
client.run(DISCORD_TOKEN)
