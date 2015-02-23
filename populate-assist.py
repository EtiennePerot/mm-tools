#!/usr/bin/env python3

import sys
import threading
import time
import webbrowser
import data

def Search(sourceClass, terms):
	webbrowser.open_new_tab(sourceClass.SearchURL(terms))
	time.sleep(1) # Necessary to makesure web pages open in a consistent order.

def Ask(context, prompt, ifEmpty='None'):
	print('-' * 8)
	return str(input('%s: %s: ' % (context, prompt)) or ifEmpty)

def EnsureAvailableCallback(context, sourceClass):
	source = context.GetSource(sourceClass)
	if source:
		return lambda: None
	print('%s: Unknown value for "%s". Opening search page.' % (context, sourceClass.KEY))
	Search(sourceClass, context.name_searchable)
	default = []
	def backgroundFetch():
		try:
			default.append(sourceClass.GetBestMatch(context.name_searchable))
		except Exception as e:
			print('Exception while retrieving best match for %s: %s' % (context, e))
			default.append(None)
	threading.Thread(target=backgroundFetch).start()
	def callback():
		while not default:
			time.sleep(.1)
		value = Ask(context, 'Value for "%s" ("None" for None, default="%s")' % (sourceClass.KEY, default[0]), ifEmpty=default[0])
		if value.startswith('http://') or value.startswith('https://'):
			value = sourceClass.ParseOpenURLToID(sourceClass.CleanURL(value))
		if value is not None and value.isdigit():
			value = int(value)
		context.kind_data[sourceClass.KEY] = value
	return callback

def PopulateAssistIDs(context):
	sources = {
		data.Context.KIND_SERIES: (data.TVDB,),
		data.Context.KIND_SEASON: (data.AniDB, data.MAL, data.IMDB),
		data.Context.KIND_MOVIE: (data.AniDB, data.MAL, data.IMDB),
		data.Context.KIND_OVA: (data.AniDB, data.MAL),
		data.Context.KIND_SOUNDTRACK: (),
	}[context.kind]
	callbacks = []
	for sourceClass in sources:
		callbacks.append(EnsureAvailableCallback(context, sourceClass))
	for callback in callbacks:
		callback()
	context.Overwrite()

def PopulateAssistArt(context):
	missing = []
	sources = set()
	need = {
		data.Context.KIND_SERIES: ('background', 'banner', 'poster'),
		data.Context.KIND_SEASON: ('background', 'banner', 'poster'),
		data.Context.KIND_MOVIE: ('background', 'poster'),
		data.Context.KIND_OVA: ('background', 'poster'),
		data.Context.KIND_SOUNDTRACK: (),
	}[context.kind]
	for art in need:
		if context.GetSingle(art):
			continue
		missing.append(art)
		for sourceClass in (data.TVDB, data.MoviePosterDB, data.ZeroChan, data.MiniTokyo):
			if art in sourceClass.ART_RESOURCE_TYPES:
				sources.add(sourceClass)
	if not missing:
		return
	assert sources
	for sourceClass in sources:
		Search(sourceClass, context.name_searchable)
	if data.MoviePosterDB in sources:
		# MoviePosterDB also supports searching by IMDB ID.
		imdbs = []
		for sub in context.GatherSubContexts():
			imdb = sub.Get('imdb')
			if imdb and imdb not in imdbs:
				imdbs.append(imdb)
		for imdb in sorted(imdbs):
			Search(data.MoviePosterDB, imdb)
	for art in missing:
		url = Ask(context, 'URL for "%s"' % (art,))
		for sourceClass in sources:
			url = sourceClass.CleanURL(url)
		context.kind_data[art] = url
	context.Overwrite()

if __name__ == '__main__':
	for path in sys.argv[1:]:
		for context in data.Traverse(path):
			print('Processing:', context)
			PopulateAssistIDs(context)
			#PopulateAssistArt(context)
