Font Inspection
===============

.. jupyter-execute::
    :hide-code:

    import ziafont


Ziafont provides some methods for inspecting a font and its glyphs.
The following classes use Jupyter representers to show the output in Jupyter cells,
but the output may also be obtained using the methods of the class, such as `table()`.

To see a table of all glyphs in a font, use :py:class:`ziafont.inspect.ShowGlyphs`.

Here, only the first 105 glyphs are shown of the default DejaVu Sans font:

.. jupyter-execute::

    font = ziafont.Font()
    ziafont.inspect.ShowGlyphs(font, nmax=105)


|

To see the glyph substitutions made by a font feature, use :py:class:`ziafont.inspect.ShowFeature`.
This example shows the substitutions made by the DejaVu Sans `salt` (Stylistic Alternatives) feature.

.. jupyter-execute::

    ziafont.inspect.ShowFeature('salt', font)

Glyph info is shown with :py:class:`ziafont.inspect.DescribeGlyph`:

.. jupyter-execute::

    ziafont.inspect.DescribeGlyph(font.glyph('B'))

And a detail rendering of the glyph and its control points:

.. jupyter-execute::

    ziafont.inspect.InspectGlyph(font.glyph('B'))

|

Finally, :py:class:`ziafont.inspect.DescribeFont` provides metadata about the font.

.. jupyter-execute::

    ziafont.inspect.DescribeFont(font)
