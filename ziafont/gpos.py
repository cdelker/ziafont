''' Glyph Positioning System (GPOS) tables '''

from __future__ import annotations
from typing import Optional
from collections import namedtuple

from .fontread import FontReader


class Gpos:
    ''' Glyph Positioning System Table '''
    def __init__(self, ofst: int, fontfile: FontReader):
        self.ofst = ofst
        self.fontfile = fontfile
        self.fontfile.seek(self.ofst)

        self.vermajor = self.fontfile.readuint16()
        self.verminor = self.fontfile.readuint16()
        scriptofst = self.fontfile.readuint16()
        featureofst = self.fontfile.readuint16()
        lookupofst = self.fontfile.readuint16()
        if self.verminor > 0:
            self.variationofst = self.fontfile.readuint32()

        # Read scripts
        scriptlisttableloc = self.ofst + scriptofst
        scriptcnt = self.fontfile.readuint16(scriptlisttableloc)
        self.scripts = {}
        for i in range(scriptcnt):
            tag = self.fontfile.read(4).decode()
            self.scripts[tag] = Script(
                tag,
                self.fontfile.readuint16() + scriptlisttableloc,
                self.fontfile)

        # Read features
        featurelisttableloc = self.ofst + featureofst
        featurecnt = self.fontfile.readuint16(featurelisttableloc)
        self.features = []
        for i in range(featurecnt):
            self.features.append(Feature(
                self.fontfile.read(4).decode(),
                self.fontfile.readuint16() + featurelisttableloc,
                self.fontfile))

        # Read Lookups
        lookuplisttableloc = self.ofst + lookupofst
        lookupcnt = self.fontfile.readuint16(lookuplisttableloc)
        self.lookups = []
        for i in range(lookupcnt):
            self.lookups.append(Lookup(
                self.fontfile.readuint16() + lookuplisttableloc,
                self.fontfile))

    def kern(self, glyph1: int, glyph2: int, script:
             str=None, lang: str=None) -> tuple[Optional[dict], Optional[dict]]:
        ''' Get kerning adjustmnet for glyph1 and glyph2 '''
        scr = self.scripts.get(script, self.scripts.get('DFLT', self.scripts.get('latn')))  # type: ignore
        if scr is None:
            return {}, {}
        langsys = scr.languages.get(lang, scr.languages.get('DFLT'))  # type: ignore
        if langsys is None:
            return {}, {}

        # Find kerning features in features list
        usefeatures = [self.features[i] for i in langsys.featureidxs]  # type: ignore
        featnames = [f.tag for f in usefeatures]
        if 'kern' in featnames:
            lookups = usefeatures[featnames.index('kern')].lookupids
            tables = [self.lookups[i] for i in lookups]
            for table in tables:
                for subtable in table.subtables:
                    v1, v2 = subtable.get_adjust(glyph1, glyph2)
                    if v1 or v2:
                        return v1, v2
        return {}, {}  # No adjustments

    def __repr__(self):
        return f'<GPOS Table v{self.vermajor}.{self.verminor}>'


class Script:
    ''' GPOS Script table '''
    def __init__(self, tag: str, ofst: int, fontfile: FontReader):
        self.tag = tag
        self.ofst = ofst
        self.fontfile = fontfile
        fileptr = self.fontfile.tell()
        self.fontfile.seek(self.ofst)
        self.defaultLangSysOfst = self.fontfile.readuint16()
        self.languages = {}

        if self.defaultLangSysOfst:
            self.languages['DFLT'] = LanguageSystem(
                'DFLT',
                self.defaultLangSysOfst + self.ofst,
                self.fontfile)

        langsyscnt = self.fontfile.readuint16()
        for i in range(langsyscnt):
            tag = self.fontfile.read(4).decode()
            self.languages[tag] = (LanguageSystem(
                tag,
                self.fontfile.readuint16() + self.ofst,
                self.fontfile))

        self.fontfile.seek(fileptr)  # Put file pointer back

    def __repr__(self):
        return f'<Script {self.tag}, {hex(self.ofst)}>'


class LanguageSystem:
    ''' GPOS Language System Table '''
    def __init__(self, tag: str, ofst: int, fontfile: FontReader):
        self.tag = tag
        self.ofst = ofst
        self.fontfile = fontfile
        fileptr = self.fontfile.tell()
        self.fontfile.seek(self.ofst)
        self.fontfile.readuint16()  # lookupordeoffset (reserved)
        self.reqdFeatureIndex = self.fontfile.readuint16()
        featurecount = self.fontfile.readuint16()
        self.featureidxs = []
        for i in range(featurecount):
            self.featureidxs.append(self.fontfile.readuint16())

        self.fontfile.seek(fileptr)  # Put file pointer back

    def __repr__(self):
        return f'<LanguageSystem {self.tag}, {hex(self.ofst)}>'


class Feature:
    ''' GPOS Feature Table '''
    def __init__(self, tag: str, ofst: int, fontfile: FontReader):
        self.tag = tag
        self.ofst = ofst
        self.fontfile = fontfile
        fileptr = self.fontfile.tell()
        self.fontfile.seek(self.ofst)
        self.featureparamofst = self.fontfile.readuint16()
        lookupcnt = self.fontfile.readuint16()
        self.lookupids = []
        for i in range(lookupcnt):
            self.lookupids.append(self.fontfile.readuint16())

        self.fontfile.seek(fileptr)  # Put file pointer back

    def __repr__(self):
        return f'<Feature {self.tag}, {hex(self.ofst)}>'


class Lookup:
    ''' GPOS Lookup Table '''
    def __init__(self, ofst: int, fontfile: FontReader):
        self.ofst = ofst
        self.fontfile = fontfile
        fileptr = self.fontfile.tell()

        RIGHT_TO_LEFT = 0x0001
        IGNORE_BASE_GLYPHS = 0x0002
        IGNORE_LIGATURES = 0x0004
        IGNORE_MARKS = 0x0008
        USE_MARK_FILTERING_SET = 0x0010
        MARK_ATTACHMENT_TYPE_MASK = 0xFF00

        self.fontfile.seek(self.ofst)
        self.type = self.fontfile.readuint16()
        self.flag = self.fontfile.readuint16()
        subtablecnt = self.fontfile.readuint16()
        self.tableofsts = []
        for i in range(subtablecnt):
            self.tableofsts.append(self.fontfile.readuint16())
        self.markfilterset = None
        if self.flag & USE_MARK_FILTERING_SET:
            self.markfilterset = self.fontfile.readuint16()

        self.subtables = []
        if self.type == 2:  # Pair adjustment positioning
            for i in range(subtablecnt):
                self.subtables.append(PairAdjustmentTable(
                    self.tableofsts[i] + self.ofst,
                    self.fontfile))
        elif self.type == 9:  # Extension subtable. Can be any type
            ptr = self.fontfile.tell()
            posformat = self.fontfile.readuint16()
            assert posformat == 1
            exttype = self.fontfile.readuint16()
            extofst = self.fontfile.readuint32()
            if exttype == 2:
                self.subtables.append(PairAdjustmentTable(
                    ptr + extofst,
                    self.fontfile))
        else:
            pass ## print('Lookup', self.type)

        self.fontfile.seek(fileptr)  # Put file pointer back

    def __repr__(self):
        return f'<LookupTable {hex(self.ofst)}>'


class PairAdjustmentTable:
    ''' Pair Adjustment Table - informs kerning between pairs of glyphs '''
    def __init__(self, ofst: int, fontfile: FontReader):
        self.ofst = ofst
        self.fontfile = fontfile
        fileptr = self.fontfile.tell()

        self.fontfile.seek(self.ofst)
        self.posformat = self.fontfile.readuint16()
        self.covofst = self.fontfile.readuint16()
        self.valueformat1 = self.fontfile.readuint16()
        self.valueformat2 = self.fontfile.readuint16()

        if self.posformat == 1:
            pairsetcount = self.fontfile.readuint16()
            pairsetofsts = []
            for i in range(pairsetcount):
                pairsetofsts.append(self.fontfile.readuint16())

            PairValue = namedtuple('PairValue', ['secondglyph', 'value1', 'value2'])
            self.pairsets = []
            for i in range(pairsetcount):
                self.fontfile.seek(pairsetofsts[i] + self.ofst)
                paircnt = self.fontfile.readuint16()
                pairs = []
                for p in range(paircnt):
                    pairs.append(PairValue(
                        self.fontfile.readuint16(),
                        self.fontfile.readvaluerecord(self.valueformat1),
                        self.fontfile.readvaluerecord(self.valueformat2)))
                self.pairsets.append(pairs)

        elif self.posformat == 2:
            classdef1ofst = self.fontfile.readuint16()
            classdef2ofst = self.fontfile.readuint16()
            class1cnt = self.fontfile.readuint16()
            class2cnt = self.fontfile.readuint16()

            self.classrecords = []
            for i in range(class1cnt):
                class2recs = []
                for j in range(class2cnt):
                    class2recs.append(
                        (self.fontfile.readvaluerecord(self.valueformat1),
                         self.fontfile.readvaluerecord(self.valueformat2)))
                self.classrecords.append(class2recs)

            self.class1def = ClassDef(self.ofst + classdef1ofst, self.fontfile)
            self.class2def = ClassDef(self.ofst + classdef2ofst, self.fontfile)

        else:
            raise ValueError('Invalid posformat in PairAdjustmnetTable')

        self.coverage = Coverage(self.covofst+self.ofst, self.fontfile)
        self.fontfile.seek(fileptr)  # Put file pointer back

    def get_adjust(self, glyph1: int, glyph2: int) -> tuple[Optional[dict], Optional[dict]]:
        ''' Get kerning adjustment for glyph1 and glyph2 pair '''
        v1 = v2 = None

        # Look up first glyph in coverage table
        covidx = self.coverage.covidx(glyph1)
        if covidx is not None:

            # Look up second glyph
            if self.posformat == 1:
                for p in self.pairsets[covidx]:
                    if p.secondglyph == glyph2:
                        v1 = p.value1
                        v2 = p.value2
                        break

            else:
                c1 = self.class1def.get_class(glyph1)
                c2 = self.class2def.get_class(glyph2)
                if c1 is not None and c2 is not None:
                    v1, v2 = self.classrecords[c1][c2]

        return v1, v2

    def __repr__(self):
        return f'<PairAdjustmentTable {hex(self.ofst)}>'


class Coverage:
    ''' Coverage Table - defines which glyphs apply to this lookup '''
    def __init__(self, ofst: int, fontfile: FontReader):
        self.ofst = ofst
        self.fontfile = fontfile
        fileptr = self.fontfile.tell()

        self.fontfile.seek(self.ofst)
        self.format = self.fontfile.readuint16()

        if self.format == 1:
            glyphcnt = self.fontfile.readuint16()
            self.glyphs = []
            for i in range(glyphcnt):
                self.glyphs.append(self.fontfile.readuint16())

        elif self.format == 2:
            rangecnt = self.fontfile.readuint16()
            Range = namedtuple('Range', ['startglyph', 'endglyph', 'covidx'])
            self.ranges = []
            for i in range(rangecnt):
                self.ranges.append(Range(
                    self.fontfile.readuint16(),
                    self.fontfile.readuint16(),
                    self.fontfile.readuint16()))
        else:
            raise ValueError('Bad coverage table format')

        self.fontfile.seek(fileptr)  # Put file pointer back

    def covidx(self, glyph: int) -> Optional[int]:
        ''' Get coverage index for this glyph, or None if not in the coverage range '''
        if self.format == 1:
            try:
                idx: Optional[int] = self.glyphs.index(glyph)
            except (ValueError, IndexError):
                idx = None
        else:
            for r in self.ranges:
                if r.startglyph <= glyph <= r.endglyph:
                    idx = r.covidx + (glyph - r.startglyph)
                    break
            else:
                idx = None
        return idx

    def __repr__(self):
        return f'<CoverageTable {hex(self.ofst)}>'


class ClassDef:
    ''' Class Definition Table - defines a "class" of glyphs. '''
    def __init__(self, ofst: int, fontfile: FontReader):
        self.ofst = ofst
        self.fontfile = fontfile
        fileptr = self.fontfile.tell()

        self.fontfile.seek(self.ofst)
        self.format = self.fontfile.readuint16()

        if self.format == 1:
            self.startglyph = self.fontfile.readuint16()
            glyphcnt = self.fontfile.readuint16()
            self.classvalues = []
            for i in range(glyphcnt):
                self.classvalues.append(self.fontfile.readuint16())

        elif self.format == 2:
            ClassRange = namedtuple('ClassRange', ['startglyph', 'endglyph', 'cls'])
            rangecnt = self.fontfile.readuint16()
            self.ranges = []
            for i in range(rangecnt):
                self.ranges.append(ClassRange(
                    self.fontfile.readuint16(),
                    self.fontfile.readuint16(),
                    self.fontfile.readuint16()))
        else:
            raise ValueError

        self.fontfile.seek(fileptr)  # Put file pointer back

    def get_class(self, glyphid: int) -> int:
        ''' Get class by glyph id '''
        if self.format == 1:
            if self.startglyph <= glyphid < self.startglyph + len(self.classvalues):
                return self.classvalues[glyphid - self.startglyph]
            else:
                return 0

        else:
            for i, rng in enumerate(self.ranges):
                if rng.startglyph <= glyphid <= rng.endglyph:
                    return rng.cls
            return 0

    def __repr__(self):
        return f'<ClassDefTable {hex(self.ofst)}>'
