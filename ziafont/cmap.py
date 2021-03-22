''' Font CMAP table - translate character into a glyph ID '''

from typing import Sequence


class Cmap12:
    ''' Format 12 cmap Table '''
    def __init__(self, platform: str, platformid: int, startcodes: Sequence[int],
                 endcodes: Sequence[int], glyphstarts: Sequence[int]):
        self.platform = platform
        self.platformid = platformid
        self.startcodes = startcodes
        self.endcodes = endcodes
        self.glyphstarts = glyphstarts

    def __repr__(self):
        return f'<Cmap Format 12: {self.platform} id={self.platformid}'

    def glyphid(self, char: str) -> int:
        ''' Get glyph index from a character '''
        charid = ord(char)

        for endid, end in enumerate(self.endcodes):
            if end >= charid:
                break
        else:
            return 0  # Character not found

        if self.startcodes[endid] > charid:
            return 0

        # Char was found
        ofst = charid - self.startcodes[endid]
        return self.glyphstarts[endid] + ofst


class Cmap4:
    ''' Format 4 cmap Table '''
    def __init__(self, platform: str, platformid: int, startcodes: Sequence[int],
                 endcodes: Sequence[int], idrangeoffset: Sequence[int],
                 iddeltas: Sequence[int], glyphidarray: Sequence[int]):
        self.platform = platform
        self.platformid = platformid
        self.startcodes = startcodes
        self.endcodes = endcodes
        self.idrangeoffset = idrangeoffset
        self.iddeltas = iddeltas
        self.glyphidarray = glyphidarray

    def __repr__(self):
        return f'<Cmap Format 4: {self.platform} id={self.platformid}'

    def glyphid(self, char: str) -> int:
        ''' Get glyph index from a character '''
        charid = ord(char)

        for endid, end in enumerate(self.endcodes):
            if end >= charid:
                break
        else:
            return 0  # Character not found (missing glyph)

        if self.startcodes[endid] > charid:
            return 0

        if self.idrangeoffset[endid] != 0:
            segcount = len(self.startcodes)
            idx = endid - segcount + self.idrangeoffset[endid]//2 + (charid - self.startcodes[endid])
            gid = self.glyphidarray[idx]
            glyphid = self.iddeltas[endid] + gid if gid > 0 else 0
        else:
            glyphid = (self.iddeltas[endid] + charid) % 0x10000
        return glyphid
