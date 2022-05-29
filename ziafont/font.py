''' Read font file and write glyphs to SVG '''

from __future__ import annotations
from typing import Literal, Sequence, Union, Optional, Dict
import sys
import os
from pathlib import Path
from collections import namedtuple
import importlib.resources as pkg_resources
import xml.etree.ElementTree as ET

from .fontread import FontReader
from . import gpos
from .cmap import Cmap12, Cmap4
from .glyph import read_glyph, dflt_fontsize, fmt, SimpleGlyph, CompoundGlyph
from .fonttypes import AdvanceWidth, Layout, Header, Table, FontInfo, FontNames


DEBUG = False

fontindex = None

Symbols = namedtuple('Symbols', ['word', 'symbols', 'width', 'ymin', 'ymax'])


class Font:
    ''' Class to read/parse a OpenType/TTF and write glyphs to SVG

        Args:
            name: File name of the font
            style: Font style such as "bold" or "italic", used when searching
                system paths for a font file
            svg2: Use SVG Version 2.0. Disable for better compatibility.
    '''
    def __init__(self, name: Union[str, Path]=None, style: str='regular', svg2: bool=True):
        self.fname = None
        if name and Path(name).exists():
            self.fname = Path(name)
        elif name:
            self.fname = findfont(name, style)

        if self.fname is None:
            with pkg_resources.path('ziafont.fonts', 'DejaVuSans.ttf') as p:
                self.fname = p

        with open(self.fname, 'rb') as f:
            self.fontfile = FontReader(f.read())
        self.info = self._loadfont()  # Load in all the font metadata
        self.svg2 = svg2
        self._glyphs: Dict[int, Union[SimpleGlyph, CompoundGlyph]] = {}
        self._glyphids: Dict[str, int] = {}

    def _loadfont(self) -> FontInfo:
        ''' Read font metadata '''
        self._readtables()
        header, layout = self._readheader()
        self.advwidths = self._readwidths(header.numlonghormetrics)
        self._readcmap()
        names = self._readnames()
        info = FontInfo(self.fname, names, header, layout)

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

        if 'glyf' not in self.tables:
            raise ValueError('Unsupported font (no glyf table).')

    def verifychecksum(self):
        ''' Verify checksum of all font tables. Raises ValueError if invalid '''
        for table in self.tables.keys():
            if table != 'head':
                self._verifychecksum(table)

    def _verifychecksum(self, table: str) -> None:
        ''' Verify checksum of table. Raises ValueError if invalid. '''
        tb = self.tables[table]
        self.fontfile.seek(tb.offset)
        s = 0
        nlongs = (tb.length + 3) // 4
        s = sum(self.fontfile.readuint32() for i in range(nlongs)) & 0xffffffff
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
                if record[3] < 16:
                    if record[0] in [0, 3]:  # Microsoft and Unicode formats
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
        gid = self._glyphids.get(char)
        if gid is None:
            gid = self.cmap.glyphid(char)  # type: ignore
            self._glyphids[char] = gid
        return gid

    def _glyphoffset(self, index: int) -> Optional[int]:
        ''' Get offset (from beginning of file) of glyph,
            Return None if no glyph (empty/space) at this index.
        '''
        if self.info.header.indextolocformat == 1:
            offset = self.fontfile.readuint32(self.tables['loca'].offset + index * 4)
            nextofst = self.fontfile.readuint32()
        else:
            offset = self.fontfile.readuint16(self.tables['loca'].offset + index * 2) * 2
            nextofst = self.fontfile.readuint16() * 2

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
        glyph = self._glyphs.get(glyphid)
        if glyph is None:
            glyph = read_glyph(glyphid, self)
            self._glyphs[glyphid] = glyph
        return glyph

    def advance(self, glyph1: int, glyph2: int=None, kern: bool=True):
        ''' Get advance width in font units, including kerning adjustment if glyph2 is defined '''
        try:
            adv = self.advwidths[glyph1].width
        except IndexError:
            adv = self.info.layout.advwidthmax.width

        if kern and glyph2 and self.gpos:
            # Only getting x-advance for first glyph.
            adv += self.gpos.kern(glyph1, glyph2)[0].get('xadvance', 0)
        return adv

    def getsize(self, s) -> tuple[float, float]:
        ''' Calculate width and height (including ascent/descent) of string '''
        txt = Text(s, self)
        return txt.getsize()

    def str2svg(self, s: str, fontsize: float=None, linespacing: float=1,
                halign: Literal['left', 'center', 'right']='left',
                valign: Literal['base', 'center', 'top']='base',
                canvas: ET.Element=None,
                xy: Sequence[float]=(0, 0),
                kern=True):
        ''' Convert a string to SVG

            Args:
                s: String to convert.
                fontsize: Font size in points
                linespacing: Space between lines
                halign: Horizontal Alignment
                valign: Vertical Alignment
                canvas: SVG XML element to draw on
                xy: Position to draw on canvas
                kern: Use font kerning adjustment
        '''
        txt = Text(s, self, fontsize, linespacing, halign, valign, kern=kern, svg2=self.svg2)
        if canvas is not None:
            txt.drawon(canvas, xy[0], xy[1])
        return txt


class Text:
    ''' Convert XML Element to SVG text with Jupyter representer.

        Args:
            s: String to draw
            font: Font name or ziafont.Font to use
            size: Font size in points
            linespacing: Spacing between lines
            halign: Horizontal Alignment
            valign: Vertical Alignment
            kern: Use kerning adjustment
            svg2: Use SVG Version 2.0. Disable for better compatibility.
    '''
    def __init__(self, s: str,  font: Union[str, Font]=None,
                 size: float=None, linespacing: float=1,
                 halign: Literal['left', 'center', 'right']='left',
                 valign: Literal['base', 'center', 'top']='base',
                 kern: bool=True,
                 svg2: bool=True):
        self.str = s
        self.halign = halign
        self.valign = valign
        self.size = size if size else dflt_fontsize()
        self.linespacing = linespacing
        self.svg2 = svg2
        self.kern = kern
        if font is None or isinstance(font, str):
            self.font = Font(font)
        else:
            self.font = font
        self._symbols = self._buildstring()

    def svgxml(self) -> ET.Element:
        ''' Get SVG XML element '''
        svg = ET.Element('svg')
        svg.attrib['xmlns'] = 'http://www.w3.org/2000/svg'
        if self.svg2:
            svg.attrib['xmlns:xlink'] = 'http://www.w3.org/1999/xlink'
        ret, (xmin, xmax, ymin, ymax) = self._drawon(svg)
        w = xmax-xmin
        h = ymax-ymin
        svg.attrib['width'] = fmt(w)
        svg.attrib['height'] = fmt(h)
        svg.attrib['viewBox'] = f'{fmt(xmin)} {fmt(ymin)} {fmt(w)} {fmt(h)}'
        return ret

    def svg(self) -> str:
        ''' Get SVG string '''
        return ET.tostring(self.svgxml(), encoding='unicode')

    def _repr_svg_(self):
        ''' Jupyter representer '''
        return self.svg()

    def drawon(self, svg: ET.Element, x: float=0, y: float=0):
        ''' Draw text on the SVG '''
        svg, _ = self._drawon(svg, x, y)
        return svg

    def _drawon(self, svg: ET.Element, x: float=0, y: float=0):
        ''' Draw text on the SVG '''
        word, symbols, width, ymin, ymax = self._symbols
        height = ymax-ymin
        xyorig = x, y
        # Adjust vertical alignment
        yofst = {'base': 0,
                 'bottom': -ymax,
                 'top': -ymin,
                 'center': -height/2-ymin}.get(self.valign, 0)
        xofst = {'center': -width/2,
                 'right': -width}.get(self.halign, 0)
        xy = x + xofst, y + yofst

        # Get existing symbol/glyphs, add ones not there yet
        if self.svg2:
            existingsymbols = svg.findall('symbol')
            symids = [sym.attrib.get('id') for sym in existingsymbols]
            for sym in symbols:
                if sym not in symids:
                    svg.append(sym)
        if xy != (0, 0):
            word.attrib['transform'] = f'translate({fmt(xy[0])} {fmt(xy[1])})'

        svg.append(word)

        if DEBUG:  # Test viewbox
            rect = ET.SubElement(svg, 'rect')
            rect.attrib['x'] = fmt(xy[0])
            rect.attrib['y'] = fmt(xy[1]+ymin)
            rect.attrib['width'] = fmt(width)
            rect.attrib['height'] = fmt(height)
            rect.attrib['fill'] = 'none'
            rect.attrib['stroke'] = 'red'
            circ = ET.SubElement(svg, 'circle')
            circ.attrib['cx'] = f'{fmt(xyorig[0])}'
            circ.attrib['cy'] = f'{fmt(xyorig[1])}'
            circ.attrib['r'] = '3'
            circ.attrib['fill'] = 'red'
            circ.attrib['stroke'] = 'red'
        return svg, (xy[0], xy[0]+width, ymin, ymax)

    def _buildstring(self) -> Symbols:
        ''' Create symbols and svg word in a <g> group tag, for placing in an svg '''
        scale = self.size / self.font.info.layout.unitsperem
        lineheight = self.size * self.linespacing
        lines = self.str.splitlines()
        yvals = [i*lineheight for i in range(len(lines))]  # valign == 'base'

        # Generate symbols and calculate x positions using left alignment
        symbols: list[ET.Element] = []  # <symbol> elements
        linewidths: list[float] = []
        allglyphs = []  # (glyph, x) where x is left aligned
        for lineidx, line in enumerate(lines):
            lineglyphs = []
            glyphs = [self.font.glyph(c) for c in line]
            x = 0
            for gidx, glyph in enumerate(glyphs):
                if glyph.id not in [s.attrib['id'] for s in symbols]:
                    symbols.append(glyph.svgsymbol())
                lineglyphs.append((glyph, x))
                nextglyph = glyphs[gidx+1] if gidx+1 < len(glyphs) else None
                xadvance = glyph.advance(nextglyph, kern=self.kern)
                x += (xadvance - min(0, glyph.path.bbox.xmin)) * scale

            if glyph.path.bbox.xmax > xadvance:
                # Make a bit wider to grab right edge that extends beyond advance width
                x += (glyph.path.bbox.xmax - xadvance) * scale
            linewidths.append(x)
            allglyphs.append(lineglyphs)

        # Place the glyphs based on halign
        word = ET.Element('g')
        word.attrib['word'] = self.str  # Just an identifier for debugging
        totwidth = max(linewidths)
        for lineidx, (lineglyphs, linewidth) in enumerate(zip(allglyphs, linewidths)):
            if self.halign == 'center':
                leftshift = (totwidth - linewidth)/2
            elif self.halign == 'right':
                leftshift = totwidth - linewidth
            else:  # halign = 'left'
                leftshift = 0
            for glyph, x in lineglyphs:
                word.append(glyph.place(x+leftshift, yvals[lineidx], self.size))

        ymin = yvals[0] - self.font.info.layout.ascent*scale
        ymax = yvals[-1] - self.font.info.layout.descent*scale

        if not self.svg2:
            symbols = []
        return Symbols(word, symbols, totwidth, ymin, ymax)

    def getsize(self) -> tuple[float, float]:
        ''' Calculate width and height (including ascent/descent) of string '''
        return self._symbols.width, self._symbols.ymax-self._symbols.ymin

    def getyofst(self) -> float:
        ''' Y-shift from bottom of bbox to 0 '''
        return -self._symbols.ymax


def _build_fontlist():
    ''' Generate list of system fonts locations and their names '''
    if sys.platform.startswith('win'):
        paths = [Path(r'C:\Windows\Fonts'),
                 Path(os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Fonts'))]
    elif sys.platform.startswith('darwin'):
        paths = [Path().home() / 'Library/Fonts',
                 Path('/Library/Fonts/'),
                 Path('/System/Library/Fonts')]
    else:
        paths = [Path('/usr/share/fonts/'),
                 Path('/usr/local/share/fonts/'),
                 Path().home() / '.fonts',
                 Path().home() / '.local/share/fonts']

    fontlist = []
    for p in paths:
        fontlist.extend(p.rglob('*.ttf'))
        fontlist.extend(p.rglob('*.otf'))

    findex = {}
    for fname in fontlist:
        try:
            f = Font(fname)
        except ValueError:
            continue  # Unsupported Font
        family = f.info.names.family.lower()
        subfamily = f.info.names.subfamily.lower()
        subfamily = subfamily.replace('book', 'regular').replace('normal', 'regular')
        subfamily = subfamily.replace('italique', 'italic').replace('gras', 'bold')
        findex[(family, subfamily)] = fname
    return findex


def findfont(name, style='Regular'):
    ''' Find a font file by name '''
    if Path(name).exists():
        return Path(name)

    global fontindex
    if fontindex is None:
        fontindex = _build_fontlist()
    return fontindex.get((name.lower(), style.lower()), None)
