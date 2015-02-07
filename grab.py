#!/usr/bin/env python3

import imghdr
import os
import sys
import mimetypes
import requests
import data

RESOURCES = {
	'banner': 'banner',
	'poster': 'poster',
	'background': 'fanart',
}
IMAGE_EXTENSIONS = ('png', 'jpg')
IMAGE_EXTENSION_MAPPINGS = {'jpeg': 'jpg', 'jpe': 'jpg'}

def Grab(context):
	for key, filename in RESOURCES.items():
		source = context.Get(key)
		if source is None or source == 'None':
			print('Warning: Undefined', key, 'in', context)
			continue
		if any(os.path.isfile(os.path.join(context.path, filename + '.' + ext)) for ext in IMAGE_EXTENSIONS):
			continue
		try:
			request = requests.get(source)
			extension = mimetypes.guess_extension(request.headers['content-type']).lower().lstrip('.')
			content = request.content
		except requests.exceptions.MissingSchema:
			# No schema specified, so it must be a local file.
			f = open(os.path.join(context.path, source), 'rb')
			content = f.read()
			f.close()
			extension = imghdr.what(None, h=content)
		extension = IMAGE_EXTENSION_MAPPINGS.get(extension, extension)
		if extension not in IMAGE_EXTENSIONS:
			print('Warning:', source, 'maps to unknown extension', extension)
			continue
		target = os.path.join(context.path, filename + '.' + extension)
		assert not os.path.exists(target)
		f = open(target, 'wb')
		f.write(content)
		f.close()
		print('Grabbed', source, 'to', target)

if __name__ == '__main__':
	for path in sys.argv[1:]:
		for context in data.Traverse(path):
			print('Grabbing:', context)
			Grab(context)
