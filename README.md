# Furibot

Bot de moderación multi-servidor para Discord, desarrollado en Python con arquitectura modular por cogs. Incluye sistema de sanciones progresivas, persistencia en base de datos, mensajes de bienvenida/despedida personalizados y rastreo de invitaciones.

[🇺🇸 English version](./README_EN.md)

---

## Características

**Moderación automática**
- Sistema de advertencias con escalada progresiva: 3 warns → mute, 6 warns → kick, 9 warns → ban
- Comandos independientes: `/warn`, `/unwarn`, `/mute`, `/kick`, `/ban`
- Anti-escape: reaplica el mute automáticamente si el usuario sale y vuelve al servidor
- Historial completo de infracciones por usuario con `/historial`

**Configuración por servidor**
- Canal de logs de moderación configurable con `/set_logs`
- Mensajes de bienvenida y despedida personalizados via JSON de Discohook (`/set_welcome`, `/set_leave`)
- Soporte de placeholders dinámicos: `{user}`, `{server}`, `{member_count}`, `{avatar}`, entre otros

**Rastreo de invitaciones**
- Detecta qué enlace de invitación usó cada miembro al unirse
- Registra la entrada en base de datos con código, creador del invite y datos del usuario

**En desarrollo**
- Módulo de IA (Gemini API) para análisis de contexto en sanciones
- Sistema de noticias automáticas por servidor

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.10+ |
| Framework | discord.py (commands + app_commands) |
| Base de datos | PostgreSQL via Supabase |
| Driver DB | asyncpg |
| Variables de entorno | python-dotenv |
| IA (próximo) | Gemini API |

---

## Estructura del proyecto

```
Furibot_1.0/
├── main.py                  # Entrada principal, carga de cogs y sincronización
├── requirements.txt         # Dependencias del proyecto
├── .env                     # Variables de entorno (no incluido en el repo)
├── .gitignore
└── cogs/
    ├── admin.py             # Comandos de moderación y configuración
    ├── stats.py             # Capa de acceso a datos (PostgreSQL/Supabase)
    ├── welcome.py           # Mensajes de bienvenida
    ├── celebrations.py      # Mensajes de despedida
    └── invites.py           # Rastreo de invitaciones
```

---

## Instalación

**1. Clona el repositorio**
```bash
git clone https://github.com/Javiz270/Furibot_1.0.git
cd Furibot_1.0
```

**2. Instala las dependencias**
```bash
pip install -r requirements.txt
```

**3. Configura las variables de entorno**

Crea un archivo `.env` en la raíz del proyecto:
```env
DISCORD_TOKEN=tu_token_de_discord
GUILD_ID=id_de_tu_servidor        # Opcional, para sync instantáneo
DB_HOST=tu_host_de_supabase
DB_NAME=postgres
DB_USER=postgres
DB_PASS=tu_contraseña
DB_PORT=5432
```

**4. Ejecuta el bot**
```bash
python main.py
```

---

## Comandos disponibles

| Comando | Permiso requerido | Descripción |
|---|---|---|
| `/warn` | Moderate Members | Amonesta a un usuario |
| `/unwarn` | Moderate Members | Perdona el warn más reciente |
| `/mute` | Moderate Members | Silencia temporalmente a un usuario |
| `/kick` | Kick Members | Expulsa a un usuario |
| `/ban` | Ban Members | Banea permanentemente a un usuario |
| `/historial` | Administrator | Muestra el expediente de un usuario |
| `/set_logs` | Administrator | Configura el canal de logs |
| `/set_welcome` | Administrator | Configura mensaje de bienvenida |
| `/set_leave` | Administrator | Configura mensaje de despedida |
| `/aviso` | Administrator | Publica un comunicado oficial |

---

## Base de datos

El bot utiliza las siguientes tablas en Supabase:

- `infractions` — Registro de todas las sanciones (warns, mutes, kicks, bans)
- `active_mutes` — Mutes activos para persistencia anti-escape
- `server_configs` — Configuración por servidor (logs, bienvenida, despedida)
- `join_logs` — Registro de entradas con código de invitación

---

## Autor

**Javier Santos** — [@Javiz270](https://github.com/Javiz270)

Proyecto personal en producción — arquitectura modular orientada a multi-servidor con persistencia en base de datos cloud
