# ziafont

Ziafont reads TrueType/OpenType font files and draws characters and strings as SVG <path> elements. Unlike the SVG <text> element, the output of Ziafont's SVG should render identically on any system, independent of whether the original font is available.

Currently, Ziafont supports fonts with TrueType glyph outlines contained in a "glyf" table in the font (these fonts typically have a .ttf extensions). Glyph outlines in a "CFF" table (typically fonts with the .otf extension) are not supported at this time. Kerning adjustment is supported if the font has a "GPOS" table.

Documentation is available at [readthedocs](https://ziafont.readthedocs.io)
