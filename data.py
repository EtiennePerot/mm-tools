import os
import re
import urllib.parse

import bs4
import requests
import yaml

class Source(object):
	KEY = None
	SEARCH_URL = None
	OPEN_URL = None
	PARSE_OPEN_URL_TO_ID = None
	ART_RESOURCE_TYPES = ()

	@classmethod
	def SearchURL(cls, terms):
		return cls.SEARCH_URL % (urllib.parse.quote(terms),)
	@classmethod
	def GetBestMatch(cls, terms):
		searchURL = cls.SearchURL(terms)
		content = requests.get(searchURL, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36'}, timeout=5).text
		soup = bs4.BeautifulSoup(content)
		for tag in soup.find_all('a'):
			try:
				url = urllib.parse.urljoin(searchURL, tag['href'])
				res = cls.PARSE_OPEN_URL_TO_ID.search(url)
				if not res:
					continue
				id = cls.ParseOpenURLToID(res.group(0))
				if id:
					return id
			except KeyError:
				pass
		return None
	@classmethod
	def OpenURL(cls, id):
		return cls.OPEN_URL % (urllib.parse.quote(str(id)),)
	@classmethod
	def ParseOpenURLToID(cls, url):
		res = cls.PARSE_OPEN_URL_TO_ID.search(url)
		return res.group(1) if res else None
	@classmethod
	def CleanURL(cls, url):
		return url

	def __init__(self, id):
		self._id = id

	def __str__(self):
		return '%s<%s>' % (self.__class__.__name__, self._id)

class TVDB(Source):
	KEY = 'tvdb'
	SEARCH_URL = 'http://thetvdb.com/?string=%s&tab=listseries&function=Search'
	OPEN_URL = 'http://thetvdb.com/?tab=series&id=%s'
	PARSE_OPEN_URL_TO_ID = re.compile(r'://[^/]*thetvdb.com/.*[?&]id=(\d+)', re.IGNORECASE)
	ART_RESOURCE_TYPES = ('background', 'banner', 'poster')

class AniDB(Source):
	KEY = 'anidb'
	SEARCH_URL = 'http://anidb.net/perl-bin/animedb.pl?show=animelist&adb.search=%s'
	OPEN_URL = 'http://anidb.net/perl-bin/animedb.pl?show=anime&aid=%s'
	PARSE_OPEN_URL_TO_ID = re.compile(r'://[^/]*anidb.net/.*animedb.*[?&]aid=(\d+)', re.IGNORECASE)

class MAL(Source):
	KEY = 'mal'
	SEARCH_URL = 'http://myanimelist.net/anime.php?q=%s'
	OPEN_URL = 'http://myanimelist.net/anime/%s'
	PARSE_OPEN_URL_TO_ID = re.compile(r'://[^/]*myanimelist.net/anime/(\d+)', re.IGNORECASE)

	@classmethod
	def _GetAPICreds(cls):
		import mal_api_config
		return mal_api_config.api_user, mal_api_config.api_password
	@classmethod
	def GetBestMatch(cls, terms):
		return None # Return None for now; Incapsula is too easy to trip up.
		soup = bs4.BeautifulSoup(requests.get('http://myanimelist.net/api/anime/search.xml?q=%s' % (urllib.parse.quote(terms),), auth=cls._GetAPICreds(), headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36'}, timeout=5).text)
		entries = soup.find_all('id')
		return entries[0].text if entries else None

class IMDB(Source):
	KEY = 'imdb'
	SEARCH_URL = 'http://www.imdb.com/find?s=tt&q=%s'
	OPEN_URL = 'http://www.imdb.com/title/%s'
	PARSE_OPEN_URL_TO_ID = re.compile(r'://[^/]*imdb.com/title/(tt\d+)', re.IGNORECASE)

class MoviePosterDB(Source):
	SEARCH_URL = 'http://www.movieposterdb.com/search/?query=%s'
	ART_RESOURCE_TYPES = ('poster',)

class ZeroChan(Source):
	SEARCH_URL = 'http://www.zerochan.net/search?q=%s'
	ART_RESOURCE_TYPES = ('background', 'poster')

class MiniTokyo(Source):
	SEARCH_URL = 'http://www.minitokyo.net/search?q=%s'
	ART_RESOURCE_TYPES = ('background', 'poster')

	_CLEAN_QUERY_ON_IMAGES = re.compile(r'^([^:/]+://static\.minitokyo\.[^?]+/downloads/[^?]+)\?.*$', re.IGNORECASE)
	@classmethod
	def CleanURL(cls, url):
		return cls._CLEAN_QUERY_ON_IMAGES.sub(r'\1', url)

infoFile = '.info'

class Context(object):
	KIND_SERIES = 'series'
	KIND_SEASON = 'season'
	KIND_MOVIE = 'movie'
	KIND_OVA = 'ova'
	KIND_SOUNDTRACK = 'soundtrack'

	KNOWN_KEYS = frozenset((
		'name',
		'background', 'banner', 'poster',
		'anidb', 'mal', 'tvdb', 'imdb',
	))

	_SEARCHABLE_FILTER = re.compile(r'[^\s\w]')
	_SEARCHABLE_JOIN = re.compile(r'\s+')

	def __init__(self, parent, path):
		self._parent = parent
		self._path = path
		self._series = {}
		self._season = {}
		self._movie = {}
		self._ova = {}
		self._soundtrack = {}
		self._kind = None

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
	def ova(self):
		return self._ova
	@property
	def soundtrack(self):
		return self._soundtrack
	@property
	def kind(self):
		return self._kind
	@property
	def kind_data(self):
		return {
			self.KIND_SERIES: self.series,
			self.KIND_SEASON: self.season,
			self.KIND_MOVIE: self.movie,
			self.KIND_OVA: self.ova,
			self.KIND_SOUNDTRACK: self.soundtrack,
		}[self.kind]
	@property
	def name(self):
		return self.Get('name')
	@property
	def name_noprefix(self):
		name = self.name
		if ' - ' in name:
			name = name[name.index(' - ') + 3:]
		return name
	@property
	def name_searchable(self):
		return self._SEARCHABLE_JOIN.sub(' ', self._SEARCHABLE_FILTER.sub(' ', self.name_noprefix))

	def GetSingle(self, key):
		return self.kind_data.get(key)
	def Get(self, key):
		return self.soundtrack.get(key, self.ova.get(key, self.movie.get(key, self.season.get(key, self.series.get(key)))))

	def GetSource(self, source):
		id = self.Get(source.KEY)
		if id is None:
			return None
		return source(id)

	def sanityCheck(self):
		for d in self.soundtrack, self.ova, self.movie, self.season, self.series:
			for k in d.keys():
				if k not in self.KNOWN_KEYS:
					raise RuntimeError('Unknown key "%s" in %s' % (k, self))

	def SubContext(self, path, data):
		"""Returns a new Context with overlaid data."""
		folderName = os.path.basename(path)
		sub = self.__class__(self, path)
		sub._series = self.series.copy()
		sub._season = self.season.copy()
		sub._movie = self.movie.copy()
		sub._ova = self.ova.copy()
		sub._soundtrack = self.soundtrack.copy()
		if 'series' in data:
			series = data['series'] or {}
			sub._series.update(series)
			sub._series['name'] = series.get('name', folderName)
			sub._kind = self.KIND_SERIES
		if 'season' in data:
			season = data['season'] or {}
			sub._season.update(season)
			sub._season['name'] = season.get('name', folderName)
			sub._kind = self.KIND_SEASON
		if 'movie' in data:
			movie = data['movie'] or {}
			sub._movie.update(movie)
			sub._movie['name'] = movie.get('name', folderName)
			sub._kind = self.KIND_MOVIE
		if 'ova' in data:
			ova = data['ova'] or {}
			sub._ova.update(ova)
			sub._ova['name'] = ova.get('name', folderName)
			sub._kind = self.KIND_OVA
		if 'soundtrack' in data:
			soundtrack = data['soundtrack'] or {}
			sub._soundtrack.update(soundtrack)
			sub._soundtrack['name'] = soundtrack.get('name', folderName)
			sub._kind = self.KIND_SOUNDTRACK
		sub.sanityCheck()
		return sub

	def GatherSubContexts(self):
		yield self
		yield from traverse(self.path, self)

	def Overwrite(self):
		finalData = {}
		for key, dataFunc in {'series': lambda x: x.series, 'season': lambda x: x.season, 'movie': lambda x: x.movie, 'ova': lambda x: x.ova, 'soundtrack': lambda x: x.soundtrack}.items():
			if self._parent is None or dataFunc(self) != dataFunc(self._parent):
				data = dataFunc(self).copy()
				if 'name' in data:
					del data['name']
				if not data: # Empty dictionary
					data = None
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
		sub = 'ROOT' if self.kind == self.KIND_SERIES else self.name
		return '%s :: %s (%s)' % (series, sub, self.kind)

def readYAML(path):
	f = open(path, 'r')
	raw = f.read().replace('\t', '  ')
	f.close()
	return yaml.load(raw)

def traverse(path, context):
	"""Traverse path and its subdirectories, picking up files as it goes. Yields Contexts."""
	entries = list(sorted(os.listdir(path)))
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
