Drawing Strings
===============

Start by importing Ziafont and loading a font from a file:

.. jupyter-execute::

    import ziafont
    font = ziafont.Font('NotoSerif-Regular.ttf')


The font name can be a path to a ttf or otf font file, or the name of a font (such as 'Arial') located in a system fonts path. If no font name is specified, a built-in font will be used.

Strings can be converted to SVG using :py:meth:`ziafont.font.Text` objects. This object provides a Jupyter representation of the string drawn as SVG, but also has methods for getting the SVG as text or as an XML element.
Running the following line in a Jupyter cell displays the rendered string.

.. jupyter-execute::

    ziafont.Text('Example', font=font)

|

Getting SVG data
----------------

Use the `.svg()` method to get a standalone SVG data as a string, which can then be saved to a file:

.. jupyter-execute::

    s = ziafont.Text('Example', font=font).svg()
    print(s[:80])  # Just show 80 characters here...


Or `.svgxml()` to get the SVG as an `XML Element Tree <https://docs.python.org/3/library/xml.etree.elementtree.html>`_:

.. jupyter-execute::

    ziafont.Text('Example', font=font).svgxml()

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
    svg.set('viewBox', f'0 0 100 50')
    circ = ET.SubElement(svg, 'circle')
    circ.set('cx', '50')
    circ.set('cy', '25')
    circ.set('r', '25')
    circ.set('fill', 'orange')

    ziafont.Text('Hello', font=font, size=18).drawon(svg, 50, 25)
    ziafont.Text('123', font=font, size=14).drawon(svg, 75, 40)

    SVG(ET.tostring(svg))

|

Multi-line strings
------------------

Multi-line strings (containing `\\n` characters) can be drawn. Use `halign` to set horizontal alignment ('left', 'center', or 'right'), and `linespacing` to control the spacing between lines as a multiplier to the normal font-specified line spacing.

.. jupyter-execute::

    ziafont.Text('Two\nLines', font=font, halign='center', linespacing=.8)

|

Rotation
--------

Text can be rotated by providing an angle in degrees.
The `rotation_mode` parameter matches `Matplotlib <https://matplotlib.org/stable/gallery/text_labels_and_annotations/demo_text_rotation_mode.html>`_ `anchor` or `default` behavior for specifying the center of rotation.

.. jupyter-execute::

    ziafont.Text('Rotated', font=font, rotation=30)

|

Kerning
-------

If the font contains a `"GPOS" <https://docs.microsoft.com/en-us/typography/opentype/spec/gpos>`_ table, with pair-positioning adjustment, kerning adjustment will be applied to control spacing between individual glyphs. This can be disabled by setting `kern=False`. See the difference in this example:

.. jupyter-execute::

    ziafont.Text('VALVES', font=font, kern=True)

.. jupyter-execute::

    ziafont.Text('VALVES', font=font, kern=False)

|

Calculating string size
-----------------------

The method :py:meth:`ziafont.font.Text.getsize` can be used to calculate the pixel width and height of a string without drawing it.

.. jupyter-execute::

    ziafont.Text('How wide is this string?').getsize()

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

    print('...', ziafont.Text('A').svg()[252:326])

.. jupyter-execute::

    ziafont.config.precision = 2
    # ...

.. jupyter-execute::
    :hide-code:

    print('...', ziafont.Text('A').svg()[228:276])