#!/usr/bin/env python2
# coding: utf-8
"""Extract a specific 'page' from a multilayer svg document.

Usage:
    svgpages.py [-d <dpi>] [-i <args>...] <outfile>
    svgpages.py batch [-p <pages>] [-f <format>] [-d <dpi>] [-i <args>...] <infile>

Options:
    --pages, -p <pages>    Pages to generate. [default: all]
    --format, -f <format>  Output format. [default: pdf]
    --dpi, -d <dpi>        Resolution for png export. [default: 90]
    --inkscape, -i <args>  Arguments to be passed to inkscape

Arguments:
    <outfile>  output file, in <basename>[.<page>].<extension> format
    <infile>   input svg file for batch mode

"""

__version__ = "0.1"
from docopt import docopt

import re, os
import subprocess, threading
from lxml import etree


INKSCAPE = '/usr/bin/inkscape'

class Pattern:
    def __init__(self, pat):
        self.pat = pat
        self.split()

        if not self.children:
            self.classify()

    def split(self):
        child_patterns = self.pat.split(',')
        if len(child_patterns) > 1:
            self.children = [Pattern(p.strip()) for p in child_patterns]
        else:
            self.children = False
        return

    def classify(self):
        if self.pat in ['all', '', None]:
            self.ptype = 'all'
        elif re.match(r'^\d+$', self.pat):
            self.ptype = 'num'
        elif re.match(r'^\d+-$', self.pat):
            self.ptype = 'from'
        elif re.match(r'^-\d+$', self.pat):
            self.ptype = 'until'
        elif re.match(r'^\d+-\d+$', self.pat):
            self.ptype = 'from-until'
        else:
            self.ptype = None

    def test(self, num):
        if self.children:
            return any((child.test(num) for child in self.children))
        else:
            if self.ptype == 'all':
                return True
            elif self.ptype == 'num':
                return num == int(self.pat)
            elif self.ptype == 'from':
                return num >= int(self.pat[:-1])
            elif self.ptype == 'until':
                return num <= int(self.pat[1:])
            elif self.ptype == 'from-until':
                lower, upper = tuple((int(x) for x in self.pat.split('-')))
                return num >= lower and num <= upper
            else:
                return False

    def max(self):
        if self.children:
            return max((child.max() for child in self.children))
        else:
            if self.ptype == 'all':
                return 1
            else:
                return max((int(s) for s in re.findall(r'\d+', self.pat)))

    def expand(self, top=None, generator=False):
        if top is None:
            top = self.max()

        ret = (i for i in range(top+1) if self.test(i))
        if generator:
            return ret
        else:
            return list(ret)

def popen_with_callback(popen_cmd, popen_kwargs={}, callback=None):
    """
    Runs the given `popen_cmd` with `popen_kwargs` in a `subprocess.Popen`,
    and then calls the `callback` function when the subprocess completes.

    `callback` is a callable object
    `popen_cmd` is the command list (executable at [0], options at [1:])
    `popen_kwargs` is a dictionary of keyword arguments that is unpacked into `subprocess.Popen`

    seen at
    http://stackoverflow.com/questions/2581817/python-subprocess-callback-when-cmd-exits
    """
    if callback is None:
        def callback():
            pass

    def run_in_thread(cmd, kwargs, callback):
        proc = subprocess.Popen(cmd, **kwargs)
        print "{} started as subprocess (PID {})".format(cmd[0], proc.pid)
        proc.wait()
        callback()
        return

    thread = threading.Thread(target=run_in_thread, args=(popen_cmd, popen_kwargs, callback))
    thread.start()
    # returns immediately after the thread starts
    return thread

def basename(filename, offset=1):
    """
    Returning the filename without the (last n) extension(s).
        basename('foobar.tar.gz')    == 'foobar.tar'
        basename('foobar.tar.gz', 2) == 'foobar'
    """
    return '.'.join(filename.split('.')[:-offset])

namespaces = {
    'dc': "http://purl.org/dc/elements/1.1/",
    'cc': "http://creativecommons.org/ns#",
    'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    'svg': "http://www.w3.org/2000/svg",
    'sodipodi': "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    'inkscape': "http://www.inkscape.org/namespaces/inkscape",
}

def ns(key, namespaces=namespaces):
    lst = key.split(':')
    for idx, item in enumerate(lst[:-1]):
        if item in namespaces:
            lst[idx] = '{{{0}}}'.format(namespaces[item])
    return ''.join(lst)

def check_args(infile=None, output_format=None, pattern=None):
    if infile is not None:
        if not os.path.isfile(infile):
            raise RuntimeError("filename not valid, `{}` does not exist".format(infile))

    if output_format is not None:
        if output_format not in ['svg', 'pdf', 'pdf_tex', 'png']:
            raise RuntimeError("output format not valid. possible values: svg, pdf, pdf_tex")

    if pattern is not None:
        if not re.match(r'((\d+|\d+-|-\d+|\d+-\d+)(,(\d+|\d+-|-\d+|\d+-\d+))*|all)', pattern):
            raise RuntimeError("pattern invalid: {}".format(pattern))

def navigate(args):
#   from json import dumps
#   print dumps(args, indent=4) + '\n'
    if not args['batch'] and args['<outfile>'] is not None:
        # makefile style
        splitted_outfile = args['<outfile>'].split('.')

        if len(splitted_outfile) < 2:
            raise RuntimeError("outfile must be in <basename>[.<page>].<ext> format")
        elif len(splitted_outfile) == 2:
            page = None
            infile = basename(args['<outfile>']) + '.svg'
        else:  # len(splitted_outfile) >= 3
            try:
                page = int(splitted_outfile[-2])
            except ValueError:
                page = None
                infile = basename(args['<outfile>']) + '.svg'
            else:
                infile = basename(args['<outfile>'], 2) + '.svg'

        ext = splitted_outfile[-1]
        check_args(infile, ext)

        make(infile, page, ext, args['--inkscape'])

    elif args['batch'] and args['<infile>'] is not None:
        check_args(args['<infile>'], args['--format'], args['--pages'])

        if args['--pages'] == 'all':
            top = max((Pattern(pat_str).max() for layer, pat_str in layers(args['<infile>'])))
            pages = xrange(1, top + 1)
        else:
            pat = Pattern(args['--pages'])
            pages = pat.expand(generator=True)

        for page in pages:
            make(args['<infile>'], page, args['--format'], args['--inkscape'])

def layers(svgfile):
    if type(svgfile) is str:
        svg = etree.parse(svgfile).getroot()
    else:
        svg = svgfile

    pat_re = re.compile(r'\<(?P<pattern>(\d+|\d+-|-\d+|\d+-\d+)(,(\d+|\d+-|-\d+|\d+-\d+))*)\>$')

    for element in svg.iterfind('svg:g', namespaces=namespaces):
        if element.attrib.get(ns('inkscape:groupmode'), None) == 'layer':
            layer_name = element.attrib.get(ns('inkscape:label'), '')
            pat_match = pat_re.search(layer_name.replace(' ',''))  # ignore spaces
            if pat_match is None:
                pat_str = ''
            else:
                pat_str = pat_match.group('pattern')

            yield element, pat_str

def make(infile, page, output_format, inkscape_args):
    if page is not None:
        # in any case: generate the svg file first
        svg = etree.parse(infile).getroot()

        for element, pat_str in layers(svg):
            if pat_str is None:
                continue
            p = Pattern(pat_str)
            if not p.test(page):
                element.getparent().remove(element)

        svgfile = '{basename}.{page}.svg'.format(
                basename = basename(infile), page = page)
        with open(svgfile, 'w') as f:
            f.write(etree.tostring(svg))
        cleanup = True
    else:
        svgfile = infile
        cleanup = False

    if output_format == 'pdf':
        generate_pdf(svgfile, inkscape_args, cleanup)
    elif output_format == 'pdf_tex':
        generate_tex(svgfile, inkscape_args, cleanup)
    elif output_format == 'png':
        try:
            dpi = int(args['--dpi'])
        except ValueError:
            raise RuntimeError("resolution has to be a valid integer value")
        generate_png(svgfile, dpi, inkscape_args, cleanup)

def generate_output(svgfile, inkscape_args = [], cleanup = False):
    for arg in inkscape_args:
        if arg.startswith('--export-area-'):
            break
    else:
        inkscape_args.append('--export-area-page')

    inkscape_args.append('--file={}'.format(svgfile))

    inkscape_cmd = [INKSCAPE] + inkscape_args

    def callback():
        if cleanup:
            os.remove(svgfile)

    popen_with_callback(inkscape_cmd, callback=callback)

def generate_png(svgfile, dpi = None, inkscape_args = [], cleanup = False):
    inkscape_args.append('--export-png={}.png'.format(basename(svgfile)))
    if dpi is not None:
        inkscape_args.append('--export-dpi={}'.format(dpi))
    generate_output(svgfile, inkscape_args, cleanup)

def generate_pdf(svgfile, inkscape_args = [], cleanup = False):
    inkscape_args.append('--export-pdf={}.pdf'.format(basename(svgfile)))
    generate_output(svgfile, inkscape_args, cleanup)

def generate_tex(svgfile, inkscape_args = [], cleanup = False):
    inkscape_args.append('--export-latex')
    generate_pdf(svgfile, inkscape_args, cleanup)

if __name__ == "__main__":
    args = docopt(__doc__, version=__version__)
    navigate(args)
