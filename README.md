# ziafont

Ziafont reads TrueType/OpenType font files and draws characters and strings as SVG <path> elements. Unlike the SVG <text> element, the output of Ziafont's SVG will render identically on any system, independent of whether the original font is available.

Ziafont supports fonts with TrueType glyph outlines contained in a "glyf" table in the font (these fonts typically have a .ttf extensions), or fonts with a "CFF " table (typically with a .otf extension). Kerning adjustment and glyph substitution are supported if the font has a "GPOS" table.

Documentation is available at [readthedocs](https://ziafont.readthedocs.io). There is also an [online demo](https://cdelker.github.io/pyscript/ziafont.html) of Glyph rendering using Ziafont.
