import discord
from discord.ext import commands
import asyncpg
import os
import datetime
from dotenv import load_dotenv

load_dotenv()

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None

    async def create_pool(self):
        """Crea la conexión con Supabase"""
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
                print("🗄️ Conexión a PostgreSQL (Supabase) establecida con éxito.")
            except Exception as e:
                print(f"❌ Error al conectar a la DB: {e}")

    async def ensure_mute_tracking_table(self):
        """Crea la tabla para persistir mutes activos (anti-escape)."""
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

    # --- NUEVA FUNCIÓN UNIFICADA (INFRACCIONES) ---
    async def log_infraction(self, guild_id, guild_name, tipo, usuario_id, usuario_nombre, moderador_id, moderador_nombre, razon):
        """Registra Kicks, Bans, Mutes y Warns en la tabla 'infractions'"""
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
                guild_id,        # $1
                guild_name,      # $2
                tipo,            # $3 (Ej: 'KICK', 'WARN', etc)
                usuario_id,      # $4
                usuario_nombre,  # $5
                moderador_id,    # $6
                moderador_nombre,# $7
                razon,           # $8
                True             # $9 (activo por defecto)
            )
            print(f"⚖️ [{tipo}] Registrado en {guild_name} para {usuario_nombre}")

    # --- REGISTRO DE ENTRADAS (JOIN LOGS) ---
    async def log_member_join(self, usuario_id, usuario_nombre, invite_code, inviter_id, inviter_nombre):
        """Guarda quién entró y con qué link en la tabla join_logs (Tabla independiente)"""
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
            print(f"📥 Entrada registrada: {usuario_nombre} vía {invite_code}")



    async def save_config(self, guild_id, guild_name, log_channel_id):
        """Guarda o actualiza la configuración de logs por servidor."""
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
            print(f"⚙️ Config de logs actualizada en {guild_name}: {log_channel_id}")

    async def save_welcome_config(self, guild_id, guild_name, welcome_channel_id, welcome_json):
        """Guarda o actualiza la configuración de bienvenida por servidor."""
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
        """Guarda o actualiza la configuración de salida por servidor."""
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
        """Obtiene la configuración JSON de bienvenida del servidor."""
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
                # Mismo criterio que leave: si solo está el JSON en Supabase, usar otro canal conocido.
                if ch is None:
                    ch = leave_ch
                if ch is None:
                    ch = log_ch
                return {
                    "channel_id": ch,
                    "json": js
                }
            return None

    async def get_leave_config(self, guild_id):
        """Obtiene la configuración JSON de salida del servidor."""
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
                # Si en Supabase solo está leave_json pero no leave_channel_id, usar otro canal conocido.
                if ch is None:
                    ch = welcome_ch
                if ch is None:
                    ch = log_ch
                return {
                    "channel_id": ch,
                    "json": js
                }
            return None

    async def get_log_channel_id(self, guild_id):
        """Obtiene el channel_id de logs configurado para un servidor."""
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

    async def get_warn_count(self, guild_id, usuario_id):
        """Cuenta cuántos WARN activos tiene un usuario en un servidor."""
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
        """Desactiva todos los WARN activos de un usuario en un servidor."""
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
        """Desactiva el WARN activo más reciente de un usuario."""
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

    async def save_active_mute(self, guild_id, usuario_id, mute_until, reason):
        """Guarda o actualiza un mute activo para persistencia anti-escape."""
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
        """Devuelve segundos restantes de mute; limpia registro si ya expiró."""
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
        """Elimina un mute activo persistido."""
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

    # --- FUNCIÓN PARA OBTENER EL HISTORIAL DE INFRACCIONES DE UN USUARIO ---
    async def get_user_history(self, guild_id, usuario_id):
        """Obtiene todas las infracciones activas de un usuario en un server específico"""
        if self.pool is None:
            await self.create_pool()
            
        async with self.pool.acquire() as conn:
            # Filtramos por server, por usuario y que sigan activos
            rows = await conn.fetch(
                '''
                SELECT tipo_accion, razon, moderador_nombre, fecha 
                FROM infractions 
                WHERE guild_id = $1 AND usuario_id = $2 AND activo = TRUE
                ORDER BY fecha DESC
                ''',
                guild_id, usuario_id
            )
            return rows

async def setup(bot):
    cog = Stats(bot)
    await bot.add_cog(cog)
    await cog.create_pool()