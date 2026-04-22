# Furibot

Multi-server Discord moderation bot built in Python with a modular cog architecture. Features progressive sanction escalation, cloud database persistence, customizable welcome/farewell messages, and invite tracking.

[🇲🇽 Versión en español](./README.md)

---

## Features

**Automated moderation**
- Progressive warning system: 3 warns → mute, 6 warns → kick, 9 warns → ban
- Independent commands: `/warn`, `/unwarn`, `/mute`, `/kick`, `/ban`
- Anti-escape: automatically reapplies mute if a sanctioned user leaves and rejoins
- Full infraction history per user via `/historial`

**Per-server configuration**
- Configurable moderation log channel via `/set_logs`
- Custom welcome and farewell messages via Discohook JSON (`/set_welcome`, `/set_leave`)
- Dynamic placeholder support: `{user}`, `{server}`, `{member_count}`, `{avatar}`, and more

**Invite tracking**
- Detects which invite link each member used when joining
- Logs entry data to the database including invite code and inviter info

**In development**
- AI module (Gemini API) for context-aware sanction decisions
- Automated news system per server

---

## Tech stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Framework | discord.py (commands + app_commands) |
| Database | PostgreSQL via Supabase |
| DB driver | asyncpg |
| Environment | python-dotenv |
| AI (upcoming) | Gemini API |

---

## Project structure

```
Furibot_1.0/
├── main.py                  # Entry point, cog loading and command sync
├── requirements.txt         # Project dependencies
├── .env                     # Environment variables (not included in repo)
├── .gitignore
└── cogs/
    ├── admin.py             # Moderation commands and server configuration
    ├── stats.py             # Data access layer (PostgreSQL/Supabase)
    ├── welcome.py           # Welcome messages
    ├── celebrations.py      # Farewell messages
    └── invites.py           # Invite tracking
```

---

## Installation

**1. Clone the repository**
```bash
git clone https://github.com/Javiz270/Furibot_1.0.git
cd Furibot_1.0
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure environment variables**

Create a `.env` file in the project root:
```env
DISCORD_TOKEN=your_discord_token
GUILD_ID=your_server_id           # Optional, for instant command sync
DB_HOST=your_supabase_host
DB_NAME=postgres
DB_USER=postgres
DB_PASS=your_password
DB_PORT=5432
```

**4. Run the bot**
```bash
python main.py
```

---

## Available commands

| Command | Required permission | Description |
|---|---|---|
| `/warn` | Moderate Members | Warn a user |
| `/unwarn` | Moderate Members | Pardon the most recent warn |
| `/mute` | Moderate Members | Temporarily mute a user |
| `/kick` | Kick Members | Kick a user from the server |
| `/ban` | Ban Members | Permanently ban a user |
| `/historial` | Administrator | View a user's infraction history |
| `/set_logs` | Administrator | Set the moderation log channel |
| `/set_welcome` | Administrator | Configure welcome message |
| `/set_leave` | Administrator | Configure farewell message |
| `/aviso` | Administrator | Post an official announcement |

---

## Database

The bot uses the following tables in Supabase:

- `infractions` — All sanctions log (warns, mutes, kicks, bans)
- `active_mutes` — Active mutes for anti-escape persistence
- `server_configs` — Per-server configuration (logs, welcome, farewell)
- `join_logs` — Entry log with invite code data

---

## Author

**Javier Santos** — [@Javiz270](https://github.com/Javiz270)

Built as a personal project to learn bot development, modular architecture, and cloud database integration.
