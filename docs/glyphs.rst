Drawing Glyphs
==============

.. jupyter-execute::
    :hide-code:
    
    import ziafont
    font = ziafont.Font('NotoSerif-Regular.ttf')


At a lower level, Ziafont can also draw individual glyphs. The glyph for a string character can be obtained from :py:meth:`ziafont.font.Font.glyph`.
Like str2svg, this method returns an object with methods for returning SVG as a string or as an SVG XML element.


.. jupyter-execute::

    font.glyph('D')    

.. jupyter-execute::

    font.glyph('D').svgxml()


The above `svg` and `svgxml` methods both return the glyph in a standalone SVG.
Often, however, the glyph should be added to an existing drawing or used elsewhere.
The `svgpath` method returns the glyph as an SVG <path> element that can be inserted in an existing SVG.
Alternatively, the `svgsymbol` method wraps the <path> in an SVG <symbol> element that can be reused multiple times in the same drawing.

|

Test Mode
---------

In addition to the glyph symbol, each glyph contains information about its bounding box.
To view the bounding box and baseline of a glyph, use the `test` method:

.. jupyter-execute::

    font.glyph('p').test()

Notice how some glyphs can extend below the baseline (red).

|

Glyph Indexes
-------------

The glyph index refers to its position within the font file, not necessarily the unicode representation of the character.
The index for a given character in the font can be obtained:

.. jupyter-execute::

    font.glyphindex('&')


.. jupyter-execute::

    font.glyph_fromid(9)

