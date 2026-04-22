# ============================================================
# Furibot - Módulo: Invites
# Descripción: Rastrea qué invitación usó cada miembro al unirse
#              y registra la entrada en la base de datos (join_logs).
#              Los mensajes de despedida se manejan en celebrations.py.
# Autor: Javier Santos
# ============================================================

import discord
from discord.ext import commands


class Invites(commands.Cog):
    """Cog de rastreo de invitaciones. Detecta qué enlace usó cada miembro al entrar al servidor."""

    def __init__(self, bot):
        self.bot = bot
        # Caché local de invitaciones por servidor: {guild_id: {code: uses}}
        self.invites = {}

    # -------------------------------------------------------
    # Métodos auxiliares
    # -------------------------------------------------------

    async def get_all_invites(self, guild):
        """
        Obtiene todas las invitaciones activas de un servidor y sus contadores de uso.
        Requiere el permiso 'Manage Server' en el bot.
        """
        try:
            invites = await guild.invites()
            return {i.code: i.uses for i in invites}
        except Exception as e:
            print(f"[ERROR] Al obtener invites de {guild.name}: {e}")
            return {}

    # -------------------------------------------------------
    # Eventos
    # -------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        """Llena el caché inicial de invitaciones para todos los servidores al arrancar el bot."""
        for guild in self.bot.guilds:
            self.invites[guild.id] = await self.get_all_invites(guild)
        print("[INFO] Monitoreo de invitaciones activo y caché lleno.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Detecta qué invitación usó el miembro comparando el caché anterior con el estado actual.
        Registra la entrada en la base de datos si se identifica el enlace utilizado.
        """
        print(f"[INFO] {member.display_name} ha entrado a {member.guild.name}")

        # --- Comparación de caché para detectar el invite usado ---
        invites_after = await self.get_all_invites(member.guild)
        invites_before = self.invites.get(member.guild.id, {})
        used_invite_code = None

        for code, uses in invites_after.items():
            if code in invites_before:
                # El invite ya existía y su contador subió
                if uses > invites_before[code]:
                    used_invite_code = code
                    break
            elif uses > 0:
                # Invite nuevo creado después del on_ready con al menos un uso
                used_invite_code = code
                break

        # --- Resolución del objeto invitación completo ---
        used_invite = None
        if used_invite_code:
            all_invites_obj = await member.guild.invites()
            used_invite = next((i for i in all_invites_obj if i.code == used_invite_code), None)

        # --- Registro en base de datos ---
        if used_invite:
            print(f"[INFO] Invite detectado: {used_invite.code} | Creador: {used_invite.inviter}")
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
                    print(f"[ERROR] Al guardar join en DB: {e}")
        else:
            print("[WARN] No se pudo determinar qué invitación se usó (posible link de vanidad o error de caché).")

        # --- Actualización del caché para la próxima entrada ---
        self.invites[member.guild.id] = invites_after


async def setup(bot):
    await bot.add_cog(Invites(bot))
