# ============================================================
# Furibot - Módulo: Welcome
# Descripción: Maneja los mensajes de bienvenida y salida de miembros.
#              Procesa payloads JSON de Discohook y aplica placeholders
#              dinámicos con datos del usuario y servidor.
# Autor: Javier Santos
# ============================================================

import json
import discord
from discord.ext import commands


# -------------------------------------------------------
# Funciones auxiliares de procesamiento de JSON
# -------------------------------------------------------

def _normalize_discohook_payload(payload):
    """
    Normaliza el payload de Discohook a su formato base (dict de contenido).
    Soporta el formato con wrapper 'messages[0].data' y el formato directo con 'data'.
    """
    if not isinstance(payload, dict):
        return payload
    if "messages" in payload and isinstance(payload["messages"], list) and payload["messages"]:
        first = payload["messages"][0]
        if isinstance(first, dict) and "data" in first and isinstance(first["data"], dict):
            return first["data"]
    if "data" in payload and isinstance(payload["data"], dict):
        return payload["data"]
    return payload


def _build_placeholders(guild: discord.Guild, member: discord.Member):
    """
    Construye el diccionario de placeholders disponibles para los mensajes de bienvenida/salida.
    Tokens soportados: {user}, {mention}, {username}, {server}, {member_count}, entre otros.
    """
    member_count = guild.member_count or 0

    avatar = (
        getattr(member, "display_avatar", None)
        or getattr(member, "avatar", None)
        or getattr(member, "default_avatar", None)
    )
    avatar_url = str(getattr(avatar, "url", ""))
    mention = getattr(member, "mention", str(member))
    display_name = getattr(member, "display_name", str(member))

    return {
        "{user}": mention,
        "{mention}": mention,
        "{username}": display_name,
        "{user_name}": display_name,
        "{user_tag}": str(member),
        "{server}": guild.name,
        "{guild}": guild.name,
        "{member_count}": str(member_count),
        "{user_id}": str(getattr(member, "id", "")),
        "{guild_id}": str(guild.id),
        "{user_avatar}": avatar_url,
        "{avatar}": avatar_url,
        "{avatar_url}": avatar_url,
    }


def _apply_placeholders(obj, placeholders):
    """
    Reemplaza recursivamente los placeholders en strings, listas y dicts.
    Permite aplicar los tokens de usuario/servidor a todo el payload JSON.
    """
    if isinstance(obj, str):
        for token, value in placeholders.items():
            obj = obj.replace(token, value)
        return obj
    if isinstance(obj, list):
        return [_apply_placeholders(v, placeholders) for v in obj]
    if isinstance(obj, dict):
        return {k: _apply_placeholders(v, placeholders) for k, v in obj.items()}
    return obj


# -------------------------------------------------------
# Cog principal
# -------------------------------------------------------

class Welcome(commands.Cog):
    """Cog de bienvenida. Envía mensajes personalizados cuando un miembro entra o sale del servidor."""

    def __init__(self, bot):
        self.bot = bot

    async def _send_from_config(self, guild: discord.Guild, member: discord.Member, config_data):
        """
        Parsea el JSON de configuración, aplica placeholders y envía el mensaje al canal configurado.
        Soporta formato legacy con wrapper 'discohook_json' y el formato actual de Discohook.
        """
        if not config_data:
            return

        # --- Parseo y normalización del payload JSON ---
        try:
            channel_id = int(config_data.get("channel_id") or 0)
            raw_json = config_data.get("json")

            if raw_json is None:
                print(f"[INFO] Bienvenida omitida en {guild.name}: welcome_json es NULL.")
                return

            if isinstance(raw_json, dict):
                payload = _normalize_discohook_payload(raw_json)
            elif isinstance(raw_json, str):
                if not raw_json.strip():
                    print(f"[INFO] Bienvenida omitida en {guild.name}: welcome_json vacío.")
                    return
                payload = json.loads(raw_json.strip())
                payload = _normalize_discohook_payload(payload)
            else:
                payload = json.loads(json.dumps(raw_json))
                payload = _normalize_discohook_payload(payload)

            # Compatibilidad con formato legacy que incluía channel_id/discohook_json
            if isinstance(payload, dict) and "discohook_json" in payload:
                if not channel_id:
                    channel_id = int(payload.get("channel_id", 0))
                inner = payload.get("discohook_json")
                if isinstance(inner, dict):
                    payload = _normalize_discohook_payload(inner)
                else:
                    payload = json.loads(inner or "{}")
                    payload = _normalize_discohook_payload(payload)

        except Exception as e:
            print(f"[ERROR] Parseando welcome_json en {guild.name}: {e}")
            return

        if not isinstance(payload, dict):
            print(f"[WARN] Bienvenida en {guild.name}: welcome_json no es un objeto JSON válido.")
            return

        if not channel_id:
            print(
                f"[INFO] Bienvenida omitida en {guild.name}: falta canal "
                "(welcome_channel_id, leave_channel_id y log_channel_id son NULL). Usa /set_welcome."
            )
            return

        # --- Resolución del canal de destino ---
        channel = guild.get_channel(channel_id) or self.bot.get_channel(channel_id)
        if channel is None:
            print(f"[WARN] Canal de bienvenida no encontrado ({channel_id}) en {guild.name}.")
            return

        # --- Aplicación de placeholders y construcción del mensaje ---
        payload = _apply_placeholders(payload, _build_placeholders(guild, member))
        content = payload.get("content")

        embeds = []
        for embed_data in payload.get("embeds") or []:
            if isinstance(embed_data, dict):
                embed_dict = dict(embed_data)
                ts = embed_dict.get("timestamp")
                if isinstance(ts, str) and ts.endswith("Z"):
                    embed_dict["timestamp"] = ts[:-1] + "+00:00"
                embeds.append(discord.Embed.from_dict(embed_dict))

        if not content and not embeds:
            print(f"[WARN] Bienvenida en {guild.name}: JSON sin content ni embeds; no se envía nada.")
            return

        # --- Envío del mensaje ---
        try:
            await channel.send(content=content, embeds=embeds if embeds else None)
        except Exception as e:
            print(f"[ERROR] Enviando bienvenida en {guild.name}: {e}")

    # -------------------------------------------------------
    # Eventos
    # -------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Dispara el mensaje de bienvenida cuando un miembro se une al servidor."""
        stats_cog = self.bot.get_cog("Stats")
        if not stats_cog:
            print(f"[WARN] Bienvenida omitida en {member.guild.name}: cog Stats no cargado.")
            return

        config_data = await stats_cog.get_welcome_config(member.guild.id)
        if not config_data:
            print(
                f"[INFO] Bienvenida omitida en {member.guild.name}: sin welcome_json en server_configs."
            )
            return

        await self._send_from_config(member.guild, member, config_data)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
