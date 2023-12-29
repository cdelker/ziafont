''' Glyph Positioning System (GPOS) tables '''

from __future__ import annotations
from typing import Optional, Union
import logging
from collections import namedtuple

from .fontread import FontReader
from .tables import Coverage, ClassDef, Feature, Script, Language


PlaceMark = namedtuple('PlaceMark', ['dx', 'dy', 'mkmk'])
MarktoBaseAnchor = namedtuple('MarktoBaseAnchor', ['base', 'mark'])


class Gpos:
    ''' Glyph Positioning System Table '''
    def __init__(self, ofst: int, fontfile: FontReader):
        self.ofst = ofst
        self.fontfile = fontfile
        self.language = Language()
        self.fontfile.seek(self.ofst)

        self.vermajor = self.fontfile.readuint16()
        self.verminor = self.fontfile.readuint16()
        scriptofst = self.fontfile.readuint16()
        featureofst = self.fontfile.readuint16()
        lookupofst = self.fontfile.readuint16()
        if self.verminor > 0:
            self.variationofst = self.fontfile.readuint32()
            logging.warning('GPOS has feature variations - unimplemented')

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
        featurelist = []
        for i in range(featurecnt):
            featurelist.append(Feature(
                self.fontfile.read(4).decode(),
                self.fontfile.readuint16() + featurelisttableloc,
                self.fontfile))

        # Read Lookups
        lookuplisttableloc = self.ofst + lookupofst
        lookupcnt = self.fontfile.readuint16(lookuplisttableloc)
        self.lookups = []
        for i in range(lookupcnt):
            self.lookups.append(GposLookup(
                self.fontfile.readuint16() + lookuplisttableloc,
                self.fontfile))

        # Put everything in a dictionary for access
        self.features = {}
        for scrname, script in self.scripts.items():
            langdict = {}
            for langname, lang in script.languages.items():
                langfeatures = [featurelist[i] for i in lang.featureidxs]
                featnames = [f.tag for f in langfeatures]
                featdict = {}
                for feat in featnames:
                    lookups = langfeatures[featnames.index(feat)].lookupids
                    tables = [self.lookups[i] for i in lookups]
                    featdict[feat] = tables
                langdict[langname] = featdict
            self.features[scrname] = langdict

    def features_active(self):
        ''' Dictionary of features active in the current script/language system '''
        return self.features.get(self.language.script, {}).get(self.language.language, {})

    def kern(self, glyph1: int, glyph2: int) -> tuple[dict, dict]:
        ''' Get kerning adjustmnet for glyph1 and glyph2 '''
        feattable = self.features_active()
        if 'kern' in feattable:
            for table in feattable['kern']:
                for subtable in table.subtables:
                    v1, v2 = subtable.get_adjust(glyph1, glyph2)
                    if v1 or v2:
                        return v1, v2
        return {}, {}  # No adjustments

    def placemark(self, base: int, mark: int) -> Optional[PlaceMark]:
        ''' Return dx, dy postition wrt original mark position '''
        features = self.features_active()
        for feat in ['mark', 'mkmk']:
            if feat in features:
                for lookup in features[feat]:
                    for subtable in lookup.subtables:
                        if not hasattr(subtable, 'anchor'):
                            logging.debug('skipping unimplemented placemark subtable %s', subtable)
                            continue

                        anchors = subtable.anchor(base, mark)
                        if anchors is not None:
                            dx = anchors.base.x - anchors.mark.x
                            dy = anchors.base.y - anchors.mark.y
                            logging.debug('Positioning Mark %s on %s: (%s, %s)',
                                          mark, base, dx, dy)
                            mkmk = isinstance(subtable, MarkToMarkSubtable)
                            return PlaceMark(dx, dy, mkmk)   # Use first one found
        return None

    def __repr__(self):
        return f'<GPOS Table v{self.vermajor}.{self.verminor}>'


class GposLookup:
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

        self.subtables: list[Union[PairAdjustmentSubtable,
                                   MarkToBaseSubtable,
                                   MarkToMarkSubtable]] = []
        for tblofst in self.tableofsts:
            tabletype = self.type
            if self.type == 9:  # Extension table - converts to another type
                fmt = self.fontfile.readuint16(self.ofst + tblofst)
                assert fmt == 1
                tabletype = self.fontfile.readuint16()
                tblofst += self.fontfile.readuint32()

            if tabletype == 2:  # Pair adjustment positioning
                self.subtables.append(PairAdjustmentSubtable(
                        tblofst + self.ofst, self.fontfile))
            elif tabletype == 4:  # Mark-to-base
                self.subtables.append(MarkToBaseSubtable(
                        tblofst + self.ofst, self.fontfile))
            elif tabletype == 6:  # Mark-to-mark
                self.subtables.append(MarkToMarkSubtable(
                        tblofst + self.ofst, self.fontfile))
            else:
                logging.debug('Unimplemented GPOS Lookup Type %s', self.type)

        self.fontfile.seek(fileptr)  # Put file pointer back

    def __repr__(self):
        return f'<GPOSLookup Type {self.type} {hex(self.ofst)}>'


class PairAdjustmentSubtable:
    ''' Pair Adjustment Table (GPOS Lookup Type 2)
        Informs kerning between pairs of glyphs
    '''
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
            raise ValueError('Invalid posformat in PairAdjustmentSubtable')

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
        return f'<PairAdjustmentSubtable {hex(self.ofst)}>'


def read_markarray_table(ofst, fontfile):
    ''' Read MarkArray table from font file '''
    cnt = fontfile.readuint16(ofst)
    MarkRecord = namedtuple('MarkRecord', ['markclass', 'anchortable'])
    markrecords = []
    for i in range(cnt):
        markclass = fontfile.readuint16()
        anchorofst = fontfile.readuint16()
        ptr = fontfile.tell()
        anchortable = read_anchortable(ofst+anchorofst, fontfile)
        markrecords.append(MarkRecord(markclass, anchortable))
        ptr = fontfile.seek(ptr)
    return markrecords


def read_anchortable(ofst, fontfile):
    ''' Read anchor table from font file '''
    Anchor = namedtuple('Anchor', ['x', 'y', 'anchorpoint', 'xofst', 'yofst'])
    fmt = fontfile.readuint16(ofst)
    point = None
    xofst = yofst = None
    x = fontfile.readint16()
    y = fontfile.readint16()
    if fmt == 2:
        point = fontfile.readuint16()
    elif fmt == 3:
        xofst = fontfile.readuint16()
        yofst = fontfile.readuint16()
        logging.warning('Anchor references Device Table - unimplemented')
    return Anchor(x, y, point, xofst, yofst)


def read_basearray(ofst, fontfile, markclasscount):
    ''' Read BaseArray table used by Mark-to-Base Lookup '''
    basecnt = fontfile.readuint16(ofst)
    basearray = []
    for i in range(basecnt):
        anchortables = []
        for j in range(markclasscount):
            baseanchorofst = fontfile.readuint16()
            ptr = fontfile.tell()
            if baseanchorofst == 0:
                anchortables.append([])
            else:
                anchortables.append(read_anchortable(
                    ofst+baseanchorofst, fontfile))
            fontfile.seek(ptr)
        basearray.append(anchortables)
    return basearray


class MarkToBaseSubtable:
    ''' Mark-To-Base Positioning Table (GPOS Lookup Type 4) '''
    def __init__(self, ofst: int, fontfile: FontReader):
        self.ofst = ofst
        self.fontfile = fontfile

        self.fmt = self.fontfile.readuint16(self.ofst)
        assert self.fmt == 1
        markcovofst = self.fontfile.readuint16()
        basecovofst = self.fontfile.readuint16()
        markclasscnt = self.fontfile.readuint16()
        markarrayofst = self.fontfile.readuint16()
        basearrayofst = self.fontfile.readuint16()

        self.markarray = read_markarray_table(self.ofst+markarrayofst, self.fontfile)
        self.basearray = read_basearray(self.ofst+basearrayofst, self.fontfile, markclasscnt)
        self.markcoverage = Coverage(self.ofst+markcovofst, self.fontfile)
        self.basecoverage = Coverage(self.ofst+basecovofst, self.fontfile)

    def anchor(self, base: int, mark: int) -> Optional[MarktoBaseAnchor]:
        ''' Get anchors for mark glyph with respect to base glyph '''
        markid = self.markcoverage.covidx(mark)
        if markid is None:
            return None

        baseid = self.basecoverage.covidx(base)
        if baseid is None:
            return None

        markanchor = self.markarray[markid]
        baseanchor = self.basearray[baseid][markanchor.markclass]
        return MarktoBaseAnchor(baseanchor, markanchor.anchortable)


class MarkToMarkSubtable:
    ''' Mark-To-Mark Positioning Table (GPOS Lookup Type 6) '''
    def __init__(self, ofst: int, fontfile: FontReader):
        self.ofst = ofst
        self.fontfile = fontfile

        self.fmt = self.fontfile.readuint16(self.ofst)
        assert self.fmt == 1
        mark1covofst = self.fontfile.readuint16()
        mark2covofst = self.fontfile.readuint16()
        markclasscnt = self.fontfile.readuint16()
        mark1arrayofst = self.fontfile.readuint16()
        mark2arrayofst = self.fontfile.readuint16()

        mark2count = self.fontfile.readuint16(self.ofst+mark2arrayofst)
        self.mark2array = []
        for i in range(mark2count):
            anchorofsts = []
            for j in range(markclasscnt):
                anchorofsts.append(self.fontfile.readuint16())
            anchortables = []
            ptr = self.fontfile.tell()
            for anchorofst in anchorofsts:
                anchortables.append(read_anchortable(
                    self.ofst+mark2arrayofst+anchorofst,
                    self.fontfile))
            self.mark2array.append(anchortables)
            self.mark1array = read_markarray_table(
                self.ofst+mark1arrayofst, self.fontfile)
            self.fontfile.seek(ptr)

        self.mark1coverage = Coverage(
            self.ofst+mark1covofst, self.fontfile)
        self.mark2coverage = Coverage(
            self.ofst+mark2covofst, self.fontfile)

    def anchor(self, mark2: int, mark1: int) -> Optional[MarktoBaseAnchor]:
        ''' Get anchors for mark glyph with respect to first mark glyph '''
        mark1id = self.mark1coverage.covidx(mark1)
        if mark1id is None:
            return None

        mark2id = self.mark2coverage.covidx(mark2)
        if mark2id is None:
            return None

        mark1anchor = self.mark1array[mark1id]
        mark2anchor = self.mark2array[mark2id][mark1anchor.markclass]
        return MarktoBaseAnchor(mark2anchor, mark1anchor.anchortable)
