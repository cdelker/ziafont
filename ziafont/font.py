''' Read font file and write glyphs to SVG '''

from __future__ import annotations
from typing import Literal, Sequence, Union, Optional
from collections import namedtuple
from pathlib import Path
import xml.etree.ElementTree as ET

from .fontread import FontReader
from . import gpos
from .cmap import Cmap12, Cmap4
from .glyph import read_glyph, dflt_fontsize, EmptyGlyph, SimpleGlyph, CompoundGlyph
from .fonttypes import GlyphComp, GlyphPath, BBox, AdvanceWidth, Layout, Header, Table, FontInfo, FontNames


DEBUG = False


class Font:
    ''' Class to read/parse a OpenType/TTF and write glyphs to SVG

        Args:
            fname: File name of the font
            svg2: Use SVG Version 2.0. Disable for better compatibility.
    '''
    def __init__(self, fname: Union[str, Path], svg2: bool=True):
        self.fname = fname
        with open(fname, 'rb') as f:
            self.fontfile = FontReader(f.read())
        self.info = self._loadfont()  # Load in all the font metadata
        self.svg2 = svg2

    def _loadfont(self) -> FontInfo:
        ''' Read font metadata '''
        self._readtables()
        header, layout = self._readheader()
        advwidths = self._readwidths(header.numlonghormetrics)
        self._readcmap()
        names = self._readnames()
        info = FontInfo(self.fname, names, header, layout, advwidths)
        
        self.gpos = None
        if 'GPOS' in self.tables:
            self.gpos = gpos.Gpos(self.tables['GPOS'].offset, self.fontfile)

        return info

    def _readtables(self) -> None:
        ''' Read list of tables in the font, and verify checksums '''
        self.fontfile.seek(0)
        scalartype = self.fontfile.readuint32()
        numtables = self.fontfile.readuint16()
        searchrange = self.fontfile.readuint16()
        entryselector = self.fontfile.readuint16()
        rangeshift = self.fontfile.readuint16()   # numtables*16-searchrange

        # Table Directory (table 5)
        self.tables = {}
        for i in range(numtables):
            tag = self.fontfile.read(4).decode()
            self.tables[tag] = Table(checksum=self.fontfile.readuint32(),
                                offset=self.fontfile.readuint32(),
                                length=self.fontfile.readuint32())
        for table in self.tables.keys():
            if table != 'head':
                self._verifychecksum(table)

        if 'glyf' not in self.tables:
            raise ValueError('Unsupported font (no glyf table).')

    def _verifychecksum(self, table: str) -> None:
        ''' Verify checksum of table. Raises ValueError if invalid. '''
        tb = self.tables[table]
        self.fontfile.seek(tb.offset)
        s = 0
        nlongs = (tb.length + 3) // 4
        for i in range(nlongs):
            s = ((s + self.fontfile.readuint32()) % 0x100000000)

        if s != tb.checksum:
            raise ValueError(f'Table {table} checksum {s} != saved checksum {tb.checksum}')

    def _readheader(self) -> tuple[Header, Layout]:
        ''' Read Font "head" and "hhea" tables '''
        version = self.fontfile.readuint32(self.tables['head'].offset)
        revision = self.fontfile.readuint32()
        chksumadjust = self.fontfile.readuint32()
        magic = self.fontfile.readuint32()
        assert magic == 0x5f0f3cf5
        flags = self.fontfile.readuint16()
        unitsperem = self.fontfile.readuint16()
        created = self.fontfile.readdate()
        modified = self.fontfile.readdate()
        xmin = self.fontfile.readint16()
        ymin = self.fontfile.readint16()
        xmax = self.fontfile.readint16()
        ymax = self.fontfile.readint16()
        macstyle = self.fontfile.readuint16()
        lowestrecppem = self.fontfile.readuint16()
        directionhint = self.fontfile.readint16()
        indextolocformat = self.fontfile.readint16()
        glyphdataformat = self.fontfile.readint16()

        # hhea table with other parameters
        _ = self.fontfile.readuint32(self.tables['hhea'].offset)  # version
        ascent = self.fontfile.readint16()
        descent = self.fontfile.readint16()
        linegap = self.fontfile.readint16()
        advwidthmax = self.fontfile.readuint16()
        minleftbearing = self.fontfile.readint16()
        minrightbearing = self.fontfile.readint16()
        xmaxextent = self.fontfile.readint16()
        caretsloperise = self.fontfile.readint16()
        caretsloperun = self.fontfile.readint16()
        caretoffset = self.fontfile.readint16()
        for i in range(4):
            self.fontfile.readint16()  # Skip reserved
        metricformat = self.fontfile.readint16()
        numlonghormetrics = self.fontfile.readuint16()

        advwidth = AdvanceWidth(advwidthmax, minleftbearing)

        layout = Layout(unitsperem, xmin, xmax, ymin, ymax, ascent, descent,
                        advwidth, minleftbearing, minrightbearing)
        header = Header(version, revision, chksumadjust, magic, flags,
                        created, modified, macstyle,
                        lowestrecppem, directionhint, indextolocformat,
                        glyphdataformat, numlonghormetrics)
        return header, layout


    def _readnames(self) -> FontNames:
        ''' Read the "name" table which includes the font name,
            copyright, and other info
        '''
        namefmt = self.fontfile.readuint16(self.tables['name'].offset)
        nameids = [''] * 15  # Empty strings for nameId table

        if namefmt == 0:  # '1' is not supported
            count = self.fontfile.readuint16()
            strofst = self.fontfile.readuint16()
            namerecords = []
            for i in range(count):
                platformId = self.fontfile.readuint16()
                platformSpecificId = self.fontfile.readuint16()
                languageId = self.fontfile.readuint16()
                nameId = self.fontfile.readuint16()
                length = self.fontfile.readuint16()
                offset = self.fontfile.readuint16()
                namerecords.append((platformId, platformSpecificId, languageId,
                                    nameId, length, offset))
            for record in namerecords:
                self.fontfile.seek(self.tables['name'].offset + strofst + record[5])
                name = self.fontfile.read(record[4])
                nameids[record[3]] = name.decode('utf-16be')

        return FontNames(*nameids)
    
    def _readwidths(self, numlonghormetrics: int) -> list[AdvanceWidth]:
        ''' Read `advanceWidth` and `leftsidebearing` from "htmx" table '''
        self.fontfile.seek(self.tables['hmtx'].offset)
        advwidths = []
        for i in range(numlonghormetrics):
            w = self.fontfile.readuint16()
            b = self.fontfile.readint16()
            advwidths.append(AdvanceWidth(w, b))
        return advwidths

    def _readcmap(self) -> None:
        ''' Read "cmap" table and select a cmap for locating glyphs from characters.
            Cmap formats 4 and 12 are supported.
        '''
        platforms = {0: 'unicode', 1: 'macintosh', 3: 'windows'}
        version = self.fontfile.readint16(self.tables['cmap'].offset)
        numtables = self.fontfile.readint16()
        CMapTable = namedtuple('CMapTable', ['platform', 'platformid', 'offset'])
        cmaptables = []
        for i in range(numtables):
            cmaptables.append(CMapTable(
                platforms.get(self.fontfile.readuint16()),
                self.fontfile.readuint16(),
                self.fontfile.readuint32()))

        self.cmap: Optional[Union[Cmap12, Cmap4]] = None  # Active cmap
        self.cmaps: list[Union[Cmap12, Cmap4]] = []
        cmap: Union[Cmap12, Cmap4]
        for ctable in cmaptables:
            cmapformat = self.fontfile.readuint16(self.tables['cmap'].offset + ctable.offset)
            if cmapformat == 4:
                endcodes = []
                startcodes = []
                iddeltas = []
                idrangeoffset = []
                glyphidxarray = []
                length = self.fontfile.readuint16()
                lang = self.fontfile.readuint16()
                segcount = self.fontfile.readuint16() // 2
                searchrange = self.fontfile.readuint16()
                entryselector = self.fontfile.readuint16()
                rangeshift = self.fontfile.readuint16()
                for i in range(segcount):
                    endcodes.append(self.fontfile.readuint16())
                _ = self.fontfile.readuint16()  # reserved pad
                for i in range(segcount):
                    startcodes.append(self.fontfile.readuint16())
                for i in range(segcount):
                    iddeltas.append(self.fontfile.readuint16())
                for i in range(segcount):
                    idrangeoffset.append(self.fontfile.readuint16())

                # Length of glyph array comes from total length of cmap table
                # //2 because len is in bytes, but table glyphidxarray is 16-bit
                glyphtablelen = (length - (self.fontfile.tell() - self.tables['cmap'].offset)) // 2
                for i in range(glyphtablelen):
                    glyphidxarray.append(self.fontfile.readuint16())
                cmap = Cmap4(ctable.platform, ctable.platformid,
                             startcodes, endcodes, idrangeoffset, iddeltas, glyphidxarray)
                if self.cmap is None:
                    self.cmap = cmap
                self.cmaps.append(cmap)

            elif cmapformat == 12:
                _ = self.fontfile.readuint16()
                length = self.fontfile.readuint32()
                lang = self.fontfile.readuint32()
                ngroups = self.fontfile.readuint32()
                starts = []
                ends = []
                glyphstarts = []
                for i in range(ngroups):
                    starts.append(self.fontfile.readuint32())
                    ends.append(self.fontfile.readuint32())
                    glyphstarts.append(self.fontfile.readuint32())
                cmap = Cmap12(ctable.platform, ctable.platformid, starts, ends, glyphstarts)
                if self.cmap is None or isinstance(self.cmap, Cmap4):
                    self.cmap = cmap
                self.cmaps.append(cmap)

        if len(self.cmaps) == 0:
            raise ValueError('No suitable cmap table found in font.')

    def usecmap(self, cmapidx: int) -> None:
        ''' Select cmap table by index. Only supported tables are included. '''
        self.cmap = self.cmaps[cmapidx]

    def glyphindex(self, char: str) -> int:
        ''' Get index of character glyph '''
        return self.cmap.glyphid(char)  # type: ignore

    def _glyphoffset(self, index: int) -> Optional[int]:
        ''' Get offset (from beginning of file) of glyph,
            Return None if no glyph (empty/space) at this index.
        '''
        if self.info.header.indextolocformat == 1:
            offset = self.fontfile.readuint32(self.tables['loca'].offset + index * 4)
            nextofst = self.fontfile.readuint32()
        else:
            offset = self.fontfile.readuint16(self.tables['loca'].offset + index * 2) * 2
            nextofst = self.fontfile.readuint32()

        if offset == nextofst:
            # Empty glyphs (ie space) have no length.
            return None
        else:
            return offset + self.tables['glyf'].offset

    def glyph(self, char: str) -> SimpleGlyph:
        ''' Get the Glyph for the character '''
        index = self.glyphindex(char)        # Glyph Number
        return self.glyph_fromid(index)

    def glyph_fromid(self, glyphid: int) -> Union[SimpleGlyph, CompoundGlyph]:
        ''' Read a glyph from the "glyf" table

            Args:
                glyphid: Glyph index used to find glyph data
        '''
        return read_glyph(glyphid, self)

    def advance(self, glyph1: int, glyph2: int=None, kern: bool=True):
        ''' Get advance width in font units, including kerning adjustment if glyph2 is defined '''
        try:
            adv = self.info.advwidths[glyph1].width
        except IndexError:
            adv = self.info.header.advwidthmax
        
        if kern and glyph2 and self.gpos:
            # Only getting x-advance for first glyph.
            adv += self.gpos.kern(glyph1, glyph2)[0].get('xadvance', 0)
        return adv
    
    def _buildstring(self, s: str, fontsize: float=None, linespacing: float=1,
                     halign: str='left', kern=True) -> tuple[ET.Element, list[ET.Element], float, float]:
        ''' Create symbols and svg word in a <g> group tag, for placing in an svg '''
        fontsize = fontsize if fontsize else dflt_fontsize()
        scale = fontsize / self.info.layout.unitsperem
        fontheight = (self.info.layout.ymax - self.info.layout.ymin) * scale
        lineheight = fontheight * linespacing

        lines = s.splitlines()
        yvals = [i*lineheight for i in range(len(lines))]  # valign == 'base'
        height = yvals[-1] + fontheight

        # Generate symbols and calculate x positions using left alignment
        symbols: list[ET.Element] = []  # <symbol> elements
        linewidths: list[float] = []
        allglyphs = []  # (glyph, x) where x is left aligned
        for line in lines:
            lineglyphs = []
            glyphs = [self.glyph(c) for c in line]
            x = 0
            for gidx, glyph in enumerate(glyphs):
                if glyph.id not in [s.attrib['id'] for s in symbols]:
                    symbols.append(glyph.svgsymbol())
                lineglyphs.append((glyph, x))
                nextglyph = glyphs[gidx+1] if gidx+1 < len(glyphs) else None
                xadvance = glyph.advance(nextglyph, kern=kern)
                x += (xadvance - min(0, glyph.path.bbox.xmin)) * scale

            if glyph.path.bbox.xmax > xadvance:
                # Make a bit wider to grab right edge that extends beyond advance width
                x += (glyph.path.bbox.xmax - xadvance) * scale
            linewidths.append(x)
            allglyphs.append(lineglyphs)

        # Place the glyphs based on halign
        word = ET.Element('g')
        word.attrib['word'] = s  # Just an identifier for debugging
        totwidth = max(linewidths)
        for lineidx, (lineglyphs, linewidth) in enumerate(zip(allglyphs, linewidths)):
            if halign == 'center':
                leftshift = (totwidth - linewidth)/2
            elif halign == 'right':
                leftshift = totwidth - linewidth
            else:  # halign = 'left'
                leftshift = 0
            for glyph, x in lineglyphs:
                word.append(glyph.place(x+leftshift, yvals[lineidx], fontsize))
        if not self.svg2:
            symbols = []
        return word, symbols, totwidth, height

    def strsize(self, s: str, fontsize: float=12, linespacing: float=1) -> tuple[float, float]:
        ''' Calculate width and height (including ascent/descent) of string '''
        _, _, width, height = self._buildstring(s, fontsize=fontsize, linespacing=linespacing)
        return width, height

    def str2svg(self, s: str, fontsize: float=None, linespacing: float=1,
                halign: Literal['left', 'center', 'right']='left',
                valign: Literal['base', 'center', 'top']='base',
                canvas: Union[ET.Element, SVGdraw]=None,
                xy: Sequence[float]=(0,0),
               kern=True,
               ) -> SVGdraw:
        ''' Draw text to SVG

            Args:
                s: String to draw
                fontsize: Size of font in points
                linespacing: Fraction of font height between lines
                halign: Horizontal alignment
                valign: Vertical alignment (when placed on existing canvas)
                canvas: Existing SVG to draw on
                xy: Position to draw on existing canvas

            Returns:
                svg: SVG drawing object containing svg+xml element tree
        '''
        fontsize = fontsize if fontsize else dflt_fontsize()

        word, symbols, width, height = self._buildstring(
            s, fontsize, linespacing, halign=halign, kern=kern)

        if isinstance(canvas, SVGdraw):
            svg = canvas.svgxml()
        elif canvas is not None:
            svg = canvas

        xyorig = xy
        if canvas is not None:
            # Adjust vertical alignment
            yofst = {'base': -linespacing*fontsize,
                     'bottom': -height,
                     'top': 0,
                     'center': -height/2}.get(valign, 0)
            xofst = {'center': -width/2,
                     'right': -width}.get(halign, 0)
            xy = xy[0] + xofst, xy[1] + yofst

            # Expand SVG viewbox to fit
            xmin, ymin, w, h = [float(f) for f in svg.attrib['viewBox'].split()]
            if xmin + w < xy[0] + width:
                w = xy[0] + width - xmin
            if ymin + h < xy[1] + height:
                h = xy[1] + height - ymin
            if xmin > xy[0]:
                w = xmin + w - xy[0]
                xmin = xy[0]
            if ymin > xy[1]:
                h = ymin + h - xy[1]
                ymin = xy[1]
            svg.attrib['width'] = str(w)
            svg.attrib['height'] = str(h)
            svg.attrib['viewBox'] = f'{xmin} {ymin} {w} {h}'

        else:  # canvas is None, make a new SVG
            base = self.info.layout.ymax * fontsize / self.info.layout.unitsperem
            svg = ET.Element('svg')
            svg.attrib['width'] = str(width)
            svg.attrib['height'] = str(height)
            svg.attrib['xmlns'] = 'http://www.w3.org/2000/svg'
            if not self.svg2:
                svg.attrib['xmlns:xlink'] = 'http://www.w3.org/1999/xlink'
            svg.attrib['viewBox'] = f'0 {-base} {width} {height}'

        # Get existing symbol/glyphs, add ones not there yet
        if self.svg2:
            existingsymbols = svg.findall('symbol')
            symids = [sym.attrib.get('id') for sym in existingsymbols]
            for sym in symbols:
                if sym not in symids:
                    svg.append(sym)
        if xy != (0, 0):
            word.attrib['transform'] = f'translate({xy[0]} {xy[1]+linespacing*fontsize})'
        
        svg.append(word)

        if DEBUG:  # Test viewbox
            rect = ET.SubElement(svg, 'rect')
            rect.attrib['x'] = f'{xy[0]}'
            rect.attrib['y'] = f'{xy[1]}'
            rect.attrib['width'] = str(width)
            rect.attrib['height'] = str(height)
            rect.attrib['fill'] = 'none'
            rect.attrib['stroke'] = 'red'
            circ = ET.SubElement(svg, 'circle')
            circ.attrib['cx'] = f'{xyorig[0]}'
            circ.attrib['cy'] = f'{xyorig[1]}'
            circ.attrib['r'] = '3'
            circ.attrib['fill'] = 'red'
            circ.attrib['stroke'] = 'red'
        return SVGdraw(svg)


class SVGdraw:
    ''' Convert XML Element to SVG text with Jupyter representer.

        Args:
            svgxml: Element tree containing SVG elements
    '''
    def __init__(self, svgxml: ET.Element):
        self._svgxml = svgxml
        x, y, w, h = svgxml.attrib['viewBox'].split()
        if DEBUG:  # Debug viewbox
            rect = ET.SubElement(self._svgxml, 'rect')
            rect.attrib['x'] = f'{x}'
            rect.attrib['y'] = f'{y}'
            rect.attrib['width'] = str(w)
            rect.attrib['height'] = str(h)
            rect.attrib['fill'] = 'none'
            rect.attrib['stroke'] = 'red'
            circ = ET.SubElement(self._svgxml, 'circle')
            circ.attrib['cx'] = '0'
            circ.attrib['cy'] = '0'
            circ.attrib['r'] = '5'
            circ.attrib['fill'] = 'red'
            circ.attrib['stroke'] = 'red'

    def svgxml(self) -> ET.Element:
        ''' Get SVG XML element '''
        return self._svgxml

    def svg(self) -> str:
        ''' Get SVG string '''
        return ET.tostring(self._svgxml, encoding='unicode')

    def _repr_svg_(self):
        ''' Jupyter representer '''
        return self.svg()
