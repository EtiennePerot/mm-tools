#!/usr/bin/env python3

import re
import sys
import threading
import time
import webbrowser
import data

def OpenURL(url):
	webbrowser.open_new_tab(url)
	time.sleep(1) # Necessary to make sure web pages open in a consistent order.

def Search(sourceClass, terms):
	OpenURL(sourceClass.SearchURL(terms))

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

def PopulateAssistSeasonNumber(context):
	if context.kind != data.Context.KIND_SEASON:
		return
	if context.Get('season') is not None:
		return
	default = None
	prompt = 'Season number'
	prefix = context.prefix
	if prefix.isdigit():
		default = int(prefix)
		prompt += ' (default: %d)' % (default,)
	context.kind_data['season'] = int(Ask(context, prompt, ifEmpty=default))
	context.Overwrite()

def PopulateAssistMovieFilename(context):
	if context.kind != data.Context.KIND_MOVIE:
		return
	if context.Get('moviefilename') is not None:
		return
	files = context.media_filenames
	if len(files) == 1:
		return
	print('Found multiple files for movie', context, ':')
	for i, f in enumerate(files):
		print(i + 1, '=', f)
	moviefilename = files[int(Ask(context, 'Index of main movie file (default=1)', ifEmpty=1)) - 1]
	print(context, 'now has selected moviefilename', moviefilename)
	context.kind_data['moviefilename'] = moviefilename
	context.Overwrite()

def PopulateAssistIDsCallbacks(context):
	callbacks = []
	for sourceClass in context.id_sources:
		callbacks.append(EnsureAvailableCallback(context, sourceClass))
	return callbacks

def PopulateAssistIDs(context, callbacks):
	for callback in callbacks:
		callback()
	if data.MAL in context.id_sources and context.Get(data.MAL.KEY) and not context.Get(data.HummingBird.KEY):
		context.kind_data[data.HummingBird.KEY] = data.HummingBird.IDFromMALID(int(context.Get(data.MAL.KEY)))
	context.Overwrite()

def _ArtNeeded(context, includeSubs=True):
	needed = set()
	needed_contexts = []
	imdbs = set()
	for c in (context.GatherSubContexts() if includeSubs else (context,)):
		for art in c.expected_art:
			if c.GetSingle(art) is None:
				if c not in needed_contexts:
					needed_contexts.append(c)
				needed.add(art)
		imdb = c.Get(data.IMDB.KEY)
		if imdb:
			imdbs.add(imdb)
	sources = set()
	for n in needed:
		for sourceClass in (data.TVDB, data.MoviePosterDB, data.ZeroChan, data.MiniTokyo):
			if art in sourceClass.ART_RESOURCE_TYPES:
				sources.add(sourceClass)
	if needed:
		assert sources
	return (
		list(sorted(needed)),
		needed_contexts,
		list(sorted(sources, key=lambda x: x.GATHER_ORDER)),
		list(sorted(imdbs)),
	)

def PopulateGatherArt(context):
	if not context.is_right_under_root or '_temp_gathering_art' in context.kind_data:
		return
	needed, needed_contexts, sources, imdbs = _ArtNeeded(context)
	if not needed:
		return
	for sourceClass in sources:
		Search(sourceClass, context.name_searchable)
	if data.MoviePosterDB in sources:
		for imdb in sorted(imdbs):
			Search(data.MoviePosterDB, imdb)
	print('Needs %s artwork for %s' % (list(needed), needed_contexts))
	print('Dump URLs below, then press Enter.')
	urls = list(map(lambda x: x.rstrip('\''), re.findall(r'https?://(?:(?!https?://)\S)+', input(), re.IGNORECASE)))
	if not urls:
		print('No URLs found. Skipping.')
		return
	context.kind_data['_temp_gathering_art'] = urls
	context.Overwrite()

def PopulateAssistArt(context):
	if not context.is_right_under_root:
		return
	needed, needed_contexts, sources, imdbs = _ArtNeeded(context)
	if not needed:
		return
	assert sources
	try:
		for url in context.kind_data['_temp_gathering_art']:
			OpenURL(url)
	except KeyboardInterrupt:
		print('Interrupted opening URLs.')
		pass
	for c in context.GatherSubContexts():
		needed, _, _, _ = _ArtNeeded(c, includeSubs=False)
		if not needed:
			continue
		print('%s: Art required: %s' % (c, needed))
		existing = []
		for f in c.filenames:
			if re.sub(r'\.[^.]+$', '', f) in data.artResourceFilenames.values():
				continue
			for ext in data.imageExtensions:
				if f.endswith('.' + ext):
					existing.append(f)
		if existing:
			print('%s: Existing potential artwork files:' % (context,))
			for e in existing:
				print('  -', e)
		for art in needed:
			url = Ask(c, 'URL for "%s"' % (art,)).strip()
			for sourceClass in sources:
				url = sourceClass.CleanURL(url)
			c.kind_data[art] = url
		c.Overwrite()

if __name__ == '__main__':
	for path in sys.argv[1:]:
		for context in data.Traverse(path):
			print('Processing:', context)
			callbacks = PopulateAssistIDsCallbacks(context)
			PopulateAssistSeasonNumber(context)
			PopulateAssistMovieFilename(context)
			PopulateAssistIDs(context, callbacks)
			PopulateGatherArt(context)
			PopulateAssistArt(context)
