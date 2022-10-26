''' Glyph classes '''

from __future__ import annotations
from typing import Sequence, Optional, TYPE_CHECKING
from types import SimpleNamespace

import os
import xml.etree.ElementTree as ET

from .fonttypes import GlyphComp, BBox
from .config import config
from .svgpath import fmt, SVGOpType
from .glyphinspect import InspectGlyph, DescribeGlyph

if TYPE_CHECKING:
    from .font import Font


class SimpleGlyph:
    ''' Simple Glyph '''
    dfltsize = 12   # Draw <symbols> in this point size

    def __init__(self, index: int, operators: Sequence[SVGOpType],
                 bbox: BBox, font: Font):
        self.index = index
        self.operators = operators
        self.bbox = bbox
        self.path = SimpleNamespace()
        self.path.bbox = bbox  # Only for backward-compatibility
        self.font = font
        basename, _ = os.path.splitext(os.path.basename(self.font.info.filename))
        basename = ''.join(c for c in basename if c.isalnum())
        self.id = f'{basename}_{index}'
        self.emscale = self.dfltsize / self.font.info.layout.unitsperem

    def _repr_svg_(self):
        return ET.tostring(self.svgxml(), encoding='unicode')

    @property
    def char(self) -> set[str]:
        ''' Get set of unicode character represented by this glyph '''
        if self.font.cmap:
            return self.font.cmap.char(self.index)
        return set()
    
    def place(self, x: float, y: float, fontsize: float) -> Optional[ET.Element]:
        ''' Get <use> svg tag translated/scaled to the right position '''
        fntscale = (fontsize/self.dfltsize)
        yshift = self.font.info.layout.ymax * self.emscale * fntscale
        elm: Optional[ET.Element]
        if config.svg2:
            elm = ET.Element('use')
            elm.attrib['href'] = f'#{self.id}'
            dx = min(self.bbox.xmin * self.emscale * fntscale, 0)
            elm.attrib['transform'] = f'translate({fmt(x+dx)} {fmt(y-yshift)}) scale({fmt(fntscale)})'
        else:
            elm = self.svgpath(x0=x, y0=y, scale=fntscale)
        return elm

    def advance(self, nextchr=None):
        ''' Get advance width in glyph units, including kerning if nextchr is defined '''
        if nextchr:
            nextchr = nextchr.index
        return self.font.advance(self.index, nextchr)

    def svgpath(self, x0: float = 0, y0: float = 0, scale: float = 1) -> Optional[ET.Element]:
        ''' Get svg <path> element for glyph, normalized to 12-point font '''
        emscale = self.emscale * scale
        path = ''
        for i, op in enumerate(self.operators):
            segment = op.path(x0, y0, scale=emscale)
            if segment[0] == 'M' and path != '':
                path += 'Z '  # Close intermediate segments
            path += segment
        if path == '':
            return None  # Don't return empty path
        path += 'Z '
        return ET.Element('path', attrib={'d': path})

    def svgsymbol(self) -> ET.Element:
        ''' Get svg <symbol> element for this glyph, scaled to 12-point font '''
        xmin = min(self.bbox.xmin * self.emscale, 0)
        xmax = self.bbox.xmax * self.emscale
        width = xmax-xmin
        ymax = max(self.font.info.layout.ymax, self.bbox.ymax) * self.emscale
        ymin = min(self.font.info.layout.ymin, self.bbox.ymin) * self.emscale
        height = ymax - ymin

        sym = ET.Element('symbol')
        sym.attrib['id'] = self.id
        sym.attrib['width'] = fmt(width)
        sym.attrib['height'] = fmt(height)
        sym.attrib['viewBox'] = f'{fmt(xmin)} {fmt(-ymax)} {fmt(width)} {fmt(height)}'
        path = self.svgpath()
        if path is not None:
            sym.append(path)
        return sym

    def svg(self, fontsize: float = None) -> str:
        ''' Get SVG as string '''
        return ET.tostring(self.svgxml(fontsize), encoding='unicode')

    def svgxml(self, fontsize: float = None) -> ET.Element:
        ''' Standalong SVG '''
        fontsize = fontsize if fontsize else config.fontsize
        scale = fontsize / self.font.info.layout.unitsperem

        # Width varies by character, but height is constant for the whole font
        # View should include whole character, even if it goes negative/outside the advwidth
        xmin = min(self.bbox.xmin * scale, 0)
        xmax = self.bbox.xmax * scale
        ymin = min(self.bbox.ymin, self.font.info.layout.ymin) * scale

        # ymax can go above font's ymax for extended (ie math) glyphs
        ymax = max(self.bbox.ymax, self.font.info.layout.ymax) * scale
        width = xmax - xmin
        height = ymax - ymin
        base = ymax
        scale = fontsize/self.dfltsize

        svg = ET.Element('svg')
        svg.attrib['width'] = fmt(width)
        svg.attrib['height'] = fmt(height)
        svg.attrib['xmlns'] = 'http://www.w3.org/2000/svg'
        svg.attrib['viewBox'] = f'{fmt(xmin)} 0 {fmt(width)} {fmt(height)}'
        if not config.svg2:
            svg.attrib['xmlns:xlink'] = 'http://www.w3.org/1999/xlink'
            elm = self.svgpath(x0=0, y0=base, scale=scale)
            if elm is not None:
                svg.append(elm)
        else:
            symbol = self.svgsymbol()
            svg.append(symbol)
            g = ET.SubElement(svg, 'use')
            g.attrib['href'] = f'#{self.id}'
            g.attrib['transform'] = f'translate({fmt(xmin)}, {fmt(base-ymax)}) scale({fmt(scale)})'
        return svg

    def test(self, pxwidth: float=400, pxheight: float=400) -> InspectGlyph:
        ''' Get Glyph Test representation showing vertices and borders '''
        return InspectGlyph(self, pxwidth, pxheight)

    def describe(self) -> DescribeGlyph:
        ''' Get Glyph Test representation showing vertices and borders '''
        return DescribeGlyph(self)


class CompoundGlyph(SimpleGlyph):
    ''' Compound glyph, made of multiple other Glyphs '''
    def __init__(self, index: int, glyphs: GlyphComp, font: Font):
        self.index = index
        self.glyphs = glyphs
        operators = self._buildcompound()
        super().__init__(index, operators, self.glyphs.bbox, font)

    def _buildcompound(self) -> list[SVGOpType]:
        ''' Combine multiple glyphs into one set of contours '''
        xoperators = []
        for glyph, xform in zip(self.glyphs.glyphs, self.glyphs.xforms):
            if xform.match:
                raise NotImplementedError('Compound glyph match transform')

            m0 = max(abs(xform.a), abs(xform.b))
            n0 = max(abs(xform.c), abs(xform.d))
            m = 2*m0 if abs(abs(xform.a)-abs(xform.c)) <= 33/65536 else m0
            n = 2*n0 if abs(abs(xform.b)-abs(xform.d)) <= 33/65536 else n0
            for op in glyph.operators:
                xoperators.append(op.xform(xform.a, xform.b, xform.c,
                                           xform.d, xform.e, xform.f, m, n))
        return xoperators



class EmptyGlyph(SimpleGlyph):
    ''' Glyph with no contours (like a space) '''
    def __init__(self, index: int, font: Font):
        super().__init__(index, [], BBox(0, 0, 0, 0), font)
