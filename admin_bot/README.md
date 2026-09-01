# Poker8 CASH admin bot

The bot is a standalone standard-library Telegram adapter. It never connects to PostgreSQL, Tron, a wallet, or a private key. Every update first calls backend `/api/cash-admin/me`; buttons are only navigation and the backend remains the authority for role, active status, tenant scope, state transition, idempotency, and audit.

Configure the three variables shown in `.env.example`, then run from the repository root:

```powershell
python -m admin_bot.main
```

Outside localhost the API URL must use HTTPS and normal certificate verification. Commands: `/queue`, `/audit`, `/help`. Every mutation asks for a reason and a final confirmation. Unknown payouts require a verified external transaction reference before confirmation; the bot cannot request a blind resend.
