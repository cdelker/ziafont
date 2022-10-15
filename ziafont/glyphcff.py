''' CFF/Type 2 Charstring Glyphs '''

from __future__ import annotations
from typing import Union, TYPE_CHECKING

import struct
from enum import Enum
import warnings

from .glyph import SimpleGlyph
from .fonttypes import BBox
from .svgpath import Point, Moveto, Lineto, Cubic, SVGOpType

if TYPE_CHECKING:
    from .font import Font


class Operator(Enum):
    ''' Charstring Operators '''
    HSTEM = 1
    # reserved = 2
    VSTEM = 3
    VMOVETO = 4
    RLINETO = 5
    HLINETO = 6
    VLINETO = 7
    RRCURVETO = 8
    # reserved = 9
    CALLSUBR = 10
    RETURN = 11
    # escape = 12
    # reserved = 13
    ENDCHAR = 14
    # reserved = 15, 16, 17
    HSTEMHM = 18
    HINTMASK = 19
    CNTRMASK = 20
    RMOVETO = 21
    HMOVETO = 22
    VSTEMHM = 23
    RCURVELINE = 24
    RLINECURVE = 25
    VVCURVETO = 26
    HHCURVETO = 27
    # reserved = 28/short int
    CALLGSUBR = 29
    VHCURVETO = 30
    HVCURVETO = 31
    # TODO: 12.XXX codes

    WIDTH = -999  # Not numbered in CFF spec


def read_glyph_cff(glyphid: int, font: Font) -> SimpleGlyph:
    ''' Read a glyph from the CFF table. '''
    if font.cffdata is None:
        font.cffdata = CFF(font)

    charstr = font.cffdata.charstr_index[glyphid]
    ops, width, ymin, ymax = charstr2path(charstr, font.cffdata)
    bbox = BBox(0, width, ymin, ymax)
    glyph = SimpleGlyph(glyphid, ops, bbox, font)
    return glyph


def charstr2path(charstr: bytes, cff: CFF) -> tuple[list[SVGOpType], float, float, float]:
    ''' Convert the charstring operators into SVG path elements '''
    operators: list[SVGOpType] = []
    width = cff.defaultwidth
    p = Point(0, 0)
    for op, value in readcharstr(charstr, cff):
        # print(op, value)
        if op == Operator.WIDTH:
            width += int(value[0])
        elif op == Operator.RMOVETO:
            p = p + Point(value[0], value[1])
            operators.append(Moveto(p))
        elif op == Operator.HMOVETO:
            p = p + Point(value[0], 0)
            operators.append(Moveto(p))
        elif op == Operator.VMOVETO:
            p = p + Point(0, value[0])
            operators.append(Moveto(p))
        elif op == Operator.HLINETO:
            for i in range(len(value)):
                if (i % 2) == 0:  # Alternate Horizontal and Vertical lines
                    p = p + Point(value[i], 0)
                else:
                    p = p + Point(0, value[i])
                operators.append(Lineto(p))

        elif op == Operator.VLINETO:
            for i in range(len(value)):
                if (i % 2) == 0:  # Alternate Horizontal and Vertical lines
                    p = p + Point(0, value[i])
                else:
                    p = p + Point(value[i], 0)
                operators.append(Lineto(p))

        elif op == Operator.RLINETO:
            for dx, dy in zip(value[::2], value[1::2]):
                p = p + Point(dx, dy)
                operators.append(Lineto(p))

        elif op in [Operator.RRCURVETO, Operator.RCURVELINE]:
            n = 0
            while len(value) > 2:
                n += 1
                dxa, dya, dxb, dyb, dxc, dyc, *_ = value
                p1 = p + Point(dxa, dya)
                p2 = p1 + Point(dxb, dyb)
                p = p2 + Point(dxc, dyc)
                operators.append(Cubic(p1, p2, p))
                value = value[6:]
            if len(value) == 2:
                # RCURVELINE ends with a line
                p = p + Point(value[0], value[1])
                operators.append(Lineto(p))

        elif op == Operator.RLINECURVE:
            while len(value) > 6:
                # Lines until last 6 arguments
                p = p + Point(value[0], value[1])
                operators.append(Lineto(p))
                value = value[2:]
            # Last 6 define Bezier
            dxa, dya, dxb, dyb, dxc, dyc, *_ = value
            p1 = p + Point(dxa, dya)
            p2 = p1 + Point(dxb, dyb)
            p = p2 + Point(dxc, dyc)
            operators.append(Cubic(p1, p2, p))

        elif op == Operator.HVCURVETO:
            if len(value) % 8 >= 4:
                dx1, dx2, dy2, dy3, *_ = value
                p1 = p + Point(dx1, 0)
                p2 = p1 + Point(dx2, dy2)
                p = p2 + Point(0, dy3)
                operators.append(Cubic(p1, p2, p))
                value = value[4:]
                while len(value) >= 8:
                    dya, dxb, dyb, dxc, dxd, dxe, dye, dyf, *_ = value
                    if len(value) == 9:
                        dxf = value[-1]
                    else:
                        dxf = 0

                    p1 = p + Point(0, dya)
                    p2 = p1 + Point(dxb, dyb)
                    p = p2 + Point(dxc, 0)
                    operators.append(Cubic(p1, p2, p))
                    p1 = p + Point(dxd, 0)
                    p2 = p1 + Point(dxe, dye)
                    p = p2 + Point(dxf, dyf)
                    operators.append(Cubic(p1, p2, p))
                    value = value[8:]

            else:
                while len(value) >= 8:
                    dxa, dxb, dyb, dyc, dyd, dxe, dye, dxf, *_ = value
                    if len(value) == 9:
                        dyf = value[-1]
                    else:
                        dyf = 0

                    p1 = p + Point(dxa, 0)
                    p2 = p1 + Point(dxb, dyb)
                    p = p2 + Point(0, dyc)
                    operators.append(Cubic(p1, p2, p))
                    p1 = p + Point(0, dyd)
                    p2 = p1 + Point(dxe, dye)
                    p = p2 + Point(dxf, dyf)
                    operators.append(Cubic(p1, p2, p))
                    value = value[8:]

        elif op == Operator.VHCURVETO:
            if len(value) % 8 >= 4:
                dy1, dx2, dy2, dx3, *_ = value
                p1 = p + Point(0, dy1)
                p2 = p1 + Point(dx2, dy2)
                p = p2 + Point(dx3, 0)
                operators.append(Cubic(p1, p2, p))
                value = value[4:]
                while len(value) >= 8:
                    dxa, dxb, dyb, dyc, dyd, dxe, dye, dxf, *_ = value
                    if len(value) == 9:
                        dyf = value[-1]
                    else:
                        dyf = 0

                    p1 = p + Point(dxa, 0)
                    p2 = p1 + Point(dxb, dyb)
                    p = p2 + Point(0, dyc)
                    operators.append(Cubic(p1, p2, p))
                    p1 = p + Point(0, dyd)
                    p2 = p1 + Point(dxe, dye)
                    p = p2 + Point(dxf, dyf)
                    operators.append(Cubic(p1, p2, p))
                    value = value[8:]

            else:
                while len(value) >= 8:
                    dya, dxb, dyb, dxc, dxd, dxe, dye, dyf, *_ = value
                    if len(value) == 9:
                        dxf = value[-1]
                    else:
                        dxf = 0

                    p1 = p + Point(0, dya)
                    p2 = p1 + Point(dxb, dyb)
                    p = p2 + Point(dxc, 0)
                    operators.append(Cubic(p1, p2, p))
                    p1 = p + Point(dxd, 0)
                    p2 = p1 + Point(dxe, dye)
                    p = p2 + Point(dxf, dyf)
                    operators.append(Cubic(p1, p2, p))
                    value = value[8:]

        elif op not in [Operator.HSTEM, Operator.HINTMASK, Operator.VSTEM,
                        Operator.VSTEMHM, Operator.HSTEMHM, Operator.RETURN,
                        Operator.CNTRMASK, Operator.ENDCHAR]:
            raise NotImplementedError(f'Operator {op} not implemented')

    if op != Operator.ENDCHAR:
        warnings.warn('Glyph has no ENDCHAR')

    ymin = min(op.ymin() for op in operators)
    ymax = max(op.ymax() for op in operators)
    return operators, width, ymin, ymax


def readcharstr(buf: bytes, cff: CFF) -> list[tuple[Union[Operator, int], Union[bytes, list[float]]]]:
    ''' Read charstring into list of (operator, value) pairs '''
    data: list[tuple[Union[Operator, int], Union[bytes, list[float]]]] = []
    value: list[float] = []
    aval: Union[None, bytes, float, list[float]]
    key: Union[Operator, int]
    nhints = 0

    while len(buf) > 0:
        # Operator (key)
        if buf[0] <= 27 or 29 <= buf[0] <= 31:
            key = buf[0]
            i = 1
            if buf[0] == 12:
                key = struct.unpack_from('>H', buf)[0]
                i = 2

            try:
                key = Operator(key)
            except ValueError:
                warnings.warn(f'Unimplemented KEY {key}')

            if len(data) == 0:
                # First operator can have extra width parameter.
                # have to deduce its presence based on the
                # operator and number of values in stack
                if key in [Operator.CNTRMASK, Operator.ENDCHAR] and len(value) == 1:
                    data.append((Operator.WIDTH, value))
                    aval = [0]
                elif ((key in [Operator.HMOVETO, Operator.VMOVETO] and len(value) > 1) or
                      (key in [Operator.RMOVETO] and len(value) > 2)):
                    data.append((Operator.WIDTH, value))
                    aval = value[1:]
                elif (key in [Operator.HSTEM, Operator.HSTEMHM, Operator.VSTEM,
                              Operator.VSTEMHM, Operator.HINTMASK] and
                      len(value) % 2 != 0):
                    data.append((Operator.WIDTH, value))
                    aval = value[1:]
                else:
                    aval = value

            elif key == Operator.CALLSUBR:
                if cff.topdict.get('charstringtype', 2) == 1:
                    bias = 0
                elif len(cff.localsubs) < 1240:
                    bias = 107
                elif len(cff.localsubs) < 33900:
                    bias = 1131
                else:
                    bias = 32768
                idx = int(value[0] + bias)
                subchstr = cff.localsubs[idx]
                data.extend(readcharstr(subchstr, cff))
                value = []
                buf = buf[i:]
                continue

            elif key in [Operator.HINTMASK, Operator.CNTRMASK]:
                if data[-1][0] == Operator.HSTEMHM and len(value) > 0:
                    # Implied VSTEM operator
                    nhints += len(value)//2
                    data.append((Operator.VSTEMHM, value))
                # N-bits for the N hint masks just read in
                hintbytes = nhints + 7 >> 3
                aval = buf[1:hintbytes+1]
                i = hintbytes+1

            else:
                aval = value

            if key in [Operator.HSTEM, Operator.HSTEMHM, Operator.VSTEM, Operator.VSTEMHM]:
                nhints += len(aval)//2

            data.append((key, aval))
            value = []

        # Opearand (value)
        elif buf[0] == 28:
            value.append(struct.unpack_from('>h', buf[1:])[0])  # signed short
            i = 3
        elif 32 <= buf[0] <= 246:
            value.append(buf[0] - 139)
            i = 1
        elif 247 <= buf[0] <= 250:
            value.append((buf[0]-247)*256 + buf[1] + 108)
            i = 2
        elif 251 <= buf[0] <= 254:
            value.append(-(buf[0]-251)*256 - buf[1] - 108)
            i = 2
        elif buf == 255:
            raise NotImplementedError # TODO REAL number
        else:
            raise ValueError('Bad encoding byte: ' + str(buf[0]))
            value.append(None)
            i = 1

        buf = buf[i:]
    return data


def readdict(buf: bytes) -> dict:
    ''' Read a CFF dictionary structure from the buffer '''
    data: dict[Union[int, str], Union[None, list[int], int]] = {}
    value: list[int] = []
    key: Union[int, str]
    while len(buf) > 0:
        # Operator (key)
        if buf[0] <= 21:
            key = buf[0]
            i = 1
            if buf[0] == 12:
                key = '12.' + str(buf[1])
                i = 2
            if len(value) == 0:
                data[key] = None
            elif len(value) == 1:
                data[key] = value[0]
            else:
                data[key] = value
            value = []

        # Opearand (value)
        elif buf[0] == 28:
            value.append(struct.unpack_from('>h', buf[1:])[0])  # signed short
            i = 3
        elif buf[0] == 29:
            value.append(struct.unpack_from('>l', buf[1:])[0])  # signed long
            i = 5
        elif 32 <= buf[0] <= 246:
            value.append(buf[0] - 139)
            i = 1
        elif 247 <= buf[0] <= 250:
            value.append((buf[0]-247)*256 + buf[1] + 108)
            i = 2
        elif 251 <= buf[0] <= 254:
            value.append(-(buf[0]-251)*256 - buf[1] - 108)
            i = 2
        elif buf[0] == 30:
            raise NotImplementedError # TODO - REAL number
        else:
            warnings.warn('Bad encoding byte: ' + str(buf[0]))
            value.append(0)
            i = 1

        buf = buf[i:]
    return data


class CFF:
    ''' Compact Font Format table info '''
    def __init__(self, font: Font):
        self.cffofst = font.tables['CFF '].offset
        self.font = font
        self.fontfile = self.font.fontfile

        self.major = self.fontfile.readuint8(self.font.tables['CFF '].offset)
        self.minor = self.fontfile.readuint8()
        self.headsize = self.fontfile.readuint8()
        self.offsize = self.fontfile.readuint8()
        self.names = self.readindex(self.cffofst + self.offsize)
        topdict_bytes = self.readindex()
        self.strings = self.readindex()
        self.globalsub = self.readindex()
        self.topdicts: list[dict] = [self.read_topdict(readdict(t)) for t in topdict_bytes]
        self.set_topdict(0)

    def set_topdict(self, idx: int = 0) -> None:
        ''' Set which TOP DICT to use and load the corresponding
            PRIVATE DICT values.
        '''
        topdict = self.topdicts[idx]
        self.topdict = topdict
        charstr_ofst = self.cffofst + topdict['charstrings']
        self.charstr_index: list[bytes] = self.readindex(charstr_ofst)
        self.nglyphs = len(self.charstr_index)

        self.font.fontfile.seek(self.cffofst + topdict['private'][1])
        pdictbytes = self.font.fontfile.read(topdict['private'][0])
        self.privatedict = self.read_topdict(readdict(pdictbytes))
        self.localsubs: list[bytes] = []
        if 'subrs' in self.privatedict:
            self.localsubs = self.readindex(
                self.cffofst + topdict['private'][1] + self.privatedict['subrs'])

    @property
    def defaultwidth(self) -> int:
        ''' Get default glyph width '''
        return self.privatedict.get('defaultwidthx', 0)

    @property
    def nominalwidth(self) -> int:
        ''' Get nominal glyph width '''
        return self.privatedict.get('nominalwidthx', 0)

    def getstring(self, sid: int) -> bytes:
        ''' Get a string by String ID '''
        nstandardstrings = 391
        if sid > nstandardstrings:
            return self.strings[sid-nstandardstrings]
        else:
            return b'standard string'  # TODO

    def readindex(self, offset=None) -> list[bytes]:
        ''' Read an INDEX structure from the CFF data '''
        count = self.fontfile.readuint16(offset)
        offsize = self.fontfile.readuint8()  # should be 1-4
        if offsize == 0:
            return []

        offsets = []
        for i in range(count+1):
            if offsize == 1:
                offsets.append(self.fontfile.readuint8())
            elif offsize == 2:
                offsets.append(self.fontfile.readuint16())
            elif offsize == 3:
                offsets.append(self.fontfile.readuint24())
            elif offsize == 4:
                offsets.append(self.fontfile.readuint32())
            else:
                raise ValueError('Incorrect offset size ' + str(offsize))

        dataofst = self.fontfile.tell()-1  # Start of Object data (minus 1)
        values = []
        for i in range(count):
            self.fontfile.seek(dataofst + offsets[i])
            values.append(self.fontfile.read(offsets[i+1]-offsets[i]))
        return values

    def read_topdict(self, d: dict) -> dict:
        ''' Translate raw CFF dictionary into topdict with meaningful keys '''
        topdict_entries = {
            0: ('version', 'sid'),
            1: ('notice', 'sid'),
            2: ('fullname', 'sid'),
            3: ('familyname', 'sid'),
            4: ('weight', 'number'),
            5: ('fontbbox', 'array'),
            13: ('uniqueid', 'number'),
            14: ('xuid', 'array'),
            15: ('charset', 'number'),
            16: ('encoding', 'number'),
            17: ('charstrings', 'number'),
            18: ('private', 'array'),
            '12.0': ('copyright', 'sid'),
            '12.1': ('isfixedpitch', 'number'),
            '12.2': ('italicangle', 'number'),
            '12.3': ('underlineposition', 'number'),
            '12.4': ('underlinethickness', 'number'),
            '12.5': ('painttype', 'number'),
            '12.6': ('charstringtype', 'number'),
            '12.7': ('fontmatrix', 'array'),
            '12.8': ('strokewidth', 'number'),
            '12.20': ('syntheticbase', 'number'),
            '12.21': ('postscript', 'sid'),
            '12.22': ('basefontname', 'sid'),
            '12.23': ('basefontblend' 'array'),
            # Private Dict Keys
            6: ('bluevalues', 'array'),
            7: ('otherblues', 'array'),
            8: ('familyblues', 'array'),
            9: ('familyotherblues', 'array'),
            10: ('stdhw', 'number'),
            11: ('stdvw', 'number'),
            19: ('subrs', 'number'),
            20: ('defaultwidthx', 'number'),
            21: ('nominalwidthx', 'number'),
            '12.9': ('bluescale', 'number'),
            '12.10': ('blueshift', 'number'),
            '12.11': ('bluefuzz', 'number'),
            '12.12': ('stemsnaph', 'array'),
            '12.13': ('stemsnaph', 'array'),
            '12.14': ('stemsnaph', 'number'),
            '12.17': ('languagegroup', 'number'),
            '12.18': ('expansionfactor', 'number'),
            '12.19': ('initialrandomseed', 'number')}

        newd = {}
        for key, value in d.items():
            print(key, value)
            newkey, dtype = topdict_entries.get(key, (key, 'number'))
            if newkey:
                if dtype == 'sid':
                    value = self.getstring(value)
                newd[newkey] = value

        assert newd.get('charstringtype', 2) == 2
        return newd
