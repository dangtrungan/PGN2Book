# PGN2Book
Export Lichess Study PGN files into beautifully typeset PDF chess books.

    uv run pgn2book.py example.pgn book.pdf

No setup: `uv` installs the two dependencies (`python-chess`, `reportlab`) from
the script's own header. Each study chapter becomes a PDF chapter on its own
page, set in two 245pt columns of EB Garamond on A4. Moves are bold, the
author's prose is ragged-right with a first-line indent, and every variation
closes with a captioned diagram of the position it reaches.

Diagrams are monochrome: white and pale grey squares, solid black pieces, a
black frame. Pass `--wood` for lichess-coloured squares.

Order inside a chapter: the mainline first, then each sideline as its own
line, deepest first.

`[%cal]` and `[%csl]` board annotations are dropped, along with any empty
variation. This is a book, not a board.

## Study tags

| tag | used for |
| --- | --- |
| `StudyName` | title on the first page |
| `ChapterName` | chapter title and running head (falls back to `Event`) |
| `FEN` / `SetUp` | starting position |

## Fonts

`fonts/` holds four static instances of [EB Garamond][ebg], instanced from the
Google Fonts variable builds under the SIL Open Font License 1.1 (see
`fonts/OFL.txt`, which ships with the book):

    fonttools varLib.instancer "EBGaramond[wght].ttf"        wght=400 -o fonts/EBGaramond-Regular.ttf
    fonttools varLib.instancer "EBGaramond[wght].ttf"        wght=700 -o fonts/EBGaramond-Bold.ttf
    fonttools varLib.instancer "EBGaramond-Italic[wght].ttf" wght=400 -o fonts/EBGaramond-Italic.ttf
    fonttools varLib.instancer "EBGaramond-Italic[wght].ttf" wght=700 -o fonts/EBGaramond-BoldItalic.ttf

Pieces are drawn from the system font
`/usr/share/fonts/noto/NotoSansSymbols2-Regular.ttf`; vendor it if you need
this to run anywhere else.

## Check

    uv run test_pgn2book.py

[ebg]: https://fonts.google.com/specimen/EB+Garamond
