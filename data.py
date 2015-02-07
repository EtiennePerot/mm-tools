import os
import urllib.parse
import yaml

class Source(object):
	KEY = None
	SEARCH_URL = None
	OPEN_URL = None

	@classmethod
	def SearchURL(cls, terms):
		return cls.SEARCH_URL % (urllib.parse.quote(terms),)
	@classmethod
	def OpenURL(cls, id):
		return cls.OPEN_URL % (urllib.parse.quote(str(id)),)

	def __init__(self, id):
		self._id = id

	def __str__(self):
		return '%s<%s>' % (self.__class__.__name__, self._id)

class TVDB(Source):
	KEY = 'tvdb'
	SEARCH_URL = 'http://thetvdb.com/?string=%s&tab=listseries&function=Search'
	OPEN_URL = 'http://thetvdb.com/?tab=series&id=%s'

class AniDB(Source):
	KEY = 'anidb'
	SEARCH_URL = 'http://anidb.net/perl-bin/animedb.pl?show=animelist&adb.search=%s'
	OPEN_URL = 'http://anidb.net/perl-bin/animedb.pl?show=anime&aid=%s'

class MAL(Source):
	KEY = 'mal'
	SEARCH_URL = 'http://myanimelist.net/anime.php?q=%s'
	OPEN_URL = 'http://myanimelist.net/anime/%s'

class IMDB(Source):
	KEY = 'imdb'
	SEARCH_URL = 'http://www.imdb.com/find?s=tt&q=%s'
	OPEN_URL = 'http://www.imdb.com/title/%s'

infoFile = '.info'

class Context(object):
	KIND_SERIES = 'kSeries'
	KIND_SEASON = 'kSeason'
	KIND_MOVIE = 'kMovie'

	KNOWN_KEYS = frozenset((
		'name',
		'background', 'banner', 'poster',
		'anidb', 'mal', 'tvdb', 'imdb',
	))

	def __init__(self, parent, path):
		self._parent = parent
		self._path = path
		self._series = {}
		self._season = {}
		self._movie = {}

	@property
	def path(self):
		return self._path
	@property
	def info_path(self):
		return os.path.join(self.path, infoFile)
	@property
	def series(self):
		return self._series
	@property
	def season(self):
		return self._season
	@property
	def movie(self):
		return self._movie
	@property
	def kind(self):
		if 'name' in self.movie:
			return self.KIND_MOVIE
		if 'name' in self.season:
			return self.KIND_SEASON
		if 'name' in self.series:
			return self.KIND_SERIES
	@property
	def name(self):
		return self.Get('name')
	@property
	def name_noprefix(self):
		name = self.name
		if ' - ' in name:
			name = name[name.index(' - ') + 3:]
		return name

	def Get(self, key):
		return self.movie.get(key, self.season.get(key, self.series.get(key)))

	def GetSource(self, source):
		id = self.Get(source.KEY)
		if id is None:
			return None
		return source(id)

	def sanityCheck(self):
		for d in self.movie, self.season, self.series:
			for k in d.keys():
				if k not in self.KNOWN_KEYS:
					raise RuntimeError('Unknown key "%s" in %s' % (k, ))

	def SubContext(self, path, data):
		"""Returns a new Context with overlaid data."""
		folderName = os.path.basename(path)
		sub = self.__class__(self, path)
		sub._series = self.series.copy()
		sub._season = self.season.copy()
		sub._movie = self.movie.copy()
		if 'series' in data:
			series = data['series'] or {}
			sub._series.update(series)
			sub._series['name'] = series.get('name', folderName)
		if 'season' in data:
			season = data['season'] or {}
			sub._season.update(season)
			sub._season['name'] = season.get('name', folderName)
		if 'movie' in data:
			movie = data['movie'] or {}
			sub._movie.update(movie)
			sub._movie['name'] = movie.get('name', folderName)
		sub.sanityCheck()
		return sub

	def Overwrite(self):
		finalData = {}
		for key, dataFunc in {'series': lambda x: x.series, 'season': lambda x: x.season, 'movie': lambda x: x.movie}.items():
			if self._parent is None or dataFunc(self) != dataFunc(self._parent):
				data = dataFunc(self).copy()
				if 'name' in data:
					del data['name']
				finalData[key] = data
		if not finalData:
			return
		currentData = readYAML(self.info_path)
		if currentData == finalData:
			return
		old = yaml.dump(currentData, default_flow_style=False).replace('  ', '\t')
		serialized = yaml.dump(finalData, default_flow_style=False).replace('  ', '\t')
		print('Rewriting %s.\nOld data:\n%s\nNew data:\n%s' % (self, old, serialized))
		f = open(self.info_path, 'w')
		f.write(serialized)
		f.close()

	def __str__(self):
		"""String representation."""
		series = self.series.get('name', 'UNKNOWN_SERIES')
		if 'name' in self.movie:
			return '%s :: %s (movie)' % (series, self.movie['name'])
		if 'name' in self.season:
			return '%s :: %s (season)' % (series, self.season['name'])
		return '%s :: %s' % (series, 'ROOT')

def readYAML(path):
	f = open(path, 'r')
	raw = f.read().replace('\t', '  ')
	f.close()
	return yaml.load(raw)

def traverse(path, context):
	"""Traverse path and its subdirectories, picking up files as it goes. Yields Contexts."""
	entries = os.listdir(path)
	if infoFile in entries:
		data = readYAML(os.path.join(path, infoFile))
		context = context.SubContext(path, data)
		yield context
	for entry in entries:
		fullEntry = os.path.join(path, entry)
		if os.path.isdir(fullEntry):
			yield from traverse(fullEntry, context)

def Traverse(path):
	path = os.path.abspath(path)
	yield from traverse(path, Context(None, path))
