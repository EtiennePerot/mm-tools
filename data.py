import math
import os
import re
import urllib.parse
import sys

import bs4
import requests
import yaml

# TVDB API
sys.path.append(os.path.join(os.path.dirname(__file__), 'submodules/tvdb_api'))
import tvdb_api

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

	@property
	def id(self):
		return self._id

	def __str__(self):
		return '%s<%s>' % (self.__class__.__name__, self._id)

class TVDB(Source):
	KEY = 'tvdb'
	GATHER_ORDER = 0
	SEARCH_URL = 'http://thetvdb.com/?string=%s&tab=listseries&function=Search'
	OPEN_URL = 'http://thetvdb.com/?tab=series&id=%s'
	PARSE_OPEN_URL_TO_ID = re.compile(r'://[^/]*thetvdb.com/.*[?&]id=(\d+)', re.IGNORECASE)
	ART_RESOURCE_TYPES = ('background', 'banner', 'poster')
	API = tvdb_api.Tvdb(language='en')

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
		import api_config
		return api_config.mal_api_user, api_config.mal_api_password
	@classmethod
	def GetBestMatch(cls, terms):
		return None # Return None for now; Incapsula is too easy to trip up.
		soup = bs4.BeautifulSoup(requests.get('http://myanimelist.net/api/anime/search.xml?q=%s' % (urllib.parse.quote(terms),), auth=cls._GetAPICreds(), headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36'}, timeout=5).text)
		entries = soup.find_all('id')
		return entries[0].text if entries else None

class HummingBird(Source):
	KEY = 'hummingbird'
	SEARCH_URL = 'https://hummingbird.me/search?query=%s'
	OPEN_URL = 'https://hummingbird.me/anime/%s'
	PARSE_OPEN_URL_TO_ID = re.compile(r'://[^/]*hummingbird.me/anime/([^/]+)', re.IGNORECASE)

	@classmethod
	def _GetAPIKey(cls):
		import api_config
		return api_config.hummingbird_api_key

	@classmethod
	def IDFromMALID(cls, malid):
		return requests.get('https://hummingbird.me/api/v2/anime/myanimelist:%d' % (malid,), headers={'X-Client-Id': cls._GetAPIKey()}).json()['anime']['id']

	def Lookup(self):
		return requests.get('https://hummingbird.me/api/v2/anime/%d' % (self.id,), headers={'X-Client-Id': self._GetAPIKey()}).json()

class IMDB(Source):
	KEY = 'imdb'
	SEARCH_URL = 'http://www.imdb.com/find?s=tt&q=%s'
	OPEN_URL = 'http://www.imdb.com/title/%s'
	PARSE_OPEN_URL_TO_ID = re.compile(r'://[^/]*imdb.com/title/(tt\d+)', re.IGNORECASE)

class MoviePosterDB(Source):
	GATHER_ORDER = 1
	SEARCH_URL = 'http://www.movieposterdb.com/search/?query=%s'
	ART_RESOURCE_TYPES = ('poster',)

class ZeroChan(Source):
	GATHER_ORDER = 2
	SEARCH_URL = 'http://www.zerochan.net/search?q=%s'
	ART_RESOURCE_TYPES = ('background', 'poster')

class MiniTokyo(Source):
	GATHER_ORDER = 3
	SEARCH_URL = 'http://www.minitokyo.net/search?q=%s'
	ART_RESOURCE_TYPES = ('background', 'poster')

	_CLEAN_QUERY_ON_IMAGES = re.compile(r'^([^:/]+://static\.minitokyo\.[^?]+/downloads/[^?]+)\?.*$', re.IGNORECASE)
	@classmethod
	def CleanURL(cls, url):
		return cls._CLEAN_QUERY_ON_IMAGES.sub(r'\1', url)

infoFile = '.info'
rootFile = '.root'
mediaExtension = '.mkv'
nfoExtension = '.nfo'
imageExtensions = ('png', 'jpg')
imageExtensionMappings = {'jpeg': 'jpg', 'jpe': 'jpg'}
artResourceFilenames = {
	'banner': 'banner',
	'poster': 'poster',
	'background': 'fanart',
}

class Episode(object):
	_EPISODE_NUMBER_GUESS_REGEXES = (
		r'(?:[^0-9a-z]|\b|(?:(?:[^0-9a-z]|\b)se?\d{1,3}))ep?(\d{2,3})(?!-bit)(?:v\d+)?(?:[^0-9a-z]|\b)',
		r'(?:[^0-9a-z]|\b|(?:(?:[^0-9a-z]|\b)se?\d{1,3}[-_\s]))(\d{2,3})(?!-bit)(?:v\d+)?(?:[^0-9a-z]|\b)',
		r'[^[a-z0-9](\d{2,3})(?!-bit)(?:v\d+)?(?:[^0-9a-z]|\b)',
	)

	@classmethod
	def GuessEpisodeNumber(cls, filename, override_regex=None):
		regexes = cls._EPISODE_NUMBER_GUESS_REGEXES
		if override_regex:
			regexes = (override_regex,) + regexes
		if filename.endswith(mediaExtension):
			filename = filename[:-len(mediaExtension)]
		for r in regexes:
			result = re.match('^.*(?:%s).*$' % (r,), filename, re.IGNORECASE)
			if result and result.group(1).isdigit():
				return int(result.group(1))
		return None

	def __init__(self, parent, index, filename, title=None, summary=None, airdate=None, subseries=None):
		self._parent = parent
		self._index = str(index)
		self._filename = filename
		self._title = title
		self._summary = summary
		self._airdate = airdate
		self._subseries = subseries
	@property
	def parent(self):
		return self._parent
	@property
	def filename(self):
		return self._filename
	@property
	def path(self):
		return os.path.join(self.parent.path, self.filename)
	@property
	def reflected_path(self):
		assert self.is_integer_ep
		return os.path.join(self.parent.reflected_path, (' %%s.ep%%0%dd%%s' % (self.index_padding,)) % (self.parent.name_noprefix, int(self.index), mediaExtension))
	@property
	def nfo_path(self):
		self.sanityCheck()
		return self.reflected_path[:-len(mediaExtension)] + nfoExtension
	@property
	def index(self):
		return self._index
	@property
	def is_integer_ep(self):
		return self._index.isdigit()
	@property
	def summary(self):
		return self._summary
	@property
	def airdate(self):
		return self._airdate
	@property
	def index_padding(self):
		return math.ceil(math.log(len(self.parent.episodes) + 1, 10))
	@property
	def title(self):
		if self._title:
			return self._title
		padding = '%%0%dd%%s' % (self.index_padding,)
		index = self.index
		decimal = ''
		if '.' in index:
			index, decimal = index.split('.')
			decimal = '.' + decimal
		else:
			assert self.is_integer_ep
		return '%s - Episode %s' % (self.parent.name_noprefix, padding % (int(index), decimal))
	@property
	def subseries(self):
		return self._subseries

	def __str__(self):
		return 'Episode#%s<%r | %s>' % (self.index, self.title, self.filename)

	def sanityCheck(self):
		if not os.path.exists(self.path):
			raise RuntimeError('Episode %s has non-existent path: %s' % (self, self.path))
		assert self.filename.endswith(mediaExtension)

	def OverwriteNFO(self, data):
		if os.path.exists(self.nfo_path):
			currentNFOHandle = open(self.nfo_path, 'r')
			currentNFO = currentNFOHandle.read(-1)
			currentNFOHandle.close()
			if currentNFO == data:
				return
		print('Writing to', self.nfo_path, ':')
		print('-' * 80)
		print(data)
		print('-' * 80)
		f = open(self.nfo_path, 'w')
		f.write(data)
		f.close()

class Context(object):
	KIND_SERIES = 'series'
	KIND_SEASON = 'season'
	KIND_MOVIE = 'movie'
	KIND_OVA = 'ova'
	KIND_SOUNDTRACK = 'soundtrack'
	KIND_IGNORE = 'ignore'

	KNOWN_KEYS = frozenset((
		'name',
		'background', 'banner', 'poster', '_temp_gathering_art',
		AniDB.KEY, MAL.KEY, TVDB.KEY, IMDB.KEY, HummingBird.KEY,
		'season', 'moviefilename', 'override_epdata', 'override_epregex',
		'www_metadata', 'metadata_preferences',
	))
	ART_KEYS = frozenset(('background', 'banner', 'poster'))
	EPDATA_SUBSERIES_KNOWN_KEYS = frozenset((
		AniDB.KEY, MAL.KEY, TVDB.KEY, IMDB.KEY, HummingBird.KEY, 'id',
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
		self._ignore = False
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
	def under_root_path(self):
		if self.is_root:
			return None
		under_root = self.path
		while not os.path.exists(os.path.join(os.path.dirname(under_root), rootFile)):
			if under_root == os.path.dirname(under_root):
				raise RuntimeError('Cannot determine media library under-root-path from %s' % (self.path,))
			under_root = os.path.dirname(under_root)
		return under_root
	@property
	def is_right_under_root(self):
		return self.under_root_path == self.path
	@property
	def root(self):
		root = self.path
		while not os.path.exists(os.path.join(root, rootFile)):
			if root == os.path.dirname(root):
				raise RuntimeError('Cannot determine media library root from %s' % (self.path,))
			root = os.path.dirname(root)
		return root
	@property
	def reflected_root(self):
		reflected = open(os.path.join(self.root, rootFile), 'r').read(-1).strip()
		assert reflected[0] == os.sep # Must be an absolute path.
		assert os.path.isdir(reflected)
		return os.path.abspath(reflected)
	@property
	def reflected_path(self):
		path = os.path.abspath(self.path)
		root = os.path.abspath(self.root)
		assert path.startswith(root + os.sep)
		reflected = os.path.join(self.reflected_root, path[len(root):].lstrip(os.sep))
		if not os.path.isdir(reflected):
			os.makedirs(reflected)
		return reflected
	@property
	def is_root(self):
		return self.path == self.root
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
			self.KIND_IGNORE: {},
		}[self.kind]
	@property
	def is_in_series(self):
		if self.kind == self.KIND_SERIES:
			return False
		parent = self._parent
		while parent and parent.kind != parent.KIND_SERIES:
			parent = parent._parent
		return parent and parent.kind == parent.KIND_SERIES
	@property
	def nfo_path(self):
		if self.kind == self.KIND_SERIES:
			return os.path.join(self.reflected_path, 'tvshow' + nfoExtension)
		if self.kind == self.KIND_SEASON:
			return os.path.join(self.reflected_path, 'season' + nfoExtension)
		if self.kind == self.KIND_MOVIE:
			return os.path.join(self.reflected_moviefilename[:-len(mediaExtension)] + nfoExtension)
	@property
	def tvshowlike_nfo_path(self):
		return os.path.join(self.reflected_path, 'tvshow' + nfoExtension)
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
	def prefix(self):
		prefix = self.name
		if ' - ' in prefix:
			prefix = prefix[:prefix.index(' - ')]
		return prefix
	@property
	def name_searchable(self):
		return self._SEARCHABLE_JOIN.sub(' ', self._SEARCHABLE_FILTER.sub(' ', self.name_noprefix))
	@property
	def metadata(self):
		return self.Get('www_metadata') or {}
	@property
	def metadata_single(self):
		return self.GetSingle('www_metadata') or {}
	@property
	def metadata_preferences(self):
		return self.Get('metadata_preferences') or {}
	@property
	def id_sources(self):
		return {
			self.KIND_SERIES: (TVDB,),
			self.KIND_SEASON: (AniDB, MAL, IMDB),
			self.KIND_MOVIE: (AniDB, MAL, IMDB),
			self.KIND_OVA: (AniDB, MAL),
			self.KIND_SOUNDTRACK: (),
			self.KIND_IGNORE: (),
		}[self.kind]
	@property
	def filenames(self):
		return list(sorted(f for f in os.listdir(self.path)))
	@property
	def media_filenames(self):
		return list(f for f in self.filenames if f.endswith(mediaExtension))
	@property
	def moviefilename(self):
		files = self.media_filenames
		moviefilename = self.GetSingle('moviefilename')
		if moviefilename:
			if moviefilename not in files:
				raise RuntimeError('%s has moviefilename=%r but file was not found' % (self, moviefilename))
			return moviefilename
		if len(files) != 1:
			raise RuntimeError('%s is a movie with no moviefilename defined, and %d media files were found: %r' % (self, len(files), files))
		return files[0]
	@property
	def reflected_moviefilename(self):
		assert self.kind == self.KIND_MOVIE
		return os.path.join(self.reflected_path, 'Movie.ep00' + mediaExtension)
	@property
	def episodes(self):
		if self.kind not in (self.KIND_SEASON, self.KIND_OVA):
			raise RuntimeError('%s: Cannot list episodes, this is not a season/OVA')
		if self.metadata_preferences.get('disable_episodes'):
			return []
		if not self.metadata_single:
			print('Warning: No metadata defined on %s. Cannot thoroughly build episode list.' % (self,))
			count = None
		else:
			count = self.metadata_single['episodes']
		files = self.media_filenames
		if count is not None and count > len(files):
			raise RuntimeError('%s: Found %d media files, but episode count is %d' % (self, len(files), count))
		epdata = {}
		if self.metadata:
			epdata = dict((str(k), v) for k, v in self.metadata.get('epdata', {}).items())
		episodes = {}
		overridden = set()
		override_regex = self.Get('override_epregex')
		for pattern, data in (self.Get('override_epdata') or {}).items():
			if 'index' not in data and all(k not in data for k in self.EPDATA_SUBSERIES_KNOWN_KEYS):
				raise RuntimeError('%s: Episode override with pattern %r (data %r) has no index nor subseries information' % (self, pattern, data))
			matched = None
			r = re.compile(pattern, re.IGNORECASE)
			for f in files:
				if r.search(f):
					if matched:
						raise RuntimeError('%s: Pattern %r matched two files: %r and %r' % (self, pattern, matched, f))
					matched = f
			if matched is None:
				raise RuntimeError('%s: Pattern %r matched no files' % (self, pattern))
			ep = data.get('index')
			if ep is None:
				ep = Episode.GuessEpisodeNumber(matched, override_regex)
				if ep is None:
					raise RuntimeError('%s: Episode override with pattern %r and no index information matched file %r for which we cannot determine the episode number' % (self, pattern, matched))
			subseries = '__main__'
			for k in self.EPDATA_SUBSERIES_KNOWN_KEYS:
				if k in data:
					mainseries = self.Get(k)
					if mainseries and str(mainseries) == str(data[k]):
						subseries = '__main__'
					else:
						subseries = '%s:%s' % (k, str(data[k]))
			episodes['%s:%s' % (subseries, ep)] = Episode(self, ep, matched, title=data.get('title'), summary=data.get('summary'), airdate=data.get('airdate'), subseries=subseries)
			overridden.add(matched)
		for f in files:
			if f in overridden:
				continue
			ep = Episode.GuessEpisodeNumber(f, override_regex)
			if ep is not None:
				index = '%s:%s' % ('__main__', ep)
				if index in episodes:
					raise RuntimeError('%s: Found episode %s twice: In %r and in %r' % (self, ep, episodes[index].filename, f))
				data = epdata.get(str(ep), {})
				episodes[index] = Episode(self, ep, f, title=data.get('title'), summary=data.get('summary'), airdate=data.get('airdate'))
		maineps = {k: v for k, v in episodes.items() if k.split(':')[0] == '__main__' and v.is_integer_ep}
		if count is not None and len(maineps) > count:
			raise RuntimeError('%s: Found more episodes than expected. Expected: %d main | Found (%d): %r | Files (%d): %r' % (self, count, len(maineps), maineps.keys(), len(files), files))
		eplist = []
		if count is None:
			count = len(maineps)
		for i in range(1, count+1):
			index = '__main__:%d' % (i,)
			if index not in episodes:
				raise RuntimeError('%s: Could not find episode %s. Found:\n%r\nFiles:\n%r\n' % (self, index, list(sorted(x.filename for x in episodes.values())), files))
			eplist.append(episodes[index])
		return eplist
	@property
	def reflected_links(self):
		if self.kind not in (self.KIND_SEASON, self.KIND_OVA):
			episodes = []
		else:
			episodes = self.episodes
		reflected_path = self.reflected_path
		for f in os.listdir(self.path):
			if f in (infoFile, rootFile):
				continue
			path = os.path.join(self.path, f)
			if not os.path.isfile(path):
				continue
			if self.kind == self.KIND_MOVIE and f == self.moviefilename:
				yield (self.reflected_moviefilename, path)
				continue
			found = False
			for e in episodes:
				if e.filename == f:
					yield (e.reflected_path, path)
					found = True
					break
			if not found:
				yield (os.path.join(reflected_path, f), path)
	@property
	def expected_art(self):
		return {
			self.KIND_SERIES: ('background', 'poster'), # +banner
			self.KIND_SEASON: ('background', 'poster'), # +banner
			self.KIND_MOVIE: ('background', 'poster'),
			self.KIND_OVA: ('background', 'poster'),
			self.KIND_SOUNDTRACK: (),
			self.KIND_IGNORE: (),
		}[self.kind]

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
		if self.kind == self.KIND_IGNORE:
			return
		for d in self.soundtrack, self.ova, self.movie, self.season, self.series:
			for k in d.keys():
				if k not in self.KNOWN_KEYS:
					raise RuntimeError('Unknown key "%s" in %s' % (k, self))
		files = self.media_filenames
		if self.kind == self.KIND_SERIES and len(files) != 0:
			raise RuntimeError('%s: Kind is series, but found %d media files in %s: %r' % (self, len(files), self.path, files))
		if self.kind not in (self.KIND_SERIES, self.KIND_SOUNDTRACK) and self._parent is not None and len(files) == 0:
			raise RuntimeError('%s: Found no media files in %s' % (self, self.path))
		if self.kind == self.KIND_MOVIE:
			assert self.moviefilename is not None
		if self.kind in (self.KIND_SEASON, self.KIND_OVA):
			for ep in self.episodes:
				ep.sanityCheck()

	def SubContext(self, path, data):
		"""Returns a new Context with overlaid data."""
		self.sanityCheck()
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
		if 'ignore' in data:
			sub._kind = self.KIND_IGNORE
		sub.sanityCheck()
		return sub

	def GatherSubContexts(self):
		yield self
		yield from traverse(self.path, self)

	def SetMetadata(self, metadata):
		self.kind_data['www_metadata'] = metadata
		self.Overwrite()

	def Overwrite(self):
		self.sanityCheck()
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
	def OverwriteNFO(self, data, nfo_path=None):
		if nfo_path is None:
			nfo_path = self.nfo_path
		assert nfo_path
		if os.path.exists(nfo_path):
			currentNFOHandle = open(nfo_path, 'r')
			currentNFO = currentNFOHandle.read(-1)
			currentNFOHandle.close()
			if currentNFO == data:
				return
		print('Writing to', nfo_path, ':')
		print('-' * 80)
		print(data)
		print('-' * 80)
		f = open(nfo_path, 'w')
		f.write(data)
		f.close()

	def __str__(self):
		"""String representation."""
		series = self.series.get('name', 'UNKNOWN_SERIES')
		sub = 'ROOT' if self.kind == self.KIND_SERIES else self.name
		return '%s :: %s (%s)' % (series, sub, self.kind)

	__repr__ = __str__

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
	if not os.path.isdir(path):
		print('Warning: Skipping traversal of', path, 'as it is not a directory.')
		return
	yield from traverse(path, Context(None, path))
