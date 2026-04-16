import discord
from discord.ext import commands

class Invites(commands.Cog):
    """Solo rastrea invitaciones en joins (join_logs). Las despedidas van en celebrations.py (on_member_remove)."""

    def __init__(self, bot):
        self.bot = bot
        self.invites = {} # Diccionario: {guild_id: {code: uses}}

    async def get_all_invites(self, guild):
        """Obtiene todas las invitaciones de un servidor y sus usos"""
        try:
            # Es vital que el bot tenga el permiso de 'Manage Server'
            invites = await guild.invites()
            return {i.code: i.uses for i in invites}
        except Exception as e:
            print(f"❌ Error al obtener invites de {guild.name}: {e}")
            return {}

    @commands.Cog.listener()
    async def on_ready(self):
        # Llenamos el caché inicial
        for guild in self.bot.guilds:
            self.invites[guild.id] = await self.get_all_invites(guild)
        print("🔍 Monitoreo de invitaciones activo y caché lleno.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        print(f"🔔 EVENTO: {member.display_name} ha entrado a {member.guild.name}")
        
        # 1. Obtenemos el estado actual de los invites
        invites_after = await self.get_all_invites(member.guild)
        invites_before = self.invites.get(member.guild.id, {})
        
        used_invite = None
        
        # 2. Buscamos cuál cambió o cuál es nueva y tiene usos
        for code, uses in invites_after.items():
            # Caso A: El invite ya existía y subió el contador
            if code in invites_before:
                if uses > invites_before[code]:
                    used_invite_code = code
                    break
            # Caso B: Es un invite nuevo que se creó después del on_ready y ya tiene un uso
            elif uses > 0:
                used_invite_code = code
                break
        else:
            used_invite_code = None

        # 3. Si encontramos el código, buscamos el objeto invitación completo
        if used_invite_code:
            all_invites_obj = await member.guild.invites()
            used_invite = next((i for i in all_invites_obj if i.code == used_invite_code), None)

        # 4. Registro en base de datos
        if used_invite:
            print(f"✅ Invite detectado: {used_invite.code} | Creador: {used_invite.inviter}")
            stats_cog = self.bot.get_cog('Stats')
            if stats_cog:
                try:
                    await stats_cog.log_member_join(
                        usuario_id=member.id,
                        usuario_nombre=member.display_name,
                        invite_code=used_invite.code,
                        inviter_id=used_invite.inviter.id,
                        inviter_nombre=used_invite.inviter.display_name
                    )
                except Exception as e:
                    print(f"❌ Error al guardar join en DB: {e}")
        else:
            print("⚠️ No se pudo determinar qué invitación se usó (posible Link de Vanidad o error de caché).")
        
        # 5. Actualizamos el caché para la próxima entrada
        self.invites[member.guild.id] = invites_after

async def setup(bot):
    await bot.add_cog(Invites(bot))