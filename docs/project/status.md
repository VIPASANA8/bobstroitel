# Project Status

Plan: `2026-08-14-online-network-mvp-roadmap.md`
Task: MVP polish
Step: testing
State: `in_progress`
Commit: `cc36d7686817a882da01d05752193d182f1c4636`
Note: Тестовый проход перед MVP. Закрыты: пуш состояния из координатора по WebSocket,
синхронизация таймера хода с серверным дедлайном, обработка отклонённых команд,
чат в реальном времени, живучесть стола при отказе движка, правило недобора ол-ина,
лимиты бай-ина из данных стола.
Evidence:
- `python -m pytest -q`: 190 passed, 3 skipped, 2 deselected.
- Живой прогон (uvicorn + sqlite, координатор включён): координатор пушит каждую
  ревизию (1–5 подряд, пропусков нет), чат доходит по сокету, отклонённая команда
  не ставит стол на паузу.

<!-- poker8-project-state {"active_plan":"2026-08-14-online-network-mvp-roadmap.md","active_step":"testing","active_task":"MVP polish","evidence":["python -m pytest -q: 190 passed, 3 skipped, 2 deselected.","Live run: coordinator pushes every revision over the socket, chat arrives live, a rejected command no longer pauses the table."],"last_confirmed_commit":"cc36d7686817a882da01d05752193d182f1c4636","note":"MVP polish pass","schema_version":1,"state":"in_progress","updated_at":"2026-08-17T00:00:00Z"} -->
