#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["chess>=1.11", "reportlab>=4.2"]
# ///
"""Self-check for pgn2book. Run: uv run test_pgn2book.py"""
import pgn2book as book

EXAMPLE = "example.pgn"


def test_study():
    book.register_fonts()
    games = list(book.games(EXAMPLE))
    assert len(games) == 5, len(games)
    assert games[0].headers["ChapterName"] == "The Gambit Accepted (3... exf4)"

    printed = [book.lines(game) for game in games]
    assert [len(lines) for lines in printed] == [4, 3, 9, 5, 10]
    assert sum(map(len, printed)) == 31, "one diagram per printed line"

    mainline, *sides = printed[0]
    assert [line[0].ply() for line in printed[0]] == [1, 12, 10, 8], "mainline, then deepest first"
    assert [line[0].san() for line in printed[0]] == ["e4", "Nc6", "Nc6", "Qe7"]
    assert mainline[-1].san() == "Bxe5"

    assert [book.label(n, first) for n, first in zip(mainline[:2], (True, False))] == ["1. e4", "e5"]
    assert book.label(mainline[0], False) == "1. e4"
    assert book.label(mainline[-1], True) == "10. Bxe5"
    assert book.label(sides[0][0], True) == "6... Nc6"
    assert book.label(sides[1][0], True) == "5... Nc6"
    assert book.label(sides[2][0], True) == "4... Qe7"

    assert mainline[-1].board().board_fen() == "r1b1kbnr/ppp2ppp/8/4B3/3q4/2N5/PPP1Q1PP/R3KB1R"

    assert book.clean("Attack [%cal Ge4e5] now") == ["Attack now"]
    assert book.clean("one\n\n two  ") == ["one", "two"]

    story = book.block(mainline)
    runs = [f.text for f in story if getattr(f, "style", None) is book.MOVES]
    assert runs == ["1. e4 e5", "2. Nc3 Nf6", "3. f4 exf4", "4. e5 Ng8", "5. Nf3 d6",
                    "6. d4 dxe5", "7. Qe2 Nc6", "8. Bxf4 Nxd4", "9. Nxd4 Qxd4", "10. Bxe5"]
    assert all("[%" not in f.text for f in story if hasattr(f, "text"))
    assert isinstance(story[-1], book.Board) and story[-1].note.text == "after 10. Bxe5"
    assert sum(isinstance(f, book.Board) for f in story) == 1
    assert story[0].spaceBefore == book.VARIATION_GAP, "a variation opens a new line"
    assert story[-1].spaceBefore == book.FIGURE_SPACE, "a diagram detaches from the text above"


if __name__ == "__main__":
    test_study()
    print("ok")
