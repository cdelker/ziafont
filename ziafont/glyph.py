''' Glyph classes '''

from __future__ import annotations
from typing import Sequence, Optional, TYPE_CHECKING
from types import SimpleNamespace

import os
import xml.etree.ElementTree as ET

from .fonttypes import GlyphComp, BBox
from .config import config
from .svgpath import fmt, SVGOpType

if TYPE_CHECKING:
    from .font import Font


    
class SimpleGlyph:
    ''' Simple Glyph '''
    dfltsize = 12   # Draw <symbols> in this point size

    def __init__(self, index: int, operators: Sequence[SVGOpType],
                 bbox: BBox, font: Font, char: str = None):
        self.char = char
        self.index = index
        self.operators = operators
        self.bbox = bbox
        self.path = SimpleNamespace()
        self.path.bbox = bbox  # Only for backward-compatibility
        self.font = font
        basename, _ = os.path.splitext(os.path.basename(self.font.info.filename))
        self.id = f'{basename}_{index}'
        self.emscale = self.dfltsize / self.font.info.layout.unitsperem

    def _repr_svg_(self):
        return ET.tostring(self.svgxml(), encoding='unicode')

    def place(self, x: float, y: float, fontsize: float) -> Optional[ET.Element]:
        ''' Get <use> svg tag translated/scaled to the right position '''
        fntscale = (fontsize/self.dfltsize)
        yshift = self.font.info.layout.ymax * self.emscale * fntscale
        elm: Optional[ET.Element]
        if config.svg2:
            elm = ET.Element('use')
            elm.attrib['href'] = f'#{self.id}'
            dx = self.bbox.xmin * self.emscale * fntscale
            elm.attrib['transform'] = f'translate({fmt(x+dx)} {fmt(y-yshift)}) scale({fmt(fntscale)})'
        else:
            elm = self.svgpath(x0=x, y0=y, scale=fntscale)
        return elm

    def advance(self, nextchr=None, kern=True):
        ''' Get advance width in glyph units, including kerning if nextchr is defined '''
        if nextchr:
            nextchr = nextchr.index
        return self.font.advance(self.index, nextchr, kern=kern)

    def svgpath(self, x0: float = 0, y0: float = 0, scale: float = 1) -> Optional[ET.Element]:
        ''' Get svg <path> element for glyph, normalized to 12-point font '''
        emscale = self.emscale * scale
        path = ''
        for i, op in enumerate(self.operators):
            path += op.path(x0, y0, scale=emscale)
        if path == '':
            return None
        path += 'Z '
        return ET.Element('path', attrib={'d': path})

    def svgsymbol(self) -> ET.Element:
        ''' Get svg <symbol> element for this glyph, scaled to 12-point font '''
        xmin = min(self.bbox.xmin * self.emscale, 0)
        xmax = self.bbox.xmax
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

    def svg(self, fontsize: float = None, svgver: int = 2) -> str:
        ''' Get SVG as string '''
        return ET.tostring(self.svgxml(fontsize, svgver=svgver),
                           encoding='unicode')

    def svgxml(self, fontsize: float = None, svgver: int = 2) -> ET.Element:
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

    def test(self) -> 'TestGlyph':
        ''' Get Glyph Test representation showing vertices and borders '''
        return TestGlyph(self)


class CompoundGlyph(SimpleGlyph):
    ''' Compound glyph, made of multiple other Glyphs '''
    def __init__(self, index: int, glyphs: GlyphComp, font: Font, char: str = None):
        self.char = char
        self.index = index
        self.glyphs = glyphs
        operators = self._buildcompound()
        super().__init__(index, operators, self.glyphs.bbox, font, char)

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


class TestGlyph:
    ''' Draw glyph svg with test/debug lines '''
    def __init__(self, glyph: SimpleGlyph):
        self.glyph = glyph

    def _repr_svg_(self):
        ''' Jupyter representation '''
        return self.svg()

    def svg(self, fontsize: float = None) -> str:
        ''' Glyph SVG string '''
        return ET.tostring(self.svgxml(fontsize), encoding='unicode')

    def svgxml(self, fontsize: float = None) -> ET.Element:
        ''' Glyph svg as XML element tree '''
        fontsize = fontsize if fontsize else config.fontsize
        svg = self.glyph.svgxml(fontsize)
        scale = fontsize / self.glyph.font.info.layout.unitsperem
        xmin = min(self.glyph.bbox.xmin * scale, 0)
        xmax = self.glyph.bbox.xmax * scale
        ymin = min(self.glyph.bbox.ymin, self.glyph.font.info.layout.ymin) * scale
        ymax = max(self.glyph.bbox.ymax, self.glyph.font.info.layout.ymax) * scale
        width = xmax - xmin
        height = ymax - ymin
        base = ymax  # = height - ymin

        # Borders and baselines
        path = ET.SubElement(svg, 'path')
        path.attrib['d'] = f'M {fmt(xmin)} {fmt(base)} L {fmt(width)} {fmt(base)}'
        path.attrib['stroke'] = 'red'

        ascent = base - self.glyph.font.info.layout.ascent * scale
        descent = base - self.glyph.font.info.layout.descent * scale
        path = ET.SubElement(svg, 'path')
        path.attrib['d'] = f'M {fmt(xmin)} {fmt(ascent)} L {fmt(width)} {fmt(ascent)}'
        path.attrib['stroke'] = 'gray'
        path.attrib['stroke-dasharray'] = '2 2'
        path = ET.SubElement(svg, 'path')
        path.attrib['d'] = f'M {fmt(xmin)} {fmt(descent)} L {fmt(width)} {fmt(descent)}'
        path.attrib['stroke'] = 'gray'
        path.attrib['stroke-dasharray'] = '2 2'
        rect = ET.SubElement(svg, 'rect')
        rect.attrib['x'] = '0'
        rect.attrib['y'] = '0'
        rect.attrib['width'] = fmt(xmax)
        rect.attrib['height'] = fmt(height)
        rect.attrib['fill'] = 'none'
        rect.attrib['stroke'] = 'blue'
        rect.attrib['stroke-dasharray'] = '2 2'
        circ = ET.SubElement(svg, 'circle')
        circ.attrib['cx'] = '0'
        circ.attrib['cy'] = fmt(base)
        circ.attrib['r'] = '3'
        circ.attrib['fill'] = 'red'

        for op in self.glyph.operators:
            points, ctrls = op.points()
            for p, c in zip(points, ctrls):
                circ = ET.SubElement(svg, 'circle')
                circ.attrib['cx'] = fmt(p.x * scale)
                circ.attrib['cy'] = fmt(base-p.y * scale)
                circ.attrib['r'] = f'{fmt(min(3, fontsize*scale/3))}'
                circ.attrib['fill'] = 'none' if c else 'blue'
                circ.attrib['stroke'] = 'blue'
                circ.attrib['opacity'] = '0.4'

        return svg


class EmptyGlyph(SimpleGlyph):
    ''' Glyph with no contours (like a space) '''
    def __init__(self, index: int, font: Font):
        super().__init__(index, [], BBox(0, 0, 0, 0), font)
