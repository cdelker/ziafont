Drawing Glyphs
==============

.. jupyter-execute::
    :hide-code:
    
    import ziafont
    font = ziafont.Font('NotoSerif-Regular.ttf')


At a lower level, Ziafont can also draw individual glyphs. The glyph for a string character can be obtained from :py:meth:`ziafont.font.Font.glyph`.
Similar to :py:meth:`ziafont.font.Text`, this method returns a Glyph object with methods for returning SVG as a string or as an SVG XML element.


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

To view the control points of a glyph path, use the `test` method:

.. jupyter-execute::

    font.glyph('p').test()

Notice how some glyphs can extend below the baseline (red).
Additional glyph information can be displayed:

.. jupyter-execute::

    font.glyph('p').describe()


|

Glyph Indexes
-------------

The glyph index refers to its position within the font file, not necessarily the unicode representation of the character.
The index for a given character in the font can be obtained:

.. jupyter-execute::

    font.glyphindex('&')


.. jupyter-execute::

    font.glyph_fromid(9)

