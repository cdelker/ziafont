''' Read font file and write glyphs to SVG '''

from __future__ import annotations
from typing import Literal, Union, Optional, Sequence, Dict
import math
from pathlib import Path
from collections import namedtuple
import importlib.resources as pkg_resources
import xml.etree.ElementTree as ET

from .config import config
from .fontread import FontReader
from . import gpos
from . import gsub
from .cmap import Cmap12, Cmap4
from .glyph import SimpleGlyph, CompoundGlyph
from .glyphcff import read_glyph_cff, CFF
from .glyphglyf import read_glyph_glyf
from .glyphinspect import ShowGlyphs
from .fonttypes import (AdvanceWidth, Layout, Header, Table,
                        FontInfo, FontNames, Symbols, FontFeatures)
from .svgpath import fmt


class Font:
    ''' Class to read/parse a OpenType/TTF and write glyphs to SVG

        Args:
            name: File name of the font. Defaults to DejaVuSans.
    '''
    def __init__(self, name: Optional[Union[str, Path]] = None):
        self.fname = None
        if name:
            if Path(name).exists():
                self.fname = Path(name)
            else:
                raise FileNotFoundError(f'Font {name} not found.')
        else:
            with pkg_resources.path('ziafont.fonts', 'DejaVuSans.ttf') as p:
                self.fname = p

        with open(self.fname, 'rb') as f:
            self.fontfile = FontReader(f.read())

        self.tables: dict[str, Table] = {}
        self.features = FontFeatures()
        self.info = self._loadfont()  # Load in all the font metadata
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

        self.gsub = None
        if 'GSUB' in self.tables:
            self.gsub = gsub.Gsub(self.tables['GSUB'].offset, self.fontfile)

        self.cffdata: Optional[CFF] = None
        if 'CFF ' in self.tables:
            self.cffdata = CFF(self)

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

        if 'glyf' not in self.tables and 'CFF ' not in self.tables:
            raise ValueError('Unsupported font (no glyf or CFF table).')

    def verifychecksum(self) -> None:
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

        self.fontfile.readuint32(self.tables['maxp'].offset)
        numglyphs = self.fontfile.readuint16()

        layout = Layout(unitsperem, xmin, xmax, ymin, ymax, ascent, descent,
                        advwidth, minleftbearing, minrightbearing)
        header = Header(version, revision, chksumadjust, magic, flags,
                        created, modified, macstyle,
                        lowestrecppem, directionhint, indextolocformat,
                        glyphdataformat, numlonghormetrics, numglyphs)
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
            ctable_ofst = self.tables['cmap'].offset + ctable.offset
            cmapformat = self.fontfile.readuint16(ctable_ofst)
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
                glyphtablelen = (length - (self.fontfile.tell() - ctable_ofst)) // 2
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

    def scripts(self):
        ''' Get list of scripts in the font '''
        scripts = set()
        if self.gpos:
            scripts = scripts.union(set(self.gpos.scripts.keys()))
        if self.gsub:
            scripts = scripts.union(set(self.gsub.scripts.keys()))
        return list(scripts)

    def languages(self, script='DFLT'):
        ''' Get list of languages in the script '''
        langs = set()
        if self.gpos:
            s = self.gpos.scripts.get(script, None)
            if s is not None:
                langs = langs.union(set(s.languages.keys()))

        if self.gsub:
            s = self.gsub.scripts.get(script, None)
            if s is not None:
                langs = langs.union(set(s.languages.keys()))
        return list(langs)

    def language(self, script, language):
        ''' Set script/language to use '''
        if script == 'DFLT' and 'DFLT' not in self.scripts():
            script = 'latn'

        if script not in self.scripts():
            raise ValueError(f'Script {script} not defined in font')

        if language not in self.languages(script):
            raise ValueError(f'Language {language} not defined in font')

        if self.gpos:
            self.gpos.language.script = script
            self.gpos.language.language = language
        if self.gsub:
            self.gsub.language.script = script
            self.gsub.language.language = language

    def glyphindex(self, char: str) -> int:
        ''' Get index of character glyph '''
        gid = self._glyphids.get(char)
        if gid is None:
            gid = self.cmap.glyphid(char)  # type: ignore
            self._glyphids[char] = gid
        return gid

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
            if 'CFF ' in self.tables:
                glyph = read_glyph_cff(glyphid, self)
            else:  # 'glyf' table
                glyph = read_glyph_glyf(glyphid, self)
            self._glyphs[glyphid] = glyph
        return glyph

    def advance(self, glyph1: int, glyph2: Optional[int] = None):
        ''' Get advance width in font units, including kerning adjustment
            if glyph2 is defined
        '''
        try:
            adv = self.advwidths[glyph1].width
        except IndexError:
            adv = self.info.layout.advwidthmax.width

        if self.features.kern and glyph2 and self.gpos:
            # Only getting x-advance for first glyph.
            adv += self.gpos.kern(glyph1, glyph2)[0].get('xadvance', 0)
        return adv

    def getsize(self, s) -> tuple[float, float]:
        ''' Calculate width and height (including ascent/descent) of string '''
        txt = Text(s, self)
        return txt.getsize()

    def text(self, s: str,
             size: Optional[float] = None,
             linespacing: float = 1,
             halign: Literal['left', 'center', 'right'] = 'left',
             valign: Literal['base', 'center', 'top'] = 'base',
             color: Optional[str] = None,
             rotation: float = 0,
             rotation_mode: str = 'anchor'):
        ''' Create a Text object using this font

            Args:
                s: String to convert.
                size: Font size in points
                linespacing: Space between lines
                halign: Horizontal Alignment
                valign: Vertical Alignment
                color: Color for string
                rotation: Rotation angle in degrees
                rotation_mode: Either 'default' or 'anchor', to
                    mimic Matplotlib behavoir. See:
                    https://matplotlib.org/stable/gallery/text_labels_and_annotations/demo_text_rotation_mode.html
                kern: Use font kerning adjustment
        '''
        txt = Text(s, self, size=size, linespacing=linespacing, halign=halign, valign=valign,
                   color=color, rotation=rotation, rotation_mode=rotation_mode)
        return txt

    def showallglyphs(self, size: float = 36, pxwidth: int = 800):
        return ShowGlyphs(self)


class Text:
    ''' Draw text as SVG paths

        Args:
            s: String to draw
            font: Font name or ziafont.Font to use
            size: Font size in points
            linespacing: Spacing between lines
            color: Color for string
            halign: Horizontal Alignment
            valign: Vertical Alignment
            rotation: Rotation angle in degrees
            rotation_mode: Either 'default' or 'anchor', to
                mimic Matplotlib behavoir. See:
                https://matplotlib.org/stable/gallery/text_labels_and_annotations/demo_text_rotation_mode.html
    '''
    def __init__(self, s: Union[str, Sequence[int]],
                 font: Optional[Union[str, Font]] = None,
                 size: Optional[float] = None,
                 linespacing: float = 1,
                 halign: Literal['left', 'center', 'right'] = 'left',
                 valign: Literal['base', 'center', 'top'] = 'base',
                 color: Optional[str] = None,
                 rotation: float = 0,
                 rotation_mode: str = 'anchor'):
        self.str = s
        self.halign = halign
        self.valign = valign
        self.color = color
        self.rotation = rotation
        self.rotation_mode = rotation_mode
        self.size = size if size else config.fontsize
        self.linespacing = linespacing
        if font is None or isinstance(font, str):
            self.font = Font(font)
        else:
            self.font = font
        self._symbols = self._buildstring()

    def svgxml(self) -> ET.Element:
        ''' Get SVG XML element '''
        svg = ET.Element('svg')
        svg.attrib['xmlns'] = 'http://www.w3.org/2000/svg'
        if config.svg2:
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

    def drawon(self, svg: ET.Element, x: float = 0, y: float = 0):
        ''' Draw text on the SVG '''
        svg, _ = self._drawon(svg, x, y)
        return svg

    def _drawon(self, svg: ET.Element, x: float = 0, y: float = 0):
        ''' Draw text on the SVG '''
        word, symbols, width, xmin, ymin, ymax = self._symbols
        height = ymax-ymin
        # Adjust vertical alignment
        yofst = {'base': 0,
                 'bottom': -ymax,
                 'top': -ymin,
                 'center': -height/2-ymin}.get(self.valign, 0)
        xofst = {'center': -width/2,
                 'right': -width}.get(self.halign, 0)
        xy = x + xofst, y + yofst

        # Get existing symbol/glyphs, add ones not there yet
        if config.svg2:
            existingsymbols = svg.findall('symbol')
            symids = [sym.attrib.get('id') for sym in existingsymbols]
            for sym in symbols:
                if sym not in symids:
                    svg.append(sym)

        xform = ''
        if xy != (0, 0):
            xform = f'translate({fmt(xy[0])} {fmt(xy[1])})'

        svg.append(word)

        if config.debug:  # Test viewbox
            rect = ET.SubElement(word, 'rect')
            rect.attrib['x'] = '0'
            rect.attrib['y'] = fmt(ymin)
            rect.attrib['width'] = fmt(width)
            rect.attrib['height'] = fmt(height)
            rect.attrib['fill'] = 'none'
            rect.attrib['stroke'] = 'red'
            circ = ET.SubElement(word, 'circle')
            circ.attrib['cx'] = fmt(-xofst)
            circ.attrib['cy'] = fmt(-yofst)
            circ.attrib['r'] = '3'
            circ.attrib['fill'] = 'red'
            circ.attrib['stroke'] = 'red'
        bbox = (xy[0]+xmin, xy[0]+width, xy[1]+ymin, xy[1]+ymax)

        if self.rotation:
            centerx = xy[0]  # Center of rotation
            centery = xy[1]
            costh = math.cos(math.radians(self.rotation))
            sinth = math.sin(math.radians(self.rotation))
            p1 = (xofst, ymin+yofst)  # Corners relative to rotation point
            p2 = (xofst+width, ymin+yofst)
            p3 = (xofst+width, ymax+yofst)
            p4 = (xofst, ymax+yofst)
            x1 = centerx + (p1[0]*costh + p1[1]*sinth) - xofst
            x2 = centerx + (p2[0]*costh + p2[1]*sinth) - xofst
            x3 = centerx + (p3[0]*costh + p3[1]*sinth) - xofst
            x4 = centerx + (p4[0]*costh + p4[1]*sinth) - xofst
            y1 = centery - (p1[0]*sinth - p1[1]*costh) - yofst
            y2 = centery - (p2[0]*sinth - p2[1]*costh) - yofst
            y3 = centery - (p3[0]*sinth - p3[1]*costh) - yofst
            y4 = centery - (p4[0]*sinth - p4[1]*costh) - yofst
            bbox = (min(x1, x2, x3, x4), max(x1, x2, x3, x4),
                    min(y1, y2, y3, y4), max(y1, y2, y3, y4))

            if self.rotation_mode == 'default':
                dx = {'left': x - bbox[0],
                      'right': x - bbox[1],
                      'center': x - (bbox[1]+bbox[0])/2}.get(self.halign, 0)
                dy = {'top': y - bbox[2],
                      'bottom': y - bbox[3],
                      'base': -sinth*dx,
                      'center': y - (bbox[3]+bbox[2])/2}.get(self.valign, 0)
                xform = f'translate({xy[0]+dx} {xy[1]+dy})'
                bbox = (bbox[0]+dx, bbox[1]+dx,
                        bbox[2]+dy, bbox[3]+dy)
            xform += f' rotate({-self.rotation} {-xofst} {-yofst})'

        if config.debug:
            rect = ET.SubElement(svg, 'rect')
            rect.attrib['x'] = fmt(bbox[0])
            rect.attrib['y'] = fmt(bbox[2])
            rect.attrib['width'] = fmt(bbox[1]-bbox[0])
            rect.attrib['height'] = fmt(bbox[3]-bbox[2])
            rect.attrib['fill'] = 'none'
            rect.attrib['stroke'] = 'blue'

        word.attrib['transform'] = xform
        if self.color:
            word.attrib['fill'] = self.color
        return svg, bbox

    def str_to_gids(self):
        if isinstance(self.str, str):
            lines = self.str.splitlines()
            gidlines = [[self.font.glyphindex(c) for c in line] for line in lines]
        else:
            gidlines = [self.str]  # Single line
        return gidlines

    def _buildstring(self) -> Symbols:
        ''' Create symbols and svg word in a <g> group tag, for placing in an svg '''
        scale = self.size / self.font.info.layout.unitsperem
        lineheight = self.size * self.linespacing

        gidlines = self.str_to_gids()
        yvals = [i*lineheight for i in range(len(gidlines))]  # valign == 'base'

        # Generate symbols and calculate x positions using left alignment
        symbols: list[ET.Element] = []  # <symbol> elements
        linewidths: list[float] = []
        xadvance = 0.
        allglyphs = []  # (glyph, x, y) where x is left aligned, y is delta from baseline
        xmin = 0
        for lineidx, glyphids in enumerate(gidlines):
            lineglyphs = []
            if self.font.gsub:
                glyphids = self.font.gsub.sub(glyphids, self.font.features)

            glyphs = [self.font.glyph_fromid(gid) for gid in glyphids]
            x = 0
            xmin = min(xmin, glyphs[0].bbox.xmin*scale)
            for gidx, glyph in enumerate(glyphs):
                if glyph.id not in [s.attrib['id'] for s in symbols]:
                    symbols.append(glyph.svgsymbol())

                prevglyph = glyphs[gidx-1] if gidx-1 >= 0 else None
                nextglyph = glyphs[gidx+1] if gidx+1 < len(glyphs) else None
                if self.font.gpos and prevglyph:
                    # Attach marks
                    placexy = self.font.gpos.placemark(prevglyph.index, glyph.index)
                    if placexy:
                        if not placexy.mkmk:  # Relative to base glyph
                            dx = dy = 0
                        dx += (placexy.dx - xadvance) * scale
                        dy += -placexy.dy * scale
                    else:
                        dx = dy = 0
                else:
                    dx = dy = 0  # Don't reset, may need these for mark-to-mark p[

                lineglyphs.append((glyph, x+dx, dy))                
                xadvance = glyph.advance(nextglyph)
                x += xadvance * scale

            if glyph.bbox.xmax > xadvance:
                # Make linewidth a bit wider to grab right edge
                # that extends beyond advance width
                x += (glyph.bbox.xmax - xadvance) * scale
                x += (-glyphs[0].bbox.xmin) * scale
            linewidths.append(x)
            allglyphs.append(lineglyphs)

        # Place the glyphs based on halign
        word = ET.Element('g')
        totwidth = max(linewidths)
        for lineidx, (lineglyphs, linewidth) in enumerate(zip(allglyphs, linewidths)):
            if self.halign == 'center':
                leftshift = (totwidth - linewidth)/2
            elif self.halign == 'right':
                leftshift = totwidth - linewidth
            else:  # halign = 'left'
                leftshift = 0
            for glyph, x, dy in lineglyphs:
                elm = glyph.place(x+leftshift, yvals[lineidx]+dy, self.size)
                if elm is not None:
                    word.append(elm)

        ymin = yvals[0] - self.font.info.layout.ymax*scale
        ymax = yvals[-1] - self.font.info.layout.ymin*scale

        if not config.svg2:
            symbols = []
        return Symbols(word, symbols, totwidth, xmin, ymin, ymax)

    def getsize(self) -> tuple[float, float]:
        ''' Calculate width and height (including ascent/descent) of string '''
        return self._symbols.width, self._symbols.ymax-self._symbols.ymin

    def getyofst(self) -> float:
        ''' Y-shift from bottom of bbox to 0 '''
        return -self._symbols.ymax
