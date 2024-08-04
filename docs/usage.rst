Usage
=====

Start by importing Ziafont and loading a font from a file:

.. jupyter-execute::

    import ziafont
    font = ziafont.Font('NotoSerif-Regular.ttf')


The font name may be a path to a ttf or otf font file.
It may also be the name of a font installed in the OS system font path.
If no font name is specified, a built-in font will be used.

Strings can be converted to SVG using :py:class:`ziafont.font.Text` objects.

.. jupyter-execute::

    font.text('Example')

This object provides a Jupyter representation of the string drawn as SVG, so when run in a Jupyter cell
the rendered text is displayed automatically.

The Text object  also has methods for getting the SVG as text or as an XML element.
Use the `.svg()` method to get a standalone SVG data as a string, which can then be saved to a file:

.. jupyter-execute::

    s = font.text('Example').svg()
    print(s[:80])  # Just show 80 characters here...

Or `.svgxml()` to get the SVG as an `XML Element Tree <https://docs.python.org/3/library/xml.etree.elementtree.html>`_:

.. jupyter-execute::

    font.text('Example').svgxml()

|

Size
----

The font size is set with the `size` parameter:

.. jupyter-execute::

    font.text('small', size=12)

.. jupyter-execute::

    font.text('large', size=72)


Color
-----

The color of text is set using any valid CSS color, either a named color (such as 'red', 'blue') or hex (such as '#FF0000').

.. jupyter-execute::

    font.text('medium slate blue', color='mediumslateblue')

|

Rotation
--------

Text can be rotated by providing an angle in degrees.
The `rotation_mode` parameter matches `Matplotlib <https://matplotlib.org/stable/gallery/text_labels_and_annotations/demo_text_rotation_mode.html>`_ `anchor` or `default` behavior for specifying the center of rotation.

.. jupyter-execute::

    font.text('Rotated', rotation=30)

|

Multi-line strings
------------------

Multi-line strings (containing `\\n` characters) can be drawn. Use `halign` to set horizontal alignment ('left', 'center', or 'right'), and `linespacing` to control the spacing between lines as a multiplier to the normal font-specified line spacing.

.. jupyter-execute::

    font.text('Two\nLines', halign='center', linespacing=.8)

|

Features
--------

The :py:data:`ziafont.Font.features` attribute is used to enable certain typesetting features,
such as kerning adjustment and ligature replacement.

The `features` attribute provides a lits of available features for the font and
their enabled status.

.. jupyter-execute::

    font = ziafont.Font()
    font.features

Here's the default rendering of a word:

.. jupyter-execute::

    font.text('apple')

and with the `salt` (Stylistic Alternatives) feature enabled, this font substitues
different glyphs for `a` and `l`, among others:

.. jupyter-execute::

    font.features['salt'] = True
    font.text('apple')

The feature attribute names correspond to user-configurable `Open Type font features <https://learn.microsoft.com/en-us/typography/opentype/spec/featurelist>`_.


Kerning
*******

If the font contains a `"GPOS" <https://docs.microsoft.com/en-us/typography/opentype/spec/gpos>`_ table, with pair-positioning adjustment, kerning adjustment will be applied to control spacing between individual glyphs.
This can be disabled by turning off the `kern` feature. See the difference in this example:

.. jupyter-execute::

    font = ziafont.Font()
    font.features['kern'] = False
    font.text('Type')

.. jupyter-execute::

    font.features['kern'] = True
    font.text('Type')


Ligatures
*********

In some fonts, multiple glyphs may be drawn with a single ligature glyph, common in combinations such as "ff" or "fl".
Ligature substitution will be applied by default if the font contains ligature data in a `"GSUB" <https://docs.microsoft.com/en-us/typography/opentype/spec/gsub>`_ table.
It can be disabled by setting the `liga` feature to False.


.. jupyter-execute::

    font.features['liga'] = False
    font.text('waffle')

.. jupyter-execute::

    font.features['liga'] = True
    font.text('waffle')

|


Drawing on an existing SVG
--------------------------

To draw the string onto an existing SVG, use the :py:meth:`ziafont.font.Text.drawon` method. Create an SVG XML structure as an XML ElementTree, and pass it as the `svg` parameter along with an `xy` position within the SVG canvas.

.. jupyter-execute::

    from IPython.display import SVG
    from xml.etree import ElementTree as ET

    svg = ET.Element('svg')
    svg.set('width', '100')
    svg.set('height', '50')
    svg.set('xmlns', 'http://www.w3.org/2000/svg')
    svg.set('viewBox', '0 0 100 50')
    circ = ET.SubElement(svg, 'circle')
    circ.set('cx', '50')
    circ.set('cy', '25')
    circ.set('r', '25')
    circ.set('fill', 'orange')

    font.text('Hello', size=18).drawon(svg, 50, 25)
    font.text('123', size=14).drawon(svg, 75, 40)

    SVG(ET.tostring(svg))

The `halign` parameter specifies the typical horizontal alignment of `left`, `right`, or `center`. Vertical alignment is set with the `valign` parameter, and may be `top`, `center`, `bottom`, or `base`. A `base` alignment will align with the baseline of the first row of text in the string, while `bottom` alignment aligns with the bottom of the entire block of text.

.. jupyter-execute::

    ziafont.config.fontsize = 16
    ziafont.config.debug = True  # Show bounding box and origin
    svg = ET.Element('svg')
    svg.attrib['xmlns'] = 'http://www.w3.org/2000/svg'
    svg.attrib['xmlns:xlink'] = 'http://www.w3.org/1999/xlink'
    svg.attrib['width'] = '300'
    svg.attrib['height'] = '100'
    svg.attrib['viewBox'] = '0 0 300 100'

    font.text('align\ntop', valign='top').drawon(svg, 50, 50)
    font.text('align\ncenter', valign='center').drawon(svg, 100, 50)
    font.text('align\nbase', valign='base').drawon(svg, 160, 50)
    font.text('align\nbottom', valign='bottom').drawon(svg, 210, 50)

    SVG(ET.tostring(svg))


.. jupyter-execute::
    :hide-code:
    
    ziafont.config.debug = False
    ziafont.config.fontsize = 48

|

Glyphs
------

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

Glyph Indexes
*************

The glyph index refers to its position within the font file, not necessarily the unicode representation of the character.
The index for a given character in the font can be obtained:

.. jupyter-execute::

    font.glyphindex('&')


.. jupyter-execute::

    font.glyph_fromid(9)



Calculating string size
-----------------------

The method :py:meth:`ziafont.font.Text.getsize` can be used to calculate the pixel width and height of a string without drawing it.

.. jupyter-execute::

    font.text('How wide is this string?').getsize()

|

Configuration Options
---------------------

The `ziafont.config` object provides some global configuration options.

|

Default Font Size
*****************

The default font size can be specified with:

.. code-block:: python

    ziafont.config.fontsize = 36

|

SVG Version Compatibility
*************************

Some SVG renderers, including recent versions of Inkscape and some OS built-in image viewers, are not fully compatible with the SVG 2.0 specification.
Set the `svg2` configuration parameter to `False` for better compatibility. This may result in larger file sizes
as each glyph is included as its own <path> element rather than being reused with <symbol> and <use> elements.

.. code-block:: python

    ziafont.config.svg2 = False

|

SVG decimal precision
*********************

The decimal precision of coordinates in SVG tags can be set using `ziafont.config.precision`.
Lower precision saves space in the SVG string, but may reduce quality of the image.

.. jupyter-execute::

    ziafont.config.precision = 6
    # ...

.. jupyter-execute::
    :hide-code:

    print('...', font.text('A').svg()[252:326])

.. jupyter-execute::

    ziafont.config.precision = 2
    # ...

.. jupyter-execute::
    :hide-code:

    print('...', font.text('A').svg()[228:276])

|

Limitations
-----------

Ziafont does not currently support right-to-left scripts, or scripts that require advanced `Complex Text Layout <https://en.wikipedia.org/wiki/Complex_text_layout>`_ rules that are not defined in the font file itself.

GSUB Lookup types 5 and 8, and GPOS lookup types 3, 5, 7, and 8 are not currently implemented, along with many script-specific `features <https://learn.microsoft.com/en-us/typography/opentype/spec/featurelist>`_.