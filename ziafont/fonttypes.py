from collections import namedtuple

Table = namedtuple('Table', ['checksum', 'offset', 'length'])
BBox = namedtuple('BBox', ['xmin', 'xmax', 'ymin', 'ymax'])
AdvanceWidth = namedtuple('AdvanceWidth', ['width', 'leftsidebearing'])
Header = namedtuple(
    'Header', ['version', 'revision', 'checksumadjust', 'magic', 'flags',
               'created', 'modified', 'macstyle', 'lowestrecppem',
               'directionhint', 'indextolocformat', 'glyphdataformat', 'numlonghormetrics'])
Layout = namedtuple(
    'Layout', ['unitsperem', 'xmin', 'xmax', 'ymin', 'ymax',
               'ascent', 'descent', 'advwidthmax',
               'minleftbearing', 'minrightbearing'])
FontInfo = namedtuple(
    'FontInfo', ['name', 'header', 'layout', 'advwidths'])

GlyphPath = namedtuple('GlyphPath', ['xvals', 'yvals', 'ctvals', 'ends', 'bbox', ])####'advwidth'])
GlyphComp = namedtuple('GlyphComp', ['glyphs', 'xforms', 'bbox'])
Xform = namedtuple('Xform', ['a', 'b', 'c', 'd', 'e', 'f', 'match'])
