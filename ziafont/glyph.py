''' Glyph classes '''

from __future__ import annotations
from typing import Union

import os
import xml.etree.ElementTree as ET

from .fonttypes import GlyphPath, GlyphComp, FontInfo, BBox, Xform

DEFAULT_FONTSIZE = 48


def set_fontsize(size: int) -> None:
    ''' Set the default font size '''
    global DEFAULT_FONTSIZE
    DEFAULT_FONTSIZE = size


def dflt_fontsize() -> float:
    ''' Get default fontsize '''
    return DEFAULT_FONTSIZE


def read_glyph(glyphid: int, font):
    ''' Read a glyph from the glyf table. '''
    offset = font._glyphoffset(glyphid)
    
    
    if offset is None:
        return EmptyGlyph(glyphid, font)

    if offset >= font.tables['glyf'].offset + font.tables['glyf'].length:
        return EmptyGlyph(glyphid, font)

    assert offset >= font.tables['glyf'].offset
    assert offset < font.tables['glyf'].offset + font.tables['glyf'].length

    font.fontfile.seek(offset)
    
    numcontours = font.fontfile.readint16()
    xmin = font.fontfile.readint16()
    ymin = font.fontfile.readint16()
    xmax = font.fontfile.readint16()
    ymax = font.fontfile.readint16()
    charbox = BBox(xmin, xmax, ymin, ymax)
    glyph: Union[SimpleGlyph, CompoundGlyph]
    if numcontours == -1:
        glyph = read_compoundglyph(font, glyphid, charbox)
    else:
        glyph = read_simpleglyph(font, glyphid, numcontours, charbox)
    return glyph


def read_simpleglyph(font, index, numcontours, charbox):
    ''' Read a symple glyph from the fontfile. Assumes file pointer is set '''
    fontfile = font.fontfile
    ends = []
    for i in range(numcontours):
        ends.append(font.fontfile.readuint16())
    instlength = fontfile.readuint16()
    fontfile.seek(instlength + fontfile.tell())  # Skip instructions

    numpoints = max(ends) + 1

    # flags
    ONCURVE = 0x01
    XSHORT = 0x02
    YSHORT = 0x04
    REPEAT = 0x08
    XDUP = 0x10
    YDUP = 0x20

    flags = []
    i = 0
    while i < numpoints:
        flag = fontfile.readuint8()
        if (flag & REPEAT):
            nrepeats = fontfile.readuint8() + 1  # Include the first one too
        else:
            nrepeats = 1
        flags.extend([flag] * nrepeats)
        i += nrepeats

    ctvals = [(f & ONCURVE) == 0 for f in flags]  # True for control point, False for real point
    xvals = []
    xval = 0  # Points are stored as deltas. Add them up as we go to get real points.
    for flag in flags:
        if (flag & XSHORT):  # X is one-byte
            if (flag & XDUP):
                xval += fontfile.readuint8()
            else:
                xval -= fontfile.readuint8()
        elif not (flag & XDUP):
            xval += fontfile.readint16()
        # else: xval stays the same
        xvals.append(xval)

    yvals = []
    yval = 0  # Add up deltas
    for flag in flags:
        if (flag & YSHORT):  # Y is one-byte
            if (flag & YDUP):
                yval += fontfile.readuint8()
            else:
                yval -= fontfile.readuint8()
        elif not (flag & YDUP):
            yval += fontfile.readint16()
        # else: yval stays the same
        yvals.append(yval)

    path = GlyphPath(xvals, yvals, ctvals, ends, charbox)
    glyph = SimpleGlyph(index, path, font)
    return glyph

    
def read_compoundglyph(font, index, charbox):
    ''' Read compound glyph from the fontfile. Assumes filepointer is set '''
    fontfile = font.fontfile

    ARG_WORDS = 0x0001
    ARG_XY = 0x0002
    # ROUND = 0x0004
    SCALE = 0x0008
    MORE = 0x0020
    XYSCALE = 0x0040
    TWOBYTWO = 0x0080
    # INSTRUCTIONS = 0x0100
    # METRICS = 0x0200
    # OVERLAP = 0x0400

    glyphidxs = []
    xforms = []
    moreglyphs = True
    while moreglyphs:
        flag = fontfile.readuint16()
        moreglyphs = (flag & MORE) == MORE
        subindex = fontfile.readuint16()
        match = False
        if (flag & ARG_WORDS):
            if (flag & ARG_XY):
                e = fontfile.readint16()
                f = fontfile.readint16()
            else:
                match = True
                e = fontfile.readuint16()
                f = fontfile.readuint16()
        else:
            if (flag & ARG_XY):
                e = fontfile.readint8()
                f = fontfile.readint8()
            else:
                match = True
                e = fontfile.readint8()
                f = fontfile.readint8()

        # Read Transformation
        if (flag & SCALE):
            a = d = fontfile.readshort()
            b = c = 0.
        elif (flag & XYSCALE):
            a = fontfile.readshort()
            d = fontfile.readshort()
            b = c = 0.
        elif (flag & TWOBYTWO):
            a = fontfile.readshort()
            b = fontfile.readshort()
            c = fontfile.readshort()
            d = fontfile.readshort()
        else:
            a = d = 1.
            b = c = 0.

        xforms.append(Xform(a, b, c, d, e, f, match))
        glyphidxs.append(subindex)

    glyphs = []
    for idx in glyphidxs:
        glyphs.append(read_glyph(idx, font))

    comp = GlyphComp(glyphs, xforms, charbox)
    return CompoundGlyph(index, comp, font)



class SimpleGlyph:
    ''' Simple Glyph '''
    dfltsize = 12   # Draw <symbols> in this point size

    def __init__(self, index: int, path: GlyphPath, font, char: str=None):
        self.char = char
        self.index = index
        self.path = path
        self.font = font
        basename, _ = os.path.splitext(os.path.basename(self.font.info.name))
        self.id = f'{basename}_{index}'
        self.emscale = self.dfltsize / self.font.info.layout.unitsperem
        
    def _repr_svg_(self):
        return ET.tostring(self.svgxml(), encoding='unicode')

    def place(self, x, y, fontsize):
        ''' Get <use> svg tag translated/scaled to the right position '''
        fntscale = (fontsize/self.dfltsize)
        yshift = self.font.info.layout.ymax * self.emscale * fntscale
        use = ET.Element('use')
        use.attrib['href'] = f'#{self.id}'
        use.attrib['transform'] = f'translate({x} {y-yshift}) scale({fntscale})'
        return use
    
    def advance(self, nextchr=None, kern=True):
        ''' Get advance width in glyph units, including kerning if nextchr is defined '''
        if nextchr:
            nextchr = nextchr.index
        return self.font.advance(self.index, nextchr, kern=kern)
    
    def svgpath(self) -> ET.Element:
        ''' Get svg <path> element for glyph, normalized to 12-point font '''
        height = (self.font.info.layout.ymax - self.font.info.layout.ymin) * self.emscale
        base = height + self.font.info.layout.ymin*self.emscale

        # Split the contours
        xconts = []
        yconts = []
        ctrls = []
        start = 0
        for i in range(len(self.path.ends)):
            stop = self.path.ends[i]+1
            xconts.append(self.path.xvals[start:stop])
            yconts.append(self.path.yvals[start:stop])
            ctrls.append(self.path.ctvals[start:stop])
            start = stop

        path = ''
        for xvals, yvals, ctrl in zip(xconts, yconts, ctrls):
            xx = [x*self.emscale for x in xvals]
            yy = [-y*self.emscale for y in yvals]
            npoints = len(xx)

            path += f'M {xx[0]} {yy[0]} '

            i = 1
            while i < npoints:
                if ctrl[i]:
                    if i == npoints-1:
                        # Last point is control. End point wraps to start point
                        path += f'Q {xx[i]} {yy[i]}, {xx[0]} {yy[0]} '
                        i += 1
                    elif ctrl[i+1]:
                        # Next point is also control.
                        # End of this bezier is implied between two controls
                        xim = (xx[i] + xx[i+1])/2
                        yim = (yy[i] + yy[i+1])/2
                        path += f'Q {xx[i]} {yy[i]}, {xim} {yim} '
                        i += 1
                    else:
                        # Next point is real. It's the endpoint.
                        path += f'Q {xx[i]} {yy[i]}, {xx[i+1]} {yy[i+1]} '
                        i += 2
                else:
                    path += f'L {xx[i]} {yy[i]} '
                    i += 1

            path += 'Z '
        return ET.Element('path', attrib={'d': path})

    def svgsymbol(self) -> ET.Element:
        ''' Get svg <symbol> element for this glyph, scaled to 12-point font '''
        xmin = min(self.path.bbox.xmin * self.emscale, 0)
        xmax = self.path.bbox.xmax
        width = xmax-xmin
        ymax = max(self.font.info.layout.ymax, self.path.bbox.ymax) * self.emscale
        ymin = min(self.font.info.layout.ymin, self.path.bbox.ymin) * self.emscale
        height = ymax - ymin

        sym = ET.Element('symbol')
        sym.attrib['id'] = self.id
        sym.attrib['width'] = str(width)
        sym.attrib['height'] = str(height)
        sym.attrib['viewBox'] = f'{xmin} {-ymax} {width} {height}'
        sym.append(self.svgpath())
        return sym

    def svg(self, fontsize: float=None) -> str:
        ''' Get SVG as string '''
        return ET.tostring(self.svgxml(fontsize), encoding='unicode')

    def svgxml(self, fontsize: float=None) -> ET.Element:
        ''' Standalong SVG '''
        fontsize = fontsize if fontsize else DEFAULT_FONTSIZE
        scale = fontsize / self.font.info.layout.unitsperem

        # Width varies by character, but height is constant for the whole font
        # View should include whole character, even if it goes negative/outside the advwidth
        xmin = min(self.path.bbox.xmin * scale, 0)
        xmax = self.path.bbox.xmax * scale
        ymin = min(self.path.bbox.ymin, self.font.info.layout.ymin) * scale
        
        # ymax can go above font's ymax for extended (ie math) glyphs
        ymax = max(self.path.bbox.ymax, self.font.info.layout.ymax) * scale
        width = xmax - xmin
        height = ymax - ymin
        base = ymax
        
        svg = ET.Element('svg')
        svg.attrib['width'] = str(width)
        svg.attrib['height'] = str(height)
        svg.attrib['xmlns'] = 'http://www.w3.org/2000/svg'
        svg.attrib['viewBox'] = f'{xmin} 0 {width} {height}'
        symbol = self.svgsymbol()
        svg.append(symbol)

        g = ET.SubElement(svg, 'use')
        g.attrib['href'] = f'#{self.id}'
        scale = fontsize/self.dfltsize
        g.attrib['transform'] = f'translate({xmin}, {base-ymax}) scale({scale})'
        return svg

    def test(self) -> 'TestGlyph':
        ''' Get Glyph Test representation showing vertices and borders '''
        return TestGlyph(self)


class CompoundGlyph(SimpleGlyph):
    ''' Compound glyph, made of multiple other Glyphs '''
    def __init__(self, index: int, glyphs: GlyphComp, font, char: str=None):
        self.char = char
        self.index = index
        self.glyphs = glyphs
        path = self._buildcontour()
        super().__init__(index, path, font, char)

    def _buildcontour(self) -> GlyphPath:
        ''' Combine multiple glyphs into one set of contours '''
        xvals: list[int] = []
        yvals: list[int] = []
        ctvals: list[int] = []
        ends: list[int] = []
        for glyph, xform in zip(self.glyphs.glyphs, self.glyphs.xforms):
            if xform.match:
                raise NotImplementedError('Compound glyph match transform')

            m0 = max(abs(xform.a), abs(xform.b))
            n0 = max(abs(xform.c), abs(xform.d))
            m = 2*m0 if abs(abs(xform.a)-abs(xform.c)) <= 33/65536 else m0
            n = 2*n0 if abs(abs(xform.b)-abs(xform.d)) <= 33/65536 else n0
            gx = [m * (xform.a/m * xx + xform.c/m * yy + xform.e) for xx, yy in zip(glyph.path.xvals, glyph.path.yvals)]
            gy = [n * (xform.b/n * xx + xform.d/n * yy + xform.f) for xx, yy in zip(glyph.path.xvals, glyph.path.yvals)]
            ends.extend([end + len(xvals) for end in glyph.path.ends])
            xvals.extend(gx)
            yvals.extend(gy)
            ctvals.extend(glyph.path.ctvals)
        path = GlyphPath(xvals, yvals, ctvals, ends, self.glyphs.bbox)
        return path


class TestGlyph:
    ''' Draw glyph svg with test/debug lines '''
    def __init__(self, glyph: SimpleGlyph):
        self.glyph = glyph

    def _repr_svg_(self):
        ''' Jupyter representation '''
        return self.svg()

    def svg(self, fontsize: float=None) -> str:
        ''' Glyph SVG string '''
        return ET.tostring(self.svgxml(fontsize), encoding='unicode')

    def svgxml(self, fontsize: float=None) -> ET.Element:
        ''' Glyph svg as XML element tree '''
        fontsize = fontsize if fontsize else DEFAULT_FONTSIZE
        svg = self.glyph.svgxml(fontsize)
        scale = fontsize / self.glyph.font.info.layout.unitsperem
        xmin = min(self.glyph.path.bbox.xmin * scale, 0)
        xmax = self.glyph.path.bbox.xmax * scale
        ymin = min(self.glyph.path.bbox.ymin, self.glyph.font.info.layout.ymin) * scale
        ymax = max(self.glyph.path.bbox.ymax, self.glyph.font.info.layout.ymax) * scale
        width = xmax - xmin
        height = ymax - ymin
        base = ymax  # = height - ymin
        # Borders and baselines
        path = ET.SubElement(svg, 'path')
        path.attrib['d'] = f'M {xmin} {base} L {width} {base}'
        path.attrib['stroke'] = 'red'

        ascent = base - self.glyph.font.info.layout.ascent * scale
        descent = base - self.glyph.font.info.layout.descent * scale
        path = ET.SubElement(svg, 'path')
        path.attrib['d'] = f'M {xmin} {ascent} L {width} {ascent}'
        path.attrib['stroke'] = 'gray'
        path.attrib['stroke-dasharray'] = '2 2'
        path = ET.SubElement(svg, 'path')
        path.attrib['d'] = f'M {xmin} {descent} L {width} {descent}'
        path.attrib['stroke'] = 'gray'
        path.attrib['stroke-dasharray'] = '2 2'
        rect = ET.SubElement(svg, 'rect')
        rect.attrib['x'] = '0'
        rect.attrib['y'] = '0'
        rect.attrib['width'] = str(xmax)
        rect.attrib['height'] = str(height)
        rect.attrib['fill'] = 'none'
        rect.attrib['stroke'] = 'blue'
        rect.attrib['stroke-dasharray'] = '2 2'
        circ = ET.SubElement(svg, 'circle')
        circ.attrib['cx'] = '0'
        circ.attrib['cy'] = str(base)
        circ.attrib['r'] = '3'
        circ.attrib['fill'] = 'red'

        # Dots defining <path>
        for x, y, c in zip(self.glyph.path.xvals, self.glyph.path.yvals, self.glyph.path.ctvals):
            circ = ET.SubElement(svg, 'circle')
            circ.attrib['cx'] = str(x * scale)
            circ.attrib['cy'] = str(base - y * scale)
            circ.attrib['r'] = f'{fontsize*scale/3}'
            circ.attrib['fill'] = 'none' if c else 'blue'
            circ.attrib['stroke'] = 'blue'
            circ.attrib['opacity'] = '0.3'
        return svg


class EmptyGlyph(SimpleGlyph):
    ''' Glyph with no contours (like a space) '''
    def __init__(self, index: int, font):
        path = GlyphPath([], [], [], [], BBox(0, 0, 0, 0))
        super().__init__(index, path, font)
