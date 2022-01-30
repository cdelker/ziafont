Ziafont
=======

Ziafont reads TrueType/OpenType font files and draws characters and strings as SVG <path> elements.
Unlike the SVG <text> element, the output of Ziafont's SVG should render identically on any system, independent of whether the
original font is available. However, the SVG will not be text-searchable, as characters are replaced by curves.

Currently, Ziafont supports fonts with TrueType glyph outlines contained in a "glyf" table in the font (these fonts typically have a .ttf extensions). Glyph outlines in a "CFF" table (typically fonts with the .otf extension) are not supported at this time.
Kerning adjustment is supported if the font has a "GPOS" table.

Example
-------

.. jupyter-execute::

    import ziafont
    font = ziafont.Font('NotoSerif-Regular.ttf')
    font.str2svg('Ziafont!')

.. jupyter-execute::

    s = font.str2svg('Z').svg()
    print(s[:80])  # Just show 80 characters here...

|

Installation
------------

Ziafont can be installed using pip:

.. code-block:: bash

    pip install ziafont


No dependencies are required.

|

Support
-------

If you appreciate Ziafont, buy me a coffee to show your support!

.. raw:: html

    <script type="text/javascript" src="https://cdnjs.buymeacoffee.com/1.0.0/button.prod.min.js" data-name="bmc-button" data-slug="cdelker" data-color="#FFDD00" data-emoji=""  data-font="Cookie" data-text="Buy me a coffee" data-outline-color="#000000" data-font-color="#000000" data-coffee-color="#ffffff" ></script>

|

----

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   strings.rst
   glyphs.rst
   api.rst