# ============================================================
# Furibot - Entrada principal
# Descripción: Inicializa el bot, carga los módulos (cogs) y
#              sincroniza los comandos slash con Discord.
# Autor: Javier Santos
# ============================================================

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")


class FuriBot(commands.Bot):
    """Clase principal del bot. Gestiona la carga de cogs y sincronización de comandos."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """
        Se ejecuta automáticamente antes de conectarse a Discord.
        Carga todos los módulos de la carpeta /cogs y sincroniza los comandos slash.
        """
        print("[INFO] Iniciando carga de módulos...")

        # --- Carga de cogs ---
        if os.path.exists('./cogs'):
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        print(f"[INFO] Módulo cargado: {filename}")
                    except Exception as e:
                        print(f"[ERROR] Al cargar {filename}: {e}")
        else:
            print("[WARN] No se encontró la carpeta './cogs'")

        # --- Sincronización de comandos slash ---
        # Si hay GUILD_ID configurado, sincroniza por servidor (instantáneo).
        # Sin GUILD_ID, sincroniza globalmente (puede tardar hasta 1 hora en reflejarse).
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"[INFO] Comandos sincronizados en guild {GUILD_ID}: {len(synced)}")
        else:
            synced = await self.tree.sync()
            print(f"[INFO] Comandos sincronizados globalmente: {len(synced)}")

    async def on_ready(self):
        """Se ejecuta cuando el bot se conecta exitosamente a Discord."""
        print(f"[INFO] Logueado como {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Game(name="BOtcito para el server")
        )


# -------------------------------------------------------
# Punto de entrada
# -------------------------------------------------------

if __name__ == "__main__":
    bot = FuriBot()
    bot.run(TOKEN)
