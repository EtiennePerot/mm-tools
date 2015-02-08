#!/usr/bin/env python3

import sys
import time
import webbrowser
import data

def EnsureAvailableCallback(context, d, sourceClass):
	source = context.GetSource(sourceClass)
	if source:
		return lambda: None
	print('%s: Unknown value for "%s". Opening search page.' % (context, sourceClass.KEY))
	webbrowser.open_new_tab(sourceClass.SearchURL(context.name_searchable))
	time.sleep(1) # Necessary to makesure web pages open in a consistent order.
	def callback():
		value = input('%s: Value for "%s": ' % (context, sourceClass.KEY)) or 'None'
		if value.startswith('http://') or value.startswith('https://'):
			value = sourceClass.ParseOpenURLToID(value)
		if value is not None and value.isdigit():
			value = int(value)
		d[sourceClass.KEY] = value
	return callback

def PopulateAssist(context):
	sources = []
	if context.kind == data.Context.KIND_SERIES:
		sources.append((context.series, data.TVDB))
	elif context.kind == data.Context.KIND_SEASON:
		sources.append((context.season, data.AniDB))
		sources.append((context.season, data.MAL))
		sources.append((context.season, data.IMDB))
	elif context.kind == data.Context.KIND_MOVIE:
		sources.append((context.movie, data.AniDB))
		sources.append((context.movie, data.MAL))
		sources.append((context.movie, data.IMDB))
	elif context.kind == data.Context.KIND_OVA:
		sources.append((context.ova, data.AniDB))
		sources.append((context.ova, data.MAL))
	callbacks = []
	for d, sourceClass in sources:
		callbacks.append(EnsureAvailableCallback(context, d, sourceClass))
	for callback in callbacks:
		callback()
	context.Overwrite()

if __name__ == '__main__':
	for path in sys.argv[1:]:
		for context in data.Traverse(path):
			print('Processing:', context)
			PopulateAssist(context)
