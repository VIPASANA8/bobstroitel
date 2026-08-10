from itertools import combinations


RANK_VALUE = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}

CLASS_NAMES = {
    8: "стрит-флеш",
    7: "каре",
    6: "фулл-хаус",
    5: "флеш",
    4: "стрит",
    3: "тройка",
    2: "две пары",
    1: "пара",
    0: "старшая карта",
}

RANK_GROUP = {
    14: "тузы", 13: "короли", 12: "дамы", 11: "валеты",
    10: "десятки", 9: "девятки", 8: "восьмёрки", 7: "семёрки",
    6: "шестёрки", 5: "пятёрки", 4: "четвёрки", 3: "тройки", 2: "двойки",
}

RANK_SINGLE = {
    14: "туз", 13: "король", 12: "дама", 11: "валет",
    10: "10", 9: "9", 8: "8", 7: "7", 6: "6", 5: "5", 4: "4", 3: "3", 2: "2",
}

RANK_SHORT = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "10", 9: "9", 8: "8", 7: "7", 6: "6", 5: "5", 4: "4", 3: "3", 2: "2"}


def _straight_high(ranks: list[int]) -> int | None:
    unique = sorted(set(ranks), reverse=True)
    if 14 in unique:
        unique.append(1)

    run = 1
    for i in range(1, len(unique)):
        if unique[i - 1] - 1 == unique[i]:
            run += 1
            if run >= 5:
                return unique[i - 4]
        else:
            run = 1
    return None


def evaluate_five(cards: list[str]) -> tuple:
    ranks = [RANK_VALUE[c[0]] for c in cards]
    suits = [c[1] for c in cards]

    counts = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1

    groups = sorted(((count, rank) for rank, count in counts.items()), reverse=True)
    flush = len(set(suits)) == 1
    straight = _straight_high(ranks)

    if flush and straight:
        return (8, straight)

    if groups[0][0] == 4:
        quad = groups[0][1]
        kicker = max(r for r in ranks if r != quad)
        return (7, quad, kicker)

    trips = sorted((r for r, c in counts.items() if c == 3), reverse=True)
    pairs = sorted((r for r, c in counts.items() if c == 2), reverse=True)

    if trips and (len(trips) >= 2 or pairs):
        trip = trips[0]
        pair = trips[1] if len(trips) >= 2 else pairs[0]
        return (6, trip, pair)

    if flush:
        return (5, *sorted(ranks, reverse=True))

    if straight:
        return (4, straight)

    if trips:
        trip = trips[0]
        kickers = sorted((r for r in ranks if r != trip), reverse=True)[:2]
        return (3, trip, *kickers)

    if len(pairs) >= 2:
        high_pair, low_pair = pairs[:2]
        kicker = max(r for r in ranks if r not in (high_pair, low_pair))
        return (2, high_pair, low_pair, kicker)

    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((r for r in ranks if r != pair), reverse=True)[:3]
        return (1, pair, *kickers)

    return (0, *sorted(ranks, reverse=True))


class HandEvaluator:
    """Dependency-free 5/7-card evaluator. Bigger tuple = stronger hand."""

    def score(self, hole_cards: list[str], board: list[str]) -> tuple:
        cards = hole_cards + board
        if len(cards) < 5:
            raise ValueError("Нужно минимум пять общих и карманных карт")
        return max(evaluate_five(list(combo)) for combo in combinations(cards, 5))

    def class_name(self, hole_cards: list[str], board: list[str]) -> str:
        return CLASS_NAMES[self.score(hole_cards, board)[0]]

    def describe(self, hole_cards: list[str], board: list[str]) -> str:
        """Human-readable hand with the exact tie-break values."""
        score = self.score(hole_cards, board)
        category = score[0]

        if category == 8:
            return f"стрит-флеш до {RANK_SINGLE.get(score[1], score[1])}"
        if category == 7:
            return f"каре: {RANK_GROUP[score[1]]}, кикер {RANK_SINGLE[score[2]]}"
        if category == 6:
            return f"фулл-хаус: {RANK_GROUP[score[1]]} + {RANK_GROUP[score[2]]}"
        if category == 5:
            ranks = "-".join(RANK_SHORT[r] for r in score[1:])
            return f"флеш: {ranks}"
        if category == 4:
            return f"стрит до {RANK_SINGLE.get(score[1], score[1])}"
        if category == 3:
            return (
                f"тройка: {RANK_GROUP[score[1]]}, кикеры "
                f"{RANK_SINGLE[score[2]]} и {RANK_SINGLE[score[3]]}"
            )
        if category == 2:
            return (
                f"две пары: {RANK_GROUP[score[1]]} и {RANK_GROUP[score[2]]}, "
                f"кикер {RANK_SINGLE[score[3]]}"
            )
        if category == 1:
            kickers = ", ".join(RANK_SINGLE[r] for r in score[2:])
            return f"пара: {RANK_GROUP[score[1]]}, кикеры {kickers}"

        ranks = "-".join(RANK_SHORT[r] for r in score[1:])
        return f"старшая карта: {ranks}"

    def compare(self, hero_cards: list[str], bot_cards: list[str], board: list[str]) -> str:
        hero_score = self.score(hero_cards, board)
        bot_score = self.score(bot_cards, board)
        if hero_score > bot_score:
            return "hero"
        if bot_score > hero_score:
            return "bot"
        return "tie"
