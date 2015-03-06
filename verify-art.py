#!/usr/bin/env python3

import os
import sys
from PIL import Image
import data

_expectedRatios = {
	'banner': lambda r: r > 3.0,
	'background': lambda r: r < 2.0,
	'poster': lambda r: r < 1.0,
}

def _VerifyFile(context, art, path):
	comparison = _expectedRatios[art]
	width, height = Image.open(path).size
	ratio = float(width) / float(height)
	if not comparison(ratio):
		raise RuntimeError('%s: Artwork for %s has ratio %0.2f (%dx%d): %s' % (context, art, ratio, width, height, path))

def VerifyArt(context):
	for art in context.expected_art:
		for ext in data.imageExtensions:
			path = os.path.join(context.path, data.artResourceFilenames[art] + '.' + ext)
			if os.path.exists(path):
				_VerifyFile(context, art, path)

if __name__ == '__main__':
	for path in sys.argv[1:]:
		for context in data.Traverse(path):
			print('Verifying:', context)
			VerifyArt(context)
