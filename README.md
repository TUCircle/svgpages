# svgpages
Split a multilayer svg into multiple single pages, based on layer names.

## Concept
The pages on which an Inkscape layer should be shown have to be specified in the layer name.
This is being done appending a `<pattern>` string to the name, including the pointy brackets.

The svg file can then be parsed by `svgpages.py`, creating one or more output files.

### Pattern Syntax
A pattern consists of one or more comma-separated subpatterns as described below:

- `n`: shown on page _n_ only
- `-n`: shown on pages _1_ to _n_, including _n_
- `n-`: shown on page _n_ and following
- `m-n`: shown on all pages between _m_ and _n_, including _m_ and _n_

### Output Formats
Currently, three different formats are supported:

- `svg`: basic functionality, an svg file stripped of invisible layers is created.
    This is being done in all cases, the other formats depend on the svg.
- `pdf`: pdf file, converted using Inkscape
- `pdf_tex`: Using Inkscape, graphics can be [exported for LaTeX use][inkscape-pdftex].
    This creates two different files, a `.pdf` file without text
    and a `.pdf_tex` file, which typesets the text and includes the pdf file.
- `png`: create png image, by default with 90 dpi.

[inkscape-pdftex]: http://tug.ctan.org/tex-archive/info/svg-inkscape/InkscapePDFLaTeX.pdf

### Modes of Operation
There is (currently) two modes of operation.
In both modes a list of Inkscape arguments can be given using `-i <arg>`.

#### Makefile-Style
The program is invoked by `svgpages.py <basename>[.<page>].<format_extension>`.
This creates an output file, where format and page are defined in the filename.

`<basename>` is the filename without `.svg`-extension, e.g. `img.small.svg` would result in `img.small`.
`<format_extension>` can be one of the output formats, `<page>` specifies the page to render.
If `<page>` is omitted, the file is being converted without filtering the layers.

#### Batch Mode
In batch mode multiple output files can be created at once:

`svgpages.py batch [-p <pages>] [-f <format>] [-d <dpi>] <infile>.svg`

`<pages>` is a pattern as defined above, but can additionally be `all` (defauklt).
The `<format>` can be as specified in the _Output Formats_ section, default `pdf`.
Resolution for png export can be set by `<dpi>`.
