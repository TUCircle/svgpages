#!/usr/bin/env python2
# coding: utf-8
"""Extract a specifiv 'page' from a multilayer svg document.

Usage:
    svgpages.py <outfile>
    svgpages.py batch [-p <pages>] [-f <format>] <infile>

Options:
    --pages, -p <pages>    Pages to generate. [default: all]
    --format, -f <format>  Output format. [default: svg]

Arguments:
    <outfile>  output file, in <basename>.<page>.<extension> format
    <infile>   input svg file for batch mode

"""

__version__ = "0.1"
from docopt import docopt

import re, os
import subprocess, threading
from lxml import etree
#from copy import copy


INKSCAPE = '/usr/bin/inkscape'

class Pattern:
    def __init__(self, pat):
        self.pat = pat
        self.split()

        if len(self.children) == 0:
            self.classify()

    def split(self):
        child_patterns = self.pat.split(',')
        if len(child_patterns) > 1:
            self.children = [Pattern(p.strip()) for p in child_patterns]
        else:
            self.children = []
        return

    def classify(self):
        if re.match(r'^\d+$', self.pat):
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
        if len(self.children) > 0:
            return any((child.test(num) for child in self.children))
        else:
            if self.ptype == 'num':
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
    Runs the given `popen_args` in a `subprocess.Popen`, and then calls the `callback` function when the subprocess completes.
    `callback` is a callable object, and `popen_args` is a list/tuple of arguments that are unpacked into `subprocess.Popen`.

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

def get_svg(svg_original, page):
    svg = copy(svg_original)

    for element in svg.iterfind('svg:g', namespaces=namespaces):
        if element.attrib.get(ns('inkscape:groupmode'), None) == 'layer':
            if not Pattern(element.attrib.get(ns('inkscape:label'), '')).test(page):
                element.getparent().remove(element)

def navigate(args):
#   from json import dumps
#   print dumps(args, indent=4) + '\n'

    if not args['batch'] and args['<outfile>'] is not None:
        # makefile style
        splitted_outfile = args['<outfile>'].split('.')

        if len(splitted_outfile) < 3:
            raise RuntimeError("outfile must be in <basename>.<page>.<ext> format")

        ext = splitted_outfile[-1]
        if ext not in ['svg', 'pdf', 'pdf_tex']:
            raise RuntimeError("no valid output format. possible values: svg, pdf, pdf_tex")

        try:
            page = int(splitted_outfile[-2])
        except ValueError:
            raise RuntimeError("page number must be a valid integer")

        filename = '.'.join(splitted_outfile[:-2]) + '.svg'
        if not os.path.isfile(filename):
            raise RuntimeError("basename not valid, `{}` does not exist".format(filename))

        make(filename, page, ext)

def make(infile, page, output_format):
    # in any case: generate the svg file first
    svg = etree.parse(infile).getroot()
    pat_re = re.compile(r'\<(?P<pattern>(\d+|\d+-|-\d+|\d+-\d+)(,(\d+|\d+-|-\d+|\d+-\d+))*)\>$')

    for element in svg.iterfind('svg:g', namespaces=namespaces):
        if element.attrib.get(ns('inkscape:groupmode'), None) == 'layer':
            layer_name = element.attrib.get(ns('inkscape:label'), '')
            pat_match = pat_re.search(layer_name)
            if pat_match is None:
                continue
            p = Pattern(pat_match.group(1))
            if not p.test(page):
                element.getparent().remove(element)

    outfile = '{basename}.{page}.svg'.format(
            basename = basename(infile), page = page)

    with open(outfile, 'w') as f:
        f.write(etree.tostring(svg))
        print "{} generated".format(outfile)

    if output_format == 'pdf':
        generate_pdf(outfile)
    elif output_format == 'pdf_tex':
        generate_tex(outfile)

def generate_pdf(svgfile, inkscape_args = []):
    for arg in inkscape_args:
        if arg.startswith('--export-area-'):
            break
    else:
        inkscape_args.append('--export-area-page')

    inkscape_io = [
            '--export-pdf={}.pdf'.format(basename(svgfile)),
            '--file={}'.format(svgfile)]

    inkscape_cmd = [INKSCAPE] + inkscape_args + inkscape_io

    popen_with_callback(inkscape_cmd, callback=lambda: os.remove(svgfile))

def generate_tex(svgfile, inkscape_args = []):
    inkscape_args.append('--export-latex')
    generate_pdf(svgfile, inkscape_args)

if __name__ == "__main__":
    args = docopt(__doc__, version=__version__)
    navigate(args)
