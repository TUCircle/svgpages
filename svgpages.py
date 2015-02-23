#!/usr/bin/env python2
# coding: utf-8
"""Split svg files into layers.

Usage:
    svglayers.py <file>

Options:
    <file>  svg file to convert

"""

__version__ = "0.1"
from docopt import docopt

import re
from lxml import etree
from copy import copy


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


class Organizer:
    def __init__(self, layers):
        self.layers = layers

    def validate_name(self, layer):
        preg = re.compile(r'\<(?P<pattern>(\d+|\d+-|-\d+|\d+-\d+)(, ?(\d+|\d+-|-\d+|\d+-\d+))*)\>$')
        return preg.match(layer.attrib.get(ns('inkscape:label'), '')) is not None

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

def main():
    svg = etree.parse(args['<file>']).getroot()

    patterns = []
    for element in svg.iterfind('svg:g', namespaces=namespaces):
        if element.attrib.get(ns('inkscape:groupmode'), None) == 'layer':
            print element.attrib.get(ns('inkscape:label'), 'ERROR: missing layer label')

if __name__ == "__main__":
    args = docopt(__doc__, version=__version__)
    main()
