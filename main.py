import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Secretos/config solo desde .env (no se imprime nada por consola).
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

class AegisBot(commands.Bot):
    def __init__(self):
        # Definimos los permisos necesarios
        intents = discord.Intents.default()
        intents.members = True 
        intents.message_content = True
        
        # Llamamos al constructor de la clase base
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """Este método se ejecuta antes de que el bot se conecte a Discord."""
        print("--- Iniciando carga de módulos ---")
        
        # Verificamos que la carpeta exista para evitar errores
        if os.path.exists('./cogs'):
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        print(f'✅ Módulo cargado: {filename}')
                    except Exception as e:
                        print(f'❌ Error al cargar {filename}: {e}')
        else:
            print("⚠️ Advertencia: No se encontró la carpeta './cogs'")

        # Sincronizamos comandos por servidor para que aparezcan al instante.
        # Si no hay GUILD_ID, usa sync global (puede tardar en reflejarse).
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"--- Comandos sincronizados en guild {GUILD_ID}: {len(synced)} ---")
        else:
            synced = await self.tree.sync()
            print(f"--- Comandos sincronizados globalmente: {len(synced)} ---")

    async def on_ready(self):
        print(f'Logueado como {self.user} (ID: {self.user.id})')
        # El estado personalizado queda genial
        await self.change_presence(
            activity=discord.Game(name="BOtcito para el server")
        )

# Ejecución del bot
if __name__ == "__main__":
    bot = AegisBot()
    bot.run(TOKEN)
