Drawing Strings
===============

Start by importing Ziafont and loading a font from a file:

.. jupyter-execute::

    import ziafont
    font = ziafont.Font('NotoSerif-Regular.ttf')


The font name can be a path to a ttf or otf font file, or the name of a font (such as 'Arial') located in a system fonts path. If no font name is specified, a built-in font will be used.

Strings can be converted to SVG using :py:meth:`ziafont.font.Font.str2svg`. This method returns a :py:class:`ziafont.font.SVGdraw` object, which provides a Jupyter representation of the string, but also has methods for getting the SVG as text or as an XML element.

.. jupyter-execute::

    font.str2svg('Example')

|

Getting SVG data
----------------

Use the `.svg()` method to get a standalone SVG image as a string, which can then be saved to a file:

.. jupyter-execute::

    s = font.str2svg('Example').svg()
    print(s[:80])  # Just show 80 characters here...


Or `.svgxml()` to get the SVG as an `XML Element Tree <https://docs.python.org/3/library/xml.etree.elementtree.html>`_ that can be added to manually:

.. jupyter-execute::

    font.str2svg('Example').svgxml()

The default font size can be set for all future str2svg calls using :py:meth:`ziafont.set_fontsize`.

|

Drawing on an existing SVG
--------------------------

To draw the string onto an existing SVG, create an SVG XML structure as an XML ElementTree, and pass it as the `canvas` parameter to :py:meth:`ziafont.font.Font.str2svg` along with an `xy` position within the SVG canvas.


.. jupyter-execute::

    from IPython.display import SVG
    from xml.etree import ElementTree as ET

    svg = ET.Element('svg')
    svg.attrib['width'] = '100'
    svg.attrib['height'] = '50'
    svg.attrib['xmlns'] = 'http://www.w3.org/2000/svg'
    svg.attrib['viewBox'] = f'0 0 100 50'
    circ = ET.SubElement(svg, 'circle')
    circ.attrib['cx'] = '50'
    circ.attrib['cy'] = '25'
    circ.attrib['r'] = '25'
    circ.attrib['fill'] = 'orange'

    font.str2svg('Hello', fontsize=18, canvas=svg, xy=(50, 25))
    font.str2svg('123', fontsize=14, canvas=svg, xy=(75, 40))

    SVG(ET.tostring(svg))

|

Multi-line strings
------------------

Multi-line strings (containing `\n` characters) can be drawn. Use `halign` to set horizontal alignment ('left', 'center', or 'right'), and `linespacing` to control the spacing between lines as a multiplier to the normal font-specified line spacing.
The resulting SVG does not require the font to be installed or available to render correctly.

.. jupyter-execute::

    font.str2svg('Two\nLines', halign='center', linespacing=.6)

|

Kerning
-------

If the font contains a `"GPOS" <https://docs.microsoft.com/en-us/typography/opentype/spec/gpos>`_ table, with pair-positioning adjustment, kerning adjustment will be applied to control spacing between individual glyphs. This can be disabled by setting `kern=False`. See the difference in this example:

.. jupyter-execute::

    font.str2svg('VALVES', kern=True)

.. jupyter-execute::

    font.str2svg('VALVES', kern=False)

|

Calculating string size
-----------------------

The method :py:meth:`ziafont.font.Font.getsize` can be used to calculate the pixel width and height of a string without drawing it.

.. jupyter-execute::

    font.getsize('How wide is this string?')

|

Configuration Options
---------------------

The `ziafont.config` object provides some global configuration options.

|

SVG Version Compatibility
*************************

Some SVG renderers, including recent versions of Inkscape and some OS built-in image viewers, are not fully compatible with the SVG 2.0 specification.
Set the `svg2` configuration parameter to `False` for better compatibility. This may result in larger file sizes
as each glyph is included as its own <path> element rather than being reused with <symbol> and <use> elements.

.. code-block:: python

    ziafont.config.svg2 = False

|

Default Font Size
*****************

The default font size can be specified with:

.. code-block:: python

    ziafont.config.fontsize = 36

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

    print('...', ziafont.Text('A').svg()[252:326])

.. jupyter-execute::

    ziafont.config.precision = 2
    # ...

.. jupyter-execute::
    :hide-code:

    print('...', ziafont.Text('A').svg()[228:276])