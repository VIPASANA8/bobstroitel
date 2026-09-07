# Poker/CUBE profile and cashier design

## Goal

Make the existing profile aware of the product it was opened from while keeping one shared wallet. Poker opens the Poker profile and CASH cashier; CUBE opens the CUBE profile and USDT cashier.

## Product context

The profile page has two contexts: `poker` and `cube`.

- Links from Poker open the page in Poker context.
- Links from CUBE open it in CUBE context.
- The header logo shows the active product and switches the whole page to the other context when pressed.
- The URL carries the context so reload, back navigation, and direct links preserve it.

No second profile page or duplicated wallet is introduced.

## Cashier

Both contexts reuse the existing CASH cashier structure and controls.

In Poker context:

- the logo is `poker♠`;
- the tabs are `CASH-касса` and `Профиль Poker`;
- CASH is the primary displayed amount and USDT is the secondary equivalent;
- the current profile palette remains unchanged.

In CUBE context:

- the logo is `cube⬢`;
- the tabs are `USDT-касса` and `Профиль CUBE`;
- USDT is the primary displayed amount and CASH is the secondary equivalent;
- the same cashier layout is recolored with the existing CUBE palette: black surfaces, lime accent, and CUBE borders/text colors.

Deposit and withdrawal actions remain the same because both products use the same underlying wallet and conversion rate.

## Profiles

The current Poker profile retains its existing identity, progression, missions, statistics, and achievements. Its history section is removed.

The CUBE profile is an intentionally empty state for now. It has no invented statistics, progression, or placeholder features beyond a concise statement that the profile has no content yet.

## Unified cashier history

History moves from the profile into the shared CASH/USDT cashier. It has four tabs:

- `Общее`: all Poker, CUBE, deposit, and withdrawal activity ordered newest first;
- `CUBE`: CUBE rounds only;
- `POKER`: Poker activity only;
- `Операции`: deposits and withdrawals only.

The history data is shared between contexts. In particular, `Операции` is identical in Poker and CUBE profiles. Context changes presentation and default denomination, not the underlying records.

Poker history includes both existing Poker hand history and Poker ledger activity. CUBE history is read from settled CUBE rounds. Deposit and withdrawal rows come from the cash journal. Internal ledger transfers that only support a game settlement are represented by their game row and are not duplicated as user-facing deposit/withdrawal operations.

Amounts are presented CASH-first in Poker context and USDT-first in CUBE context, with the shared conversion applied consistently.

## Data and implementation boundaries

- Extend the existing profile page rather than creating a parallel CUBE page.
- Reuse the current cashier markup and dialog handlers.
- Add the smallest server endpoint needed to return the unified, classified history feed.
- Do not change wallet accounting, conversion, deposit, withdrawal, Poker settlement, or CUBE settlement behavior.
- Do not create CUBE profile statistics before product requirements exist.

## Error and empty states

- If the wallet is unavailable, the cashier keeps its existing visible error behavior.
- Each history tab has its own relevant empty message.
- A failed history request must not hide a successfully loaded wallet or profile.
- Unsupported or missing context values fall back to Poker.

## Verification

Automated checks cover context selection, logo switching, labels, denomination order, shared operations history, history classification, removal of history from the Poker profile, and the empty CUBE profile. Browser checks cover Poker and CUBE contexts at desktop and phone widths using the existing cashier layout.
