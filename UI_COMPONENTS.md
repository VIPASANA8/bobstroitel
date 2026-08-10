# Poker Trainer v0.13 — карта компонентов

Главный слой компоновки: `static/component-ui.css`.

Компоненты: `MobileHeader`, `PokerTable`, `PlayerSeat`, `HeroSeat`, `Pot`, `Board`, `TurnTimer`, `SelectedAction`, `MainActions`, `BetPresets`, `BetControl`, `AutoActionBar`.

Координаты меняются в начале `component-ui.css`: `--seat-0-x/y` … `--seat-6-x/y`, `--pot-y`, `--pot-chips-y`, `--board-y`, `--hud-y`, `--hud-edge`.

`component-ui.js` поворачивает физические места так, чтобы локальный игрок всегда был `data-visual-seat="0"` и находился снизу.

## v0.13

- исправлен flow `header → table → controls`;
- убран старый `min-height:100dvh`, из-за которого нижние кнопки уезжали вниз;
- нижний UI всегда видим: действия → пресеты → сумма → слайдер → авто-действие;
- packaged SQLite заполнен как 7-max: 1 человек + 6 ботов, чтобы сразу видеть полную компоновку;
- игровая механика/API не переписаны.
