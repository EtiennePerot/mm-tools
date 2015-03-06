#!/usr/bin/env python3

import imghdr
import re
import os
import sys
import time
import mimetypes
import html
import requests
import data

def MetadataFromHummingBird(context):
	hummingbird = int(context.Get(data.HummingBird.KEY))
	response = data.HummingBird(hummingbird).Lookup()
	synopsis = response['anime']['synopsis']
	synopsis = re.sub(r'\s*[[(]?Source:.*[])]?\s*$', '', synopsis, re.IGNORECASE)
	synopsis = synopsis.replace('[Written by MAL Rewrite]', '')
	return {
		'source': 'hummingbird:%d' % (hummingbird,),
		'summary': synopsis.strip(),
		'episodes': int(response['anime']['episode_count']),
		'genres': response['anime']['genres'],
		'year': int(response['anime']['started_airing_date'].split('-')[0]),
	}

def MetadataFromMAL(context):
	mal = int(context.Get(data.MAL.KEY))
	response = requests.get('https://malapi.shioridiary.me/anime/%d' % (mal,)).json()
	synopsis = html.unescape(re.sub(r'<[^<>]+>', '', re.sub(r'<script[\s\S]*/script>', '', re.sub(r'<br[^<>]*>', '\n', re.sub(r'[\r\n]+', '', response['synopsis'].replace('&#13;', '\r')), re.IGNORECASE), re.IGNORECASE)))
	synopsis = re.sub(r'\s*[[(]?Source:.*[])]?\s*$', '', synopsis, re.IGNORECASE)
	synopsis = synopsis.replace('[Written by MAL Rewrite]', '')
	return {
		'source': 'mal:%d' % (mal,),
		'summary': synopsis.strip(),
		'episodes': int(response['episodes']),
		'genres': response['genres'],
		'year': int(response['start_date'].split(' ')[-1]),
	}

def EpDataFromTVDB(context):
	epdata = {}
	ep_mapping = context.metadata_preferences.get('tvdb_episode_mapping', {})
	ep_mapping_found = {}
	show = data.TVDB.API[int(context.Get(data.TVDB.KEY))]
	season = context.metadata_preferences.get('tvdb_season', context.Get('season'))
	if season is None:
		raise RuntimeError('%s has no season number defined' % (context,))
	season = show[season]
	episodes = context.episodes
	if ep_mapping:
		assert len(ep_mapping) == len(episodes)
	for ep in episodes:
		if not ep.is_integer_ep:
			continue
		episode = None
		if ep_mapping:
			mapping = str(ep_mapping[int(ep.index)])
			for s in show.values():
				for e in s.values():
					if str(e['id']) == str(mapping):
						episode = e
						ep_mapping_found[int(ep.index)] = True
						break
				if episode is not None:
					break
			if episode is None:
				raise RuntimeError('%s: Episode mapping for index %s found no match' % (context, ep.index))
		else:
			episode = season[int(ep.index)]
		if 'episodename' in episode:
			d = {'title': episode['episodename']}
			if 'overview' in episode:
				d['summary'] = episode['overview']
			if 'firstaired' in episode:
				d['airdate'] = episode['firstaired']
			epdata[ep.index] = d
	if frozenset(ep_mapping_found.keys()) != frozenset(ep_mapping.keys()):
		raise RuntimeError('%s: Episode mapping had mappings for %r, but only found mappings for %r' % (context, ep_mapping.keys(), ep_mapping_found.keys()))
	return epdata

def EpDataFromHummingBird(context):
	if context.metadata_preferences.get('no_hummingbird'):
		return None
	epdata = {}
	hummingbird = int(context.Get(data.HummingBird.KEY))
	response = data.HummingBird(hummingbird).Lookup()
	for ep in response['linked']['episodes']:
		d = {'title': ep['title']}
		if 'synopsis' in ep and ep['synopsis']:
			d['summary'] = ep['synopsis']
		if 'airdate' in ep and ep['airdate']:
			d['airdate'] = ep['airdate']
		epdata[ep['number']] = d
	return epdata

def PoorEpData(epdata):
	if not epdata:
		return True
	for ep, d in epdata.items():
		if 'synopsis' in d and len(d['synopsis']) > 8:
			return False
	return True

def GrabMetadata(context):
	metadata = context.metadata_single
	if metadata:
		# Consider doing checks on last retrieval date.
		return
	if context.kind == data.Context.KIND_SERIES:
		tvdb = context.Get(data.TVDB.KEY)
		if tvdb is None or tvdb == 'None':
			print('Warning: Cannot get metadata for', context, 'as no TVDB ID is assigned.')
			return
		tvdb = int(context.Get(data.TVDB.KEY))
		show = data.TVDB.API[tvdb]
		metadata = {
			'source': 'tvdb:%d' % (tvdb,),
			'summary': show.data['overview'],
			'genres': list(filter(lambda x: x, show.data['genre'].split('|'))),
		}
		airdate = show.data['firstaired'].split('-')
		if len(airdate) == 3:
			metadata['year'] = int(airdate[0])
	elif context.kind in (data.Context.KIND_SEASON, data.Context.KIND_MOVIE, data.Context.KIND_OVA):
		if context.Get(data.HummingBird.KEY) is not None:
			metadata = MetadataFromHummingBird(context)
		elif context.Get(data.MAL.KEY) is not None:
			metadata = MetadataFromMAL(context)
		else:
			print('Warning: Cannot get metadata for', context, 'as no MAL/HummingBird ID is assigned.')
		if metadata and context.kind == data.Context.KIND_SEASON:
			if context.metadata_preferences.get('force_episodes') is not None:
				metadata['episodes'] = int(context.metadata_preferences.get('force_episodes'))
			epdata = None
			if context.Get(data.HummingBird.KEY) is not None:
				epdata = EpDataFromHummingBird(context)
				if epdata:
					metadata['source_epdata'] = '%s:%s' % (data.HummingBird.KEY, context.Get(data.HummingBird.KEY))
			if PoorEpData(epdata) and context.Get(data.TVDB.KEY) is not None:
				epdata = EpDataFromTVDB(context)
				if epdata:
					metadata['source_epdata'] = '%s:%s' % (data.TVDB.KEY, context.Get(data.TVDB.KEY))
			if epdata:
				metadata['epdata'] = epdata
	if metadata:
		metadata['retrieved'] = time.strftime('%Y-%m-%d')
		context.SetMetadata(metadata)

def GrabArt(context):
	if context.kind in (data.Context.KIND_SOUNDTRACK, data.Context.KIND_IGNORE):
		return
	for key, filename in data.artResourceFilenames.items():
		if key not in context.expected_art:
			continue
		source = context.GetSingle(key)
		if source is None or source == 'None':
			print('Warning: Undefined', key, 'in', context)
			continue
		if any(os.path.isfile(os.path.join(context.path, filename + '.' + ext)) for ext in data.imageExtensions):
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
		extension = data.imageExtensionMappings.get(extension, extension)
		if extension not in data.imageExtensions:
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
			GrabMetadata(context)
			GrabArt(context)
