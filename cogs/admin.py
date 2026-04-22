# ============================================================
# Furibot - Módulo: Admin
# Descripción: Comandos de moderación y configuración de servidor.
#              Incluye warn, mute, kick, ban, unwarn, historial,
#              avisos y configuración de canales de logs/bienvenida.
# Autor: Javier Santos
# ============================================================

import discord
from discord import app_commands
from discord.ext import commands
import datetime
import asyncio


class Admin(commands.Cog):
    """Cog de moderación. Maneja warns, mutes, kicks, bans y configuración de servidor."""

    def __init__(self, bot):
        self.bot = bot
        # Evita tareas duplicadas si se programa un nuevo mute antes de que acabe el anterior
        self._mute_end_tasks = {}

    # -------------------------------------------------------
    # Métodos auxiliares internos
    # -------------------------------------------------------

    def _cancel_mute_end_task(self, guild_id, user_id):
        """Cancela la tarea programada de fin de mute para un usuario, si existe."""
        key = (guild_id, user_id)
        task = self._mute_end_tasks.pop(key, None)
        if task and not task.done():
            task.cancel()

    def _schedule_mute_end_dm(self, user_id, guild_id, guild_name, segundos, reset_warns=False):
        """
        Programa una tarea asíncrona que, tras `segundos`, limpia el mute en la base de datos
        y envía un DM al usuario notificando que su silencio ha terminado.
        Si reset_warns=True, también reinicia las advertencias del usuario.
        """
        self._cancel_mute_end_task(guild_id, user_id)

        async def _run():
            try:
                await asyncio.sleep(segundos)

                # --- Limpieza en base de datos ---
                stats_cog = self.bot.get_cog('Stats')
                if stats_cog:
                    try:
                        if reset_warns:
                            await stats_cog.reset_warns(guild_id, user_id)
                        await stats_cog.clear_active_mute(guild_id, user_id)
                    except Exception as e:
                        print(f"[ERROR] Al finalizar mute en DB: {e}")

                # --- Notificación al usuario por DM ---
                try:
                    user = await self.bot.fetch_user(user_id)
                    if reset_warns:
                        msg = (
                            f"🛡️ Aviso de Furibot: Tu tiempo de silencio en {guild_name} ha finalizado. "
                            "Tus advertencias han sido reiniciadas. ¡Pórtate bien!"
                        )
                    else:
                        msg = (
                            f"🛡️ Aviso de Furibot: Tu tiempo de silencio en {guild_name} ha finalizado. "
                            "Ya puedes volver a participar con normalidad."
                        )
                    await user.send(msg)
                except Exception:
                    pass

            except asyncio.CancelledError:
                raise
            finally:
                self._mute_end_tasks.pop((guild_id, user_id), None)

        task = asyncio.create_task(_run())
        self._mute_end_tasks[(guild_id, user_id)] = task

    async def registrar_en_db(self, interaction, tipo, usuario, razon):
        """
        Registra una infracción en la tabla 'infractions' a través del cog Stats
        y envía un embed de moderación al canal de logs configurado en el servidor.
        """
        if interaction.guild is None:
            return

        stats_cog = self.bot.get_cog('Stats')
        if not stats_cog:
            print("[WARN] Stats cog no disponible; no se pudo registrar la infracción.")
            return

        # --- Registro en base de datos ---
        await stats_cog.log_infraction(
            guild_id=interaction.guild.id,
            guild_name=interaction.guild.name,
            tipo=tipo,
            usuario_id=usuario.id,
            usuario_nombre=usuario.display_name,
            moderador_id=interaction.user.id,
            moderador_nombre=interaction.user.display_name,
            razon=razon
        )

        # --- Envío de embed al canal de logs ---
        log_channel_id = await stats_cog.get_log_channel_id(interaction.guild.id)
        if not log_channel_id:
            return

        log_channel = interaction.guild.get_channel(log_channel_id) or self.bot.get_channel(log_channel_id)
        if log_channel is None:
            print(f"[WARN] Canal de logs no encontrado: {log_channel_id}")
            return

        embed = discord.Embed(
            title=f"🛡️ Registro de moderación: {tipo}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Usuario", value=f"{usuario.mention} (`{usuario.id}`)", inline=False)
        embed.add_field(name="Moderador", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Razón", value=razon, inline=False)
        embed.add_field(name="Servidor", value=interaction.guild.name, inline=False)

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"[ERROR] No se pudo enviar embed de logs: {e}")

    # -------------------------------------------------------
    # Comandos de configuración
    # -------------------------------------------------------

    @app_commands.command(name="set_logs", description="Configura el canal donde se enviarán los reportes")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_logs(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Establece el canal de logs de moderación para el servidor."""
        if interaction.guild is None:
            await interaction.response.send_message("❌ Este comando solo se puede usar dentro de un servidor.", ephemeral=True)
            return

        stats_cog = self.bot.get_cog('Stats')
        if not stats_cog:
            await interaction.response.send_message("❌ No se encontró el módulo de estadísticas. Intenta de nuevo más tarde.", ephemeral=True)
            return

        try:
            await stats_cog.save_config(interaction.guild.id, interaction.guild.name, canal.id)
            await interaction.response.send_message(f"✅ Canal de logs configurado en: {canal.mention}", ephemeral=True)
        except Exception as e:
            print(f"[ERROR] Al guardar configuración de logs: {e}")
            await interaction.response.send_message("❌ No se pudo guardar la configuración de logs.", ephemeral=True)

    @app_commands.command(name="set_welcome", description="Configura canal y JSON de bienvenida (Discohook)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_welcome(self, interaction: discord.Interaction, canal: discord.TextChannel, welcome_json: str):
        """Guarda la configuración del mensaje de bienvenida para el servidor."""
        if interaction.guild is None:
            await interaction.response.send_message("❌ Este comando solo se puede usar dentro de un servidor.", ephemeral=True)
            return

        stats_cog = self.bot.get_cog('Stats')
        if not stats_cog:
            await interaction.response.send_message("❌ No se encontró el módulo de estadísticas.", ephemeral=True)
            return

        try:
            await stats_cog.save_welcome_config(
                interaction.guild.id,
                interaction.guild.name,
                canal.id,
                welcome_json
            )
            await interaction.response.send_message(
                f"✅ Configuración de bienvenida guardada para {canal.mention}.",
                ephemeral=True
            )
        except Exception as e:
            print(f"[ERROR] Al guardar configuración de bienvenida: {e}")
            await interaction.response.send_message("❌ No se pudo guardar la configuración de bienvenida.", ephemeral=True)

    @app_commands.command(name="set_leave", description="Configura canal y JSON de salida (Discohook)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_leave(self, interaction: discord.Interaction, canal: discord.TextChannel, leave_json: str):
        """Guarda la configuración del mensaje de salida para el servidor."""
        if interaction.guild is None:
            await interaction.response.send_message("❌ Este comando solo se puede usar dentro de un servidor.", ephemeral=True)
            return

        stats_cog = self.bot.get_cog('Stats')
        if not stats_cog:
            await interaction.response.send_message("❌ No se encontró el módulo de estadísticas.", ephemeral=True)
            return

        try:
            await stats_cog.save_leave_config(
                interaction.guild.id,
                interaction.guild.name,
                canal.id,
                leave_json
            )
            await interaction.response.send_message(
                f"✅ Configuración de salida guardada para {canal.mention}.",
                ephemeral=True
            )
        except Exception as e:
            print(f"[ERROR] Al guardar configuración de salida: {e}")
            await interaction.response.send_message("❌ No se pudo guardar la configuración de salida.", ephemeral=True)

    # -------------------------------------------------------
    # Comandos de consulta
    # -------------------------------------------------------

    @app_commands.command(name="historial", description="Muestra el expediente de un usuario")
    @app_commands.checks.has_permissions(administrator=True)
    async def historial(self, interaction: discord.Interaction, usuario: discord.Member):
        """Muestra todas las infracciones registradas de un usuario en el servidor."""
        if interaction.guild is None:
            await interaction.response.send_message("❌ Este comando solo se puede usar dentro de un servidor.", ephemeral=True)
            return

        await interaction.response.defer()
        stats_cog = self.bot.get_cog('Stats')

        if not stats_cog:
            await interaction.followup.send("❌ No se encontró el módulo de estadísticas.")
            return

        historial = await stats_cog.get_user_history(interaction.guild.id, usuario.id)

        if not historial:
            await interaction.followup.send(f"✅ **{usuario.display_name}** tiene un expediente limpio.")
            return

        embed = discord.Embed(
            title=f"📋 Expediente de {usuario.display_name}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now()
        )

        for reg in historial:
            fecha_str = reg['fecha'].strftime("%d/%m/%Y")
            embed.add_field(
                name=f"{reg['tipo_accion']} - {fecha_str}",
                value=f"**Razón:** {reg['razon']}\n**Mod:** {reg['moderador_nombre']}",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="aviso", description="Envía un anuncio oficial en un embed")
    @app_commands.checks.has_permissions(administrator=True)
    async def aviso(self, interaction: discord.Interaction, canal: discord.TextChannel, mensaje: str):
        """Publica un comunicado oficial en el canal especificado."""
        embed = discord.Embed(
            title="📢 COMUNICADO OFICIAL",
            description=mensaje,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.set_footer(text=f"Emitido por {interaction.user.display_name}")
        await canal.send(embed=embed)
        await interaction.response.send_message("✅ Aviso enviado con éxito.", ephemeral=True)

    # -------------------------------------------------------
    # Comandos de moderación
    # -------------------------------------------------------

    @app_commands.command(name="kick", description="Expulsa a un usuario")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
        """Expulsa a un usuario del servidor y registra la acción."""
        await interaction.response.defer(ephemeral=True)
        await usuario.kick(reason=razon)
        await self.registrar_en_db(interaction, "KICK", usuario, razon)
        await interaction.followup.send(f"👢 **{usuario.display_name}** expulsado. Datos guardados.")

    @app_commands.command(name="ban", description="Banea permanentemente a un usuario")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
        """Banea permanentemente a un usuario del servidor y registra la acción."""
        await interaction.response.defer(ephemeral=True)
        await usuario.ban(reason=razon)
        await self.registrar_en_db(interaction, "BAN", usuario, razon)
        await interaction.followup.send(f"🚫 **{usuario.display_name}** baneado. Registro guardado.")

    @app_commands.command(name="mute", description="Silencia a un usuario temporalmente")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, usuario: discord.Member, minutos: int = 10, razon: str = "No especificada"):
        """Aplica timeout a un usuario por el tiempo especificado y programa notificación de fin."""
        await interaction.response.defer(ephemeral=True)
        tiempo = datetime.timedelta(minutes=minutos)
        await usuario.timeout(tiempo, reason=razon)

        stats_cog = self.bot.get_cog('Stats')
        if stats_cog and interaction.guild is not None:
            mute_until = datetime.datetime.now(datetime.timezone.utc) + tiempo
            await stats_cog.save_active_mute(interaction.guild.id, usuario.id, mute_until, razon)
            self._schedule_mute_end_dm(
                usuario.id,
                interaction.guild.id,
                interaction.guild.name,
                max(1, minutos) * 60,
                reset_warns=False,
            )

        await self.registrar_en_db(interaction, "MUTE", usuario, f"({minutos} min) {razon}")
        await interaction.followup.send(f"🔇 **{usuario.display_name}** silenciado por {minutos} minutos.")

    @app_commands.command(name="warn", description="Amonesta a un usuario")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, usuario: discord.Member, razon: str):
        """
        Registra una advertencia al usuario. Aplica sanciones automáticas
        según el acumulado: 3 warns = mute, 6 warns = kick, 9 warns = ban.
        """
        await interaction.response.defer(ephemeral=True)
        await self.registrar_en_db(interaction, "WARN", usuario, razon)

        stats_cog = self.bot.get_cog('Stats')
        if stats_cog and interaction.guild is not None:
            warn_count = await stats_cog.get_warn_count(interaction.guild.id, usuario.id)

            # --- Sanciones automáticas por acumulación de warns ---
            if warn_count in (3, 6, 9):
                try:
                    if warn_count == 3:
                        tiempo = datetime.timedelta(minutes=10)
                        await usuario.timeout(tiempo, reason="MUTE POR WARNS")
                        mute_until = datetime.datetime.now(datetime.timezone.utc) + tiempo
                        await stats_cog.save_active_mute(
                            interaction.guild.id, usuario.id, mute_until, "MUTE POR WARNS"
                        )
                        self._schedule_mute_end_dm(
                            usuario.id, interaction.guild.id, interaction.guild.name,
                            600, reset_warns=True,
                        )
                        await self.registrar_en_db(
                            interaction, "MUTE POR WARNS", usuario,
                            "Sanción automática por acumulación de 3 advertencias."
                        )
                        if interaction.channel:
                            await interaction.channel.send(
                                "⚖️ El sistema ha aplicado un mute automático por acumulación de 3 advertencias."
                            )

                    elif warn_count == 6:
                        self._cancel_mute_end_task(interaction.guild.id, usuario.id)
                        await stats_cog.clear_active_mute(interaction.guild.id, usuario.id)
                        await usuario.kick(reason="KICK POR WARNS")
                        await self.registrar_en_db(
                            interaction, "KICK POR WARNS", usuario,
                            "Sanción automática por acumulación de 6 advertencias."
                        )
                        if interaction.channel:
                            await interaction.channel.send(
                                "⚖️ El sistema ha aplicado un kick automático por acumulación de 6 advertencias."
                            )

                    elif warn_count == 9:
                        self._cancel_mute_end_task(interaction.guild.id, usuario.id)
                        await stats_cog.clear_active_mute(interaction.guild.id, usuario.id)
                        await usuario.ban(reason="BAN POR WARNS")
                        await self.registrar_en_db(
                            interaction, "BAN POR WARNS", usuario,
                            "Sanción automática por acumulación de 9 advertencias."
                        )
                        if interaction.channel:
                            await interaction.channel.send(
                                "⚖️ El sistema ha aplicado un ban automático por acumulación de 9 advertencias."
                            )

                except Exception as e:
                    print(f"[ERROR] Al aplicar sanción automática por warns: {e}")

        await interaction.followup.send(f"⚠️ **{usuario.display_name}** ha sido amonestado. Razón: {razon}")

    @app_commands.command(name="unwarn", description="Perdona manualmente un warn activo de un usuario")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unwarn(self, interaction: discord.Interaction, usuario: discord.Member):
        """Desactiva el warn más reciente activo de un usuario y registra el perdón."""
        if interaction.guild is None:
            await interaction.response.send_message("❌ Este comando solo se puede usar dentro de un servidor.", ephemeral=True)
            return

        stats_cog = self.bot.get_cog('Stats')
        if not stats_cog:
            await interaction.response.send_message("❌ No se encontró el módulo de estadísticas.", ephemeral=True)
            return

        updated = await stats_cog.pardon_latest_warn(interaction.guild.id, usuario.id)
        if not updated:
            await interaction.response.send_message(
                f"ℹ️ **{usuario.display_name}** no tiene warns activos para perdonar.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Se perdonó un warn activo de **{usuario.display_name}**.",
            ephemeral=True
        )
        await self.registrar_en_db(
            interaction, "UNWARN", usuario,
            "Se desactivó manualmente un warn activo."
        )

    # -------------------------------------------------------
    # Eventos
    # -------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Al reincorporarse un usuario, reaplica el mute si tenía uno activo.
        Previene la evasión de sanciones saliendo y volviendo al servidor.
        """
        stats_cog = self.bot.get_cog('Stats')
        if not stats_cog:
            return

        try:
            remaining_seconds = await stats_cog.get_remaining_mute_seconds(member.guild.id, member.id)
            if remaining_seconds <= 0:
                return

            await member.timeout(
                datetime.timedelta(seconds=remaining_seconds),
                reason="Reaplicación automática de mute activo (anti-escape)"
            )
            print(
                f"[INFO] Mute reaplicado a {member.display_name} en {member.guild.name} "
                f"por {remaining_seconds} segundos restantes."
            )
        except Exception as e:
            print(f"[ERROR] Al reaplicar mute anti-escape: {e}")

    # -------------------------------------------------------
    # Manejo de errores
    # -------------------------------------------------------

    @set_logs.error
    @set_welcome.error
    @set_leave.error
    @aviso.error
    @kick.error
    @ban.error
    @mute.error
    @warn.error
    @unwarn.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Maneja errores de permisos insuficientes en todos los comandos del cog."""
        if isinstance(error, app_commands.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send("❌ No tienes permisos suficientes.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ No tienes permisos suficientes.", ephemeral=True)
        else:
            print(f"[ERROR] En comando de Admin: {error}")


async def setup(bot):
    await bot.add_cog(Admin(bot))
