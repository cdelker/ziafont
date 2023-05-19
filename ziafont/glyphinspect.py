''' Inspect and debug glyphs '''

from __future__ import annotations
from typing import TYPE_CHECKING
import xml.etree.ElementTree as ET

from .svgpath import fmt

if TYPE_CHECKING:
    from .glyph import SimpleGlyph


class InspectGlyph:
    ''' Draw glyph svg with test/debug lines '''
    def __init__(self, glyph: SimpleGlyph, pxwidth: float = 400, pxheight: float = 400):
        self.glyph = glyph
        self.font = self.glyph.font
        self.pxwidth = pxwidth
        self.pxheight = pxheight

    def _repr_svg_(self):
        ''' Jupyter representation '''
        return self.svg()

    def svg(self) -> str:
        ''' Glyph SVG string '''
        return ET.tostring(self.svgxml(), encoding='unicode')

    def svgxml(self) -> ET.Element:
        ''' Glyph svg as XML element tree '''
        # Draw glyph at 1:1 scale in glyph units
        height = self.font.info.layout.ymax - self.font.info.layout.ymin
        width = height * self.pxwidth/self.pxheight

        # vertical positions
        ymargin = height / 20
        height *= 1.1
        bot = height - ymargin
        baseline = height + self.font.info.layout.ymin - ymargin
        descend = baseline - self.font.info.layout.descent
        ascend = baseline - self.font.info.layout.ascent
        top = baseline - self.font.info.layout.ymax

        # horizontal positions
        xadvance = self.glyph.advance()
        x0 = (width - xadvance)/2
        x1 = x0 + xadvance

        # drawing constants
        radius = fmt(width/150)
        txtmargin = fmt(25)
        txtsize = fmt(width/40)
        tick = width/50

        svg = ET.Element('svg')
        svg.set('xmlns', 'http://www.w3.org/2000/svg')
        svg.set('viewBox', f'0 0 {fmt(width)} {fmt(height)}')
        svg.set('width', fmt(self.pxwidth))
        svg.set('height', fmt(self.pxheight))

        # Height lines
        def hline(y, name, color):
            path = ET.SubElement(svg, 'path')
            path.attrib['d'] = f'M 0 {fmt(y)} l {fmt(width)} 0'
            path.attrib['stroke'] = color
            path.set('stroke-width', '1px')
            path.set('opacity', '.5')
            path.set('vector-effect', 'non-scaling-stroke')
            text = ET.SubElement(svg, 'text')
            text.set('x', fmt(txtmargin))
            text.set('y', fmt(y-20))
            text.set('font-size', txtsize)
            text.text = name
        hline(baseline, 'baseline', 'red')
        hline(bot, 'ymin', 'gray')
        hline(descend, 'descend', 'gray')
        hline(ascend, 'ascend', 'gray')
        hline(top, 'ymax', 'gray')

        # Vertical lines
        def vline(x, color):
            path = ET.SubElement(svg, 'path')
            path.attrib['d'] = f'M {fmt(x)} 0 l 0 {fmt(height)}'
            path.attrib['stroke'] = color
            path.set('stroke-width', '1px')
            path.set('opacity', '.5')
            path.set('vector-effect', 'non-scaling-stroke')
        vline(x0, 'gray')
        vline(x1, 'gray')

        # Ticks
        z = ET.SubElement(svg, 'path')
        z.set('d', (f'M {fmt(x0-tick)} {fmt(baseline)} '
                    f'L {fmt(x0)} {fmt(baseline)} {fmt(x0)} {fmt(baseline+tick)}'))
        z.set('stroke', '#444444')
        z.set('stroke-width', '4px')
        z.set('fill', 'none')
        z.set('vector-effect', 'non-scaling-stroke')
        z = ET.SubElement(svg, 'path')
        z.set('d', (f'M {fmt(x1+tick)} {fmt(baseline)} '
                    f'L {fmt(x1)} {fmt(baseline)} {fmt(x1)} {fmt(baseline+tick)}'))
        z.set('stroke', '#444444')
        z.set('stroke-width', '4px')
        z.set('fill', 'none')
        z.set('vector-effect', 'non-scaling-stroke')
        text = ET.SubElement(svg, 'text')
        text.set('x', fmt(x0))
        text.set('y', fmt(baseline+tick+100))
        text.set('font-size', txtsize)
        text.set('text-anchor', 'middle')
        text.set('alignment-baseline', 'top')
        text.text = '0'
        text = ET.SubElement(svg, 'text')
        text.set('x', fmt(x1))
        text.set('y', fmt(baseline+tick+100))
        text.set('font-size', txtsize)
        text.set('text-anchor', 'middle')
        text.set('alignment-baseline', 'top')
        text.text = str(int(xadvance))

        # Glyph Outline
        g = self.glyph.svgpath(x0=x0, y0=baseline,
                               scale_factor=1/self.glyph._points_per_unit)  # type: ignore
        if g is not None:
            g.set('fill', 'lightgray')
            g.set('stroke', 'black')
            g.set('stroke-width', '2px')
            g.set('vector-effect', 'non-scaling-stroke')
            svg.append(g)

        for op in self.glyph.operators:
            points, ctrls = op.points()
            for p, c in zip(points, ctrls):
                circ = ET.SubElement(svg, 'circle')
                circ.set('cx', fmt(x0 + p.x))
                circ.set('cy', fmt(baseline-p.y))
                circ.set('r', radius)
                circ.set('fill', '#393ee3' if c else '#d1211b')
                circ.set('stroke-width', '1px')
                circ.set('vector-effect', 'non-scaling-stroke')
        return svg


class DescribeGlyph:
    ''' Table of Glyph information '''
    def __init__(self, glyph: SimpleGlyph):
        self.glyph = glyph

    def __repr__(self):
        chstr = ', '.join(list(self.glyph.char))
        ordstr = ', '.join(format(ord(k), '04X') for k in list(self.glyph.char))
        r = f'Index: {self.glyph.index}\n'
        r += f'Unicode: {ordstr}\n'
        r += f'Character: {chstr}\n'
        r += f'xmin: {self.glyph.bbox.xmin}\n'
        r += f'xmax: {self.glyph.bbox.xmax}\n'
        r += f'ymin: {self.glyph.bbox.ymin}\n'
        r += f'ymax: {self.glyph.bbox.ymax}\n'
        r += f'Advance: {self.glyph.advance()}\n'
        if hasattr(self.glyph, 'glyphs'):  # Compound
            comps = self.glyph.glyphs.glyphs
            ids = ', '.join(str(c.index) for c in comps)
            r += f'Component ids: {ids}\n'
        return r

    def _repr_html_(self):
        ''' Jupyter representation, HTML table '''
        return self.describe()

    def describe(self):
        ''' HTML table with glyph parameters '''
        chstr = ', '.join(list(self.glyph.char))
        ordstr = ', '.join(format(ord(k), '04X') for k in list(self.glyph.char))
        comprow = ''
        if hasattr(self.glyph, 'glyphs'):  # Compound
            comps = self.glyph.glyphs.glyphs
            ids = ', '.join(str(c.index) for c in comps)
            comprow = f'<tr><td>Component ids</td><td>{ids}</td></tr>'

        h = f'''
        <table>
        <tr><td>Index</td><td>{self.glyph.index}</td></tr>
        <tr><td>Unicode</td><td>{ordstr}</td></tr>
        <tr><td>Character</td><td>{chstr}</td></tr>
        <tr><td>xmin</td><td>{self.glyph.bbox.xmin}</td></tr>
        <tr><td>xmax</td><td>{self.glyph.bbox.xmax}</td></tr>
        <tr><td>ymin</td><td>{self.glyph.bbox.ymin}</td></tr>
        <tr><td>ymax</td><td>{self.glyph.bbox.ymax}</td></tr>
        <tr><td>Advance</td><td>{self.glyph.advance()}</td></tr>
        {comprow}
        </table>
        '''
        return h


class ShowGlyphs:
    ''' Show all glyphs in the font '''
    def __init__(self, font, size: float = 36, pxwidth: float = 800):
        self.font = font
        self.size = size
        self.pxwidth = pxwidth
        self.linespacing = 1.15

    def _repr_svg_(self):
        ''' Jupyter representation '''
        return self.svg()

    def svg(self) -> str:
        ''' Glyph SVG string '''
        return ET.tostring(self.svgxml(), encoding='unicode')

    def svgxml(self) -> ET.Element:
        lineheight = self.size * self.linespacing
        scale = self.size / self.font.info.layout.unitsperem

        svg = ET.Element('svg')
        svg.set('xmlns', 'http://www.w3.org/2000/svg')
        svg.set('width', fmt(self.pxwidth))

        x = 0
        y = lineheight
        for i in range(self.font.info.header.numglyphs):
            glyph = self.font.glyph_fromid(i)
            if x + glyph.advance() * scale > self.pxwidth:
                y += lineheight
                x = 0
            if x == 0 and glyph.bbox.xmin < 0:
                x = glyph.bbox.xmin * scale
            g = glyph.svgpath(x0=x, y0=y, scale_factor=self.size/glyph.DFLT_SIZE_PT)
            if g is not None:
                svg.append(g)
            x += glyph.advance() * scale

        height = y + lineheight/2
        svg.set('viewBox', f'0 0 {fmt(self.pxwidth)} {fmt(height)}')
        svg.set('height', fmt(height))
        return svg


class ShowLookup4:
    ''' Show items in Lookup Table type 4 '''
    def __init__(self, lookup, font, size: float=36, pxwidth: int=400):
        self.lookup = lookup
        self.font = font
        self.size = size
        self.pxwidth = pxwidth
        self.linespacing = 1.25

    def _repr_svg_(self):
        ''' Jupyter representation '''
        return self.svg()

    def svg(self) -> str:
        ''' Glyph SVG string '''
        return ET.tostring(self.svgxml(), encoding='unicode')

    def svgxml(self) -> ET.Element:
        ''' Get SVG as XML tree '''
        lineheight = self.size * self.linespacing
        scale = self.size / self.font.info.layout.unitsperem

        svg = ET.Element('svg')
        svg.set('xmlns', 'http://www.w3.org/2000/svg')
        svg.set('width', fmt(self.pxwidth))

        y = lineheight
        for subtable in self.lookup.subtables:
            assert subtable.covtable.format == 1
            for covidx, startglyph in enumerate(subtable.covtable.glyphs):
                ligset = subtable.ligsets[covidx]
                for nextglyphs, repl in ligset.items():
                    origglyphs = [startglyph] + list(nextglyphs)

                    x = 0
                    for gid in origglyphs:
                        glyph = self.font.glyph_fromid(gid)
                        g = glyph.svgpath(x0=x, y0=y, scale_factor=self.size/glyph.DFLT_SIZE_PT)
                        if g is not None:
                            svg.append(g)
                        x += glyph.advance() * scale
                    x += 20
                    glyph = self.font.glyph('-')
                    svg.append(glyph.svgpath(x0=x, y0=y,
                                             scale_factor=self.size/glyph.DFLT_SIZE_PT))
                    x += glyph.advance() * scale
                    x += 20

                    glyph = self.font.glyph_fromid(repl)
                    g = glyph.svgpath(x0=x, y0=y, scale_factor=self.size/glyph.DFLT_SIZE_PT)
                    g.set('fill', 'red')
                    svg.append(g)
                    y += lineheight

        svg.set('viewBox', f'0 0 {fmt(self.pxwidth)} {fmt(y + lineheight/2)}')
        svg.set('height', fmt(y + lineheight/2))
        return svg
