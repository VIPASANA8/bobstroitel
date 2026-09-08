# Poker8 CASH admin bot

The bot is a standalone standard-library Telegram adapter. It never connects to PostgreSQL, Tron, a wallet, or a private key. Every update first calls backend `/api/cash-admin/me`; buttons are only navigation and the backend remains the authority for role, active status, tenant scope, state transition, idempotency, and audit.

Configure the three variables shown in `.env.example`, then run from the repository root:

```powershell
python -m admin_bot.main
```

Outside localhost the API URL must use HTTPS and normal certificate verification.

Read-only reporting commands:

- `/economy` — owner CUBE side, partner earnings/share and all-time referral payout totals;
- `/referrals` — referral payout states, Poker/CUBE split for recent settlements and largest groups;
- `/partner` — partner share, posted CUBE periods and the latest settlement breakdown;
- `/audit` — recent operator actions;
- `/user ID` — user balances and operations;
- `/order ID` — RUB P2P order;
- `/recon [YYYY-MM-DD]` — daily RUB reconciliation.

Operational command: `/queue` shows decisions requiring operator action. Every mutation asks for a reason and a final confirmation. Unknown payouts require a verified external transaction reference before confirmation; the bot cannot request a blind resend.
