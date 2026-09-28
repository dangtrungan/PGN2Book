#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["chess>=1.11", "reportlab>=4.2"]
# ///
"""Export a PGN study as a typeset two-column PDF book.

    uv run pgn2book.py study.pgn book.pdf [--wood]

Every variation is printed as its own line of bold moves with the comment
prose below it, closed by a diagram of the final position.  Lichess [%cal]
and [%csl] annotations are dropped: this is a book, not a board.
"""
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import chess
import chess.pgn
from reportlab import rl_config
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph)

# ---------------------------------------------------------------- page grid
# Measured off the reference book: A4, 41pt margins, two 245pt columns.
MARGIN = 41.0
GUTTER = 23.4
COLUMN = (A4[0] - 2 * MARGIN - GUTTER) / 2
TOP, BOTTOM = 73.9, 87.0
RIGHT = MARGIN + 2 * COLUMN + GUTTER

BODY_SIZE, BODY_LEAD = 13.74, 18.32
HEAD_SIZE, CAPTION_SIZE = 12.19, 12.22
HEAD_Y, FOLIO_Y = 778.0, 51.3
FIGURE_SPACE, VARIATION_GAP = 12.0, 18.32     # a diagram breathes; a variation opens a new line

# ------------------------------------------------------------------ figures
SQUARE, COORD = 26.0, 8.0
MONO = (white, HexColor("#dcdcdc"))                 # the book default: no colour
WOOD = (HexColor("#f0d9b5"), HexColor("#b58863"))   # lichess colours, opt in with --wood
LIGHT, DARK = MONO
INK = HexColor("#59554e")
GLYPH = {"p": 0x265F, "n": 0x265E, "b": 0x265D, "r": 0x265C, "q": 0x265B, "k": 0x265A}


def register_fonts():
    fonts = Path(__file__).parent / "fonts"
    # ponytail: piece glyphs come from a system Noto font; vendor it to ship this elsewhere
    for name, file in [("Garamond", "EBGaramond-Regular.ttf"),
                       ("Garamond-Bold", "EBGaramond-Bold.ttf"),
                       ("Garamond-Italic", "EBGaramond-Italic.ttf"),
                       ("Garamond-BoldItalic", "EBGaramond-BoldItalic.ttf"),
                       ("NotoChess", "/usr/share/fonts/noto/NotoSansSymbols2-Regular.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(fonts / file)))
    pdfmetrics.registerFontFamily("Garamond", normal="Garamond", bold="Garamond-Bold",
                                  italic="Garamond-Italic", boldItalic="Garamond-BoldItalic")
    rl_config.canvas_basefontname = "Garamond"      # keeps Helvetica out of the page resources


BODY = ParagraphStyle("body", fontName="Garamond", fontSize=BODY_SIZE, leading=BODY_LEAD,
                      alignment=TA_LEFT, firstLineIndent=16.5, spaceAfter=0)
MOVES = ParagraphStyle("moves", parent=BODY, fontName="Garamond-Bold")
TITLE = ParagraphStyle("title", parent=MOVES, fontSize=20.35, leading=25,
                       firstLineIndent=0, spaceAfter=20)
COVER = ParagraphStyle("cover", parent=TITLE, alignment=TA_CENTER, spaceAfter=34)
CAPTION = ParagraphStyle("caption", parent=BODY, fontSize=CAPTION_SIZE, leading=14,
                         alignment=TA_CENTER, firstLineIndent=0)


class Board(Flowable):
    """A 216pt diagram of a position, captioned with the move that reached it."""

    def __init__(self, position, caption):
        super().__init__()
        self.position = position
        self.note = Paragraph(caption, CAPTION)
        self.spaceBefore = FIGURE_SPACE

    def wrap(self, availWidth, availHeight):
        self.w = availWidth
        _, caption = self.note.wrap(availWidth, availHeight)
        self.h = 8 * SQUARE + COORD + caption
        return self.w, self.h

    def draw(self):
        c, pos = self.canv, self.position
        x0 = (self.w - 8 * SQUARE) / 2
        y0 = self.h - 8 * SQUARE
        for f in range(8):
            for r in range(8):
                c.setFillColor(LIGHT if (f + r) % 2 else DARK)
                c.rect(x0 + f * SQUARE, y0 + r * SQUARE, SQUARE, SQUARE, stroke=0, fill=1)
        c.setStrokeColor(black)
        c.setLineWidth(0.5)
        c.rect(x0, y0, 8 * SQUARE, 8 * SQUARE, stroke=1, fill=0)

        c.setFont("Garamond", 6.5)
        c.setFillColor(INK)
        for i in range(8):
            c.drawCentredString(x0 + (i + 0.5) * SQUARE, y0 - COORD + 2.4, "abcdefgh"[i])
            c.drawRightString(x0 - 2.4, y0 + (i + 0.5) * SQUARE - 2.2, str(i + 1))

        c.setFont("NotoChess", 20.5)
        c.setFillColor(black)
        for square, piece in pos.piece_map().items():
            cx = x0 + (chess.square_file(square) + 0.5) * SQUARE
            cy = y0 + (chess.square_rank(square) + 0.5) * SQUARE
            c.drawCentredString(cx, cy - 7.4,
                                chr(GLYPH[piece.symbol().lower()] - (6 if piece.color else 0)))
        if pos.is_check():
            king = pos.king(pos.turn)
            cx = x0 + (chess.square_file(king) + 0.5) * SQUARE
            cy = y0 + (chess.square_rank(king) + 0.5) * SQUARE
            c.setFont("Garamond-Bold", 11)
            c.drawString(cx + 5.5, cy - 3, "#" if pos.is_checkmate() else "+")

        self.note.drawOn(c, 0, 0)


# --------------------------------------------------------------------- pgn
DIRECTIVE = re.compile(r"\[%(?:cal|csl|clk|emt|eval|variation|position|drop|opaque)\b[^\]]*\]")


def clean(comment):
    """Comment text as printable lines, with Lichess board annotations removed."""
    text = DIRECTIVE.sub("", comment or "")
    return [escape(" ".join(line.split())) for line in text.splitlines() if line.split()]


def label(node, first):
    """`1. e4`, `e5`, or `4... Qe7` when a line opens on Black's move.

    `ply()` counts moves from one, so odd plies are White.
    """
    san, ply = node.san(), node.ply()
    if ply % 2:
        return f"{(ply + 1) // 2}. {san}"
    return f"{ply // 2}... {san}" if first else san


def lines(game):
    """One chain of moves per printed line: the mainline, then every sideline."""
    def chain(node):
        """Moves following `node` down its first-child line."""
        out = []
        while node.variations:
            node = node.variations[0]
            out.append(node)
        return out

    main, sides = chain(game), []
    pending = [game]
    while pending:
        for i, child in enumerate(pending.pop().variations):
            if i:
                sides.append((child.ply(), child))
            pending.append(child)
    sides.sort(key=lambda side: -side[0])          # deepest first, tree order within a depth
    return [main] + [[node] + chain(node) for _, node in sides]


def block(moves):
    """A bold run of moves, its comment prose, and the closing diagram."""
    out, run = [], []
    for node in moves:
        run.append(label(node, not run))
        if comment := clean(node.comment):
            out.append(Paragraph(" ".join(run), MOVES))
            run = []
            out += [Paragraph(line, BODY) for line in comment]
    if run:
        out.append(Paragraph(" ".join(run), MOVES))
    last = moves[-1]
    out.append(Board(last.board(), "after " + label(last, True)))
    out[0].spaceBefore = VARIATION_GAP          # every variation opens a new line
    return out


def games(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        while (game := chess.pgn.read_game(handle)) is not None:
            yield game.game() if isinstance(game, chess.pgn.ChildNode) else game


def title_of(game, fallback):
    headers = game.headers
    return headers.get("ChapterName") or headers.get("Event") or fallback


# ------------------------------------------------------------------- output
def furniture(chapter):
    def draw(canvas, _doc):
        canvas.setFillColor(black)
        canvas.setFont("Garamond-Italic", HEAD_SIZE)
        canvas.drawRightString(RIGHT, HEAD_Y, chapter)
        canvas.setFont("Garamond", HEAD_SIZE)
        canvas.drawRightString(RIGHT, FOLIO_Y, str(canvas.getPageNumber()))

    return draw


def build(sources, out):
    register_fonts()
    chapters = list(sources)
    if not chapters:
        sys.exit("no games found")
    frames = [Frame(MARGIN, BOTTOM, COLUMN, A4[1] - TOP - BOTTOM, id="left",
                    leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
              Frame(MARGIN + COLUMN + GUTTER, BOTTOM, COLUMN, A4[1] - TOP - BOTTOM, id="right",
                    leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]
    doc = BaseDocTemplate(out, pagesize=A4, title=chapters[0].headers.get("StudyName", ""))
    doc.addPageTemplates([PageTemplate(id=f"chapter-{i}", frames=frames, onPage=furniture(name))
                          for i, name in enumerate(title_of(g, f"Chapter {i + 1}")
                                                    for i, g in enumerate(chapters))])

    story = []
    for i, game in enumerate(chapters):
        if i:
            story += [NextPageTemplate(f"chapter-{i}"), PageBreak()]
        if i == 0 and (study := game.headers.get("StudyName")):
            story.append(Paragraph(escape(study), COVER))
        story.append(Paragraph(escape(title_of(game, f"Chapter {i + 1}")), TITLE))
        story += [Paragraph(line, BODY) for line in clean(game.comment)]
        for moves in lines(game):
            story += block(moves)
    doc.build(story)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4) or (len(sys.argv) == 4 and sys.argv[3] != "--wood"):
        sys.exit("usage: uv run pgn2book.py STUDY.pgn BOOK.pdf [--wood]")
    if len(sys.argv) == 4:
        LIGHT, DARK = WOOD
    build(games(sys.argv[1]), sys.argv[2])
    print(f"wrote {sys.argv[2]}")
