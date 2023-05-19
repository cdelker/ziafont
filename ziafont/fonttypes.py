from collections import namedtuple
from dataclasses import dataclass


Table = namedtuple('Table', ['checksum', 'offset', 'length'])
BBox = namedtuple('BBox', ['xmin', 'xmax', 'ymin', 'ymax'])
AdvanceWidth = namedtuple('AdvanceWidth', ['width', 'leftsidebearing'])
Header = namedtuple(
    'Header', ['version', 'revision', 'checksumadjust', 'magic', 'flags',
               'created', 'modified', 'macstyle', 'lowestrecppem',
               'directionhint', 'indextolocformat', 'glyphdataformat',
               'numlonghormetrics', 'numglyphs'])
FontNames = namedtuple('FontNames', ['copyright', 'family', 'subfamily', 'unique',
                                     'name', 'nameversion', 'postscript', 'trademark',
                                     'manufacturer', 'designer', 'description', 'vendorurl',
                                     'designerurl', 'license', 'LicenseURL'])
Layout = namedtuple(
    'Layout', ['unitsperem', 'xmin', 'xmax', 'ymin', 'ymax',
               'ascent', 'descent', 'advwidthmax',
               'minleftbearing', 'minrightbearing'])
FontInfo = namedtuple(
    'FontInfo', ['filename', 'names', 'header', 'layout'])

GlyphComp = namedtuple('GlyphComp', ['glyphs', 'xforms', 'bbox'])
Xform = namedtuple('Xform', ['a', 'b', 'c', 'd', 'e', 'f', 'match'])
Symbols = namedtuple('Symbols', ['word', 'symbols', 'width', 'xmin', 'ymin', 'ymax'])


@dataclass
class FontFeatures:
    kern: bool = True   # Horizontal kerning
    liga: bool = True   # Ligatures (combine fi, for example)
    calt: bool = True   # Contextual alternatives
    clig: bool = True   # Contextual ligatures
    salt: bool = False  # Stylistic alternatives (apply all or nothing)
    dlig: bool = False  # Discretionary ligatures
    hlig: bool = False  # Historical ligatures
    c2sc: bool = False  # Small Capitals from Capitals
    frac: bool = False  # Fractions
    zero: bool = False  # Zeros with slash
    ssty: bool = False  # Math script style alternates
