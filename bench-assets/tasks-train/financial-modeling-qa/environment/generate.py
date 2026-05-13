"""
Deterministic generator for the dice-game TRAIN variant.

Produces:
  - /root/data.xlsx : 150 games * 2 turns = 300 rows, columns: Turn, Game, R1..R6
  - /root/background.pdf : scoring rules description
Also prints the expected answer for the train question.

Run locally to produce data.xlsx + background.pdf; copy outputs next to this file.
"""
import random
from pathlib import Path

import openpyxl
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

HERE = Path(__file__).parent

N_GAMES = 150
TURNS_PER_GAME = 2
N_DICE = 6
SEED = 20260414


def gen_rolls():
    rng = random.Random(SEED)
    rows = []
    turn = 1
    for gid in range(1, N_GAMES + 1):
        for _ in range(TURNS_PER_GAME):
            rolls = [rng.randint(1, 6) for _ in range(N_DICE)]
            rows.append([turn, gid] + rolls)
            turn += 1
    return rows


def write_xlsx(rows, path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rolls"
    ws.append(["Turn", "Game", "R1", "R2", "R3", "R4", "R5", "R6"])
    for r in rows:
        ws.append(r)
    wb.save(path)


RULES_TEXT = [
    ("Dice Scoring Game — Training Variant", "Heading1"),
    (
        "Each game consists of two turns. In every turn, a player rolls six "
        "six-sided dice (values 1..6). Each turn is then scored against six "
        "categories; the player keeps the score from exactly one category.",
        "BodyText",
    ),
    ("Categories (per turn)", "Heading2"),
    (
        "1. High-Often: the maximum value on the dice, multiplied by the number "
        "of dice showing that maximum value.",
        "BodyText",
    ),
    ("2. Summation: the plain sum of all six dice.", "BodyText"),
    (
        "3. Highs-and-Lows: the product of the maximum value, the minimum value, "
        "and (maximum - minimum).",
        "BodyText",
    ),
    (
        "4. Only-Two: a flat bonus of 30 points if the turn contains exactly two "
        "distinct values (any two), otherwise 0.",
        "BodyText",
    ),
    (
        "5. All-Numbers: a flat bonus of 40 points if the turn contains every "
        "value from 1 through 6 (one of each), otherwise 0.",
        "BodyText",
    ),
    (
        "6. Run-of-Four: a flat bonus of 50 points if four consecutive dice "
        "(in their given order) form a run of four strictly ascending or "
        "strictly descending consecutive integers, otherwise 0.",
        "BodyText",
    ),
    ("Game Score", "Heading2"),
    (
        "Within a single game, the two turns must use different categories. The "
        "game score is the maximum over all ordered pairs (i, j) with i != j of "
        "turn1.category[i] + turn2.category[j].",
        "BodyText",
    ),
    ("Data File", "Heading2"),
    (
        "The data file /root/data.xlsx has columns: Turn (monotonically "
        "increasing), Game (each id appears twice, once per turn), R1..R6 (the "
        "six dice rolls for that turn). There are 150 games in total.",
        "BodyText",
    ),
    ("Team Partition", "Heading2"),
    (
        "Team Red consists of games whose Game id is at most N/2 (i.e. games "
        "1..75). Team Blue consists of games whose Game id is strictly greater "
        "than N/2 (games 76..150). The k-th Red game is paired against the "
        "k-th Blue game (game 1 vs game 76, game 2 vs game 77, ...).",
        "BodyText",
    ),
]


def write_pdf(path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=LETTER)
    styles = getSampleStyleSheet()
    story = []
    for text, style_name in RULES_TEXT:
        story.append(Paragraph(text, styles[style_name]))
        story.append(Spacer(1, 6))
    doc.build(story)


# ---- scoring (mirrors validation rules) ----
def turn_scores(turn):
    mx = max(turn)
    mn = min(turn)
    high_often = mx * sum(1 for v in turn if v == mx)
    summation = sum(turn)
    highs_lows = mx * mn * (mx - mn)
    only_two = 30 if len(set(turn)) == 2 else 0
    all_numbers = 40 if set(turn) == {1, 2, 3, 4, 5, 6} else 0

    def is_run4(a):
        return (
            (a[0] + 1 == a[1] and a[1] + 1 == a[2] and a[2] + 1 == a[3])
            or (a[0] - 1 == a[1] and a[1] - 1 == a[2] and a[2] - 1 == a[3])
        )

    run4 = 50 if any(is_run4(turn[i:i + 4]) for i in range(3)) else 0
    return [high_often, summation, highs_lows, only_two, all_numbers, run4]


def best_game_score(s1, s2):
    best = 0
    for i in range(6):
        for j in range(6):
            if i == j:
                continue
            v = s1[i] + s2[j]
            if v > best:
                best = v
    return best


def compute_answer(rows):
    game_rolls = {}
    for row in rows:
        _turn, gid, *rolls = row
        game_rolls.setdefault(gid, []).append(rolls)
    game_scores = {}
    for gid, turns in game_rolls.items():
        assert len(turns) == 2, f"game {gid} has {len(turns)} turns"
        s1 = turn_scores(turns[0])
        s2 = turn_scores(turns[1])
        game_scores[gid] = best_game_score(s1, s2)

    half = N_GAMES // 2
    red = sorted([g for g in game_scores if g <= half])
    blue = sorted([g for g in game_scores if g > half])
    assert len(red) == len(blue), (len(red), len(blue))
    red_wins = blue_wins = 0
    for r, b in zip(red, blue):
        if game_scores[r] > game_scores[b]:
            red_wins += 1
        elif game_scores[b] > game_scores[r]:
            blue_wins += 1
    return red_wins - blue_wins, red_wins, blue_wins


def main():
    rows = gen_rolls()
    xlsx_path = HERE / "data.xlsx"
    pdf_path = HERE / "background.pdf"
    write_xlsx(rows, xlsx_path)
    write_pdf(pdf_path)
    ans, rw, bw = compute_answer(rows)
    print(f"rows={len(rows)} games={N_GAMES} seed={SEED}")
    print(f"red_wins={rw} blue_wins={bw} answer={ans}")
    print(f"wrote {xlsx_path}")
    print(f"wrote {pdf_path}")


if __name__ == "__main__":
    main()
