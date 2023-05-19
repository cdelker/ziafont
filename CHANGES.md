# Release notes

### 0.6 - 2023-05-19

- Enabled SSTY font feature (math script glyph alternatives) 
- Fixed vertical alignment of glyphs taller than the font maximum (eg Math Assembly Glyphs)
- Updates for consistency with ziamath


### 0.5 - 2022-11-05

- Added support for CFF font table (usually .otf fonts)
- Implemented ligature substitution and partial support for GSUB table
- Implemented mark-to-mark and mark-to-base GPOS positioning
- Enhanced glyph.test() mode
- Fix index errors when reading some fonts
- Only specify font by filename
- Strip empty path elements from SVG


### 0.4 - 2022-06-20

- Added global configuration object
- Added rotation parameter
- Added color parameter
- Renamed str2svg to text


### 0.3 - 2022-05-28

- Locate fonts by name from system font paths
- Read font NAME table
- Added Text class for drawing multiline text with a font
- Fall back on default font when given font name not found
- Fix glyph paths that start with a control point
- Add parameter for SVG decimal precision
- Fix kerning on fonts with no scripts table
- Removed whitespace from getsize return value
- Changed default built-in font to DejaVuSans


### 0.2 - 2021_07_05

- Added an option to use SVG1.x format for compatibility since SVG2.0 is not fully supported in all browsers/renderers yet.


### 0.1 - 2021_03_22

Initial Release
