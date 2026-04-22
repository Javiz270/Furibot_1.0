# ============================================================
# Furibot - Módulo: Stats
# Descripción: Capa de acceso a datos (PostgreSQL/Supabase).
#              Gestiona infracciones, configuraciones de servidor,
#              mutes activos, historial de usuarios y logs de entrada.
# Autor: Javier Santos
# ============================================================

import discord
from discord.ext import commands
import asyncpg
import os
import datetime
from dotenv import load_dotenv

load_dotenv()


class Stats(commands.Cog):
    """Cog de base de datos. Centraliza todas las operaciones con PostgreSQL (Supabase)."""

    def __init__(self, bot):
        self.bot = bot
        self.pool = None

    # -------------------------------------------------------
    # Conexión y configuración inicial
    # -------------------------------------------------------

    async def create_pool(self):
        """Crea el pool de conexiones con la base de datos de Supabase."""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    host=os.getenv('DB_HOST'),
                    database=os.getenv('DB_NAME'),
                    user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASS'),
                    port=os.getenv('DB_PORT')
                )
                await self.ensure_mute_tracking_table()
                print("[INFO] Conexión a PostgreSQL (Supabase) establecida.")
            except Exception as e:
                print(f"[ERROR] Al conectar a la DB: {e}")

    async def ensure_mute_tracking_table(self):
        """Crea la tabla active_mutes si no existe (persistencia anti-escape)."""
        if self.pool is None:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS active_mutes (
                    guild_id BIGINT NOT NULL,
                    usuario_id BIGINT NOT NULL,
                    mute_until TIMESTAMPTZ NOT NULL,
                    reason TEXT,
                    PRIMARY KEY (guild_id, usuario_id)
                )
                '''
            )

    # -------------------------------------------------------
    # Infracciones
    # -------------------------------------------------------

    async def log_infraction(self, guild_id, guild_name, tipo, usuario_id, usuario_nombre, moderador_id, moderador_nombre, razon):
        """
        Registra una infracción en la tabla 'infractions'.
        Tipos válidos: 'KICK', 'BAN', 'MUTE', 'WARN', 'UNWARN', 'MUTE POR WARNS', etc.
        """
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO infractions (
                    guild_id, guild_name, tipo_accion, usuario_id,
                    usuario_nombre, moderador_id, moderador_nombre, razon, activo
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ''',
                guild_id,
                guild_name,
                tipo,
                usuario_id,
                usuario_nombre,
                moderador_id,
                moderador_nombre,
                razon,
                True
            )
            print(f"[INFO] [{tipo}] Registrado en {guild_name} para {usuario_nombre}")

    async def get_warn_count(self, guild_id, usuario_id):
        """Retorna el número de warns activos de un usuario en un servidor."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                '''
                SELECT COUNT(*)
                FROM infractions
                WHERE guild_id = $1
                  AND usuario_id = $2
                  AND tipo_accion = 'WARN'
                  AND activo = TRUE
                ''',
                guild_id, usuario_id
            )
            return count

    async def reset_warns(self, guild_id, usuario_id):
        """Desactiva todos los warns activos de un usuario en un servidor."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            result = await conn.execute(
                '''
                UPDATE infractions
                SET activo = FALSE
                WHERE guild_id = $1
                  AND usuario_id = $2
                  AND tipo_accion = 'WARN'
                  AND activo = TRUE
                ''',
                guild_id, usuario_id
            )
            return result

    async def pardon_latest_warn(self, guild_id, usuario_id):
        """
        Desactiva el warn activo más reciente de un usuario.
        Retorna True si se actualizó algún registro, False si no había warns activos.
        """
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            result = await conn.execute(
                '''
                UPDATE infractions
                SET activo = FALSE
                WHERE ctid IN (
                    SELECT ctid
                    FROM infractions
                    WHERE guild_id = $1
                      AND usuario_id = $2
                      AND tipo_accion = 'WARN'
                      AND activo = TRUE
                    ORDER BY fecha DESC
                    LIMIT 1
                )
                ''',
                guild_id, usuario_id
            )
            return result.endswith("1")

    async def get_user_history(self, guild_id, usuario_id):
        """Retorna todas las infracciones activas de un usuario en un servidor, ordenadas por fecha."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                '''
                SELECT tipo_accion, razon, moderador_nombre, fecha
                FROM infractions
                WHERE guild_id = $1
                  AND usuario_id = $2
                  AND activo = TRUE
                ORDER BY fecha DESC
                ''',
                guild_id, usuario_id
            )
            return rows

    # -------------------------------------------------------
    # Mutes activos (persistencia anti-escape)
    # -------------------------------------------------------

    async def save_active_mute(self, guild_id, usuario_id, mute_until, reason):
        """Guarda o actualiza un mute activo para que persista si el usuario abandona el servidor."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO active_mutes (guild_id, usuario_id, mute_until, reason)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id, usuario_id)
                DO UPDATE SET
                    mute_until = EXCLUDED.mute_until,
                    reason = EXCLUDED.reason
                ''',
                guild_id, usuario_id, mute_until, reason
            )

    async def get_remaining_mute_seconds(self, guild_id, usuario_id):
        """
        Retorna los segundos restantes de mute para un usuario.
        Si el mute ya expiró, elimina el registro y retorna 0.
        """
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                '''
                SELECT mute_until
                FROM active_mutes
                WHERE guild_id = $1
                  AND usuario_id = $2
                ''',
                guild_id, usuario_id
            )
            if not row:
                return 0

            mute_until = row["mute_until"]
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            remaining = int((mute_until - now_utc).total_seconds())

            if remaining <= 0:
                await conn.execute(
                    '''
                    DELETE FROM active_mutes
                    WHERE guild_id = $1
                      AND usuario_id = $2
                    ''',
                    guild_id, usuario_id
                )
                return 0

            return remaining

    async def clear_active_mute(self, guild_id, usuario_id):
        """Elimina el registro de mute activo de un usuario."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                DELETE FROM active_mutes
                WHERE guild_id = $1
                  AND usuario_id = $2
                ''',
                guild_id, usuario_id
            )

    # -------------------------------------------------------
    # Configuración de servidores
    # -------------------------------------------------------

    async def save_config(self, guild_id, guild_name, log_channel_id):
        """Guarda o actualiza el canal de logs configurado para un servidor."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO server_configs (guild_id, guild_name, log_channel_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id)
                DO UPDATE SET
                    guild_name = EXCLUDED.guild_name,
                    log_channel_id = EXCLUDED.log_channel_id
                ''',
                guild_id, guild_name, log_channel_id
            )
            print(f"[INFO] Canal de logs actualizado en {guild_name}: {log_channel_id}")

    async def save_welcome_config(self, guild_id, guild_name, welcome_channel_id, welcome_json):
        """Guarda o actualiza la configuración del mensaje de bienvenida."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO server_configs (guild_id, guild_name, welcome_channel_id, welcome_json)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id)
                DO UPDATE SET
                    guild_name = EXCLUDED.guild_name,
                    welcome_channel_id = EXCLUDED.welcome_channel_id,
                    welcome_json = EXCLUDED.welcome_json
                ''',
                guild_id, guild_name, welcome_channel_id, welcome_json
            )

    async def save_leave_config(self, guild_id, guild_name, leave_channel_id, leave_json):
        """Guarda o actualiza la configuración del mensaje de salida."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO server_configs (guild_id, guild_name, leave_channel_id, leave_json)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id)
                DO UPDATE SET
                    guild_name = EXCLUDED.guild_name,
                    leave_channel_id = EXCLUDED.leave_channel_id,
                    leave_json = EXCLUDED.leave_json
                ''',
                guild_id, guild_name, leave_channel_id, leave_json
            )

    async def get_welcome_config(self, guild_id):
        """
        Retorna la configuración de bienvenida del servidor.
        Si no hay canal configurado, intenta usar el canal de salida o de logs como fallback.
        """
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                '''
                SELECT welcome_channel_id, welcome_json, leave_channel_id, log_channel_id
                FROM server_configs
                WHERE guild_id = $1
                ''',
                guild_id
            )
            if row:
                ch = row["welcome_channel_id"]
                js = row["welcome_json"]
                leave_ch = row["leave_channel_id"]
                log_ch = row["log_channel_id"]

                js_empty = js is None or (isinstance(js, str) and not js.strip())
                if js_empty:
                    return None

                # Fallback de canal si welcome_channel_id no está configurado
                if ch is None:
                    ch = leave_ch
                if ch is None:
                    ch = log_ch

                return {"channel_id": ch, "json": js}
            return None

    async def get_leave_config(self, guild_id):
        """
        Retorna la configuración de salida del servidor.
        Si no hay canal configurado, intenta usar el canal de bienvenida o de logs como fallback.
        """
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                '''
                SELECT leave_channel_id, leave_json, welcome_channel_id, log_channel_id
                FROM server_configs
                WHERE guild_id = $1
                ''',
                guild_id
            )
            if row:
                ch = row["leave_channel_id"]
                js = row["leave_json"]
                welcome_ch = row["welcome_channel_id"]
                log_ch = row["log_channel_id"]

                js_empty = js is None or (isinstance(js, str) and not js.strip())
                if js_empty:
                    return None

                # Fallback de canal si leave_channel_id no está configurado
                if ch is None:
                    ch = welcome_ch
                if ch is None:
                    ch = log_ch

                return {"channel_id": ch, "json": js}
            return None

    async def get_log_channel_id(self, guild_id):
        """Retorna el ID del canal de logs configurado para un servidor."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                '''
                SELECT log_channel_id
                FROM server_configs
                WHERE guild_id = $1
                ''',
                guild_id
            )
            if row:
                return row["log_channel_id"]
            return None

    # -------------------------------------------------------
    # Logs de entradas (join logs)
    # -------------------------------------------------------

    async def log_member_join(self, usuario_id, usuario_nombre, invite_code, inviter_id, inviter_nombre):
        """Registra quién entró al servidor y mediante qué enlace de invitación."""
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO join_logs (usuario_id, usuario_nombre, invitacion_codigo, invitador_id, invitador_nombre)
                VALUES ($1, $2, $3, $4, $5)
                ''',
                usuario_id, usuario_nombre, invite_code, inviter_id, inviter_nombre
            )
            print(f"[INFO] Entrada registrada: {usuario_nombre} via {invite_code}")


async def setup(bot):
    cog = Stats(bot)
    await bot.add_cog(cog)
    await cog.create_pool()
