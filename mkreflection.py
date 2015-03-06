#!/usr/bin/env python3

import os
import shutil
import sys
import data
from xml.sax.saxutils import escape as xml_escape

_TVSHOW_TEMPLATE = """
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<tvshow>
	<title>{title}</title>
	<year>{year}</year>
	<plot>{plot}</plot>
	<!-- Commented out so that no attempt is made to import from the web: <tvdbid>{id}</tvdbid> -->
	<!-- Commented out so that no attempt is made to import from the web: <id>{id}</id> -->
	{genres}
</tvshow>
"""

_SEASON_TEMPLATE = """
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<tvshow>
	<title>{title}</title>
	<sorttitle>{sorttitle}</sorttitle>
	<season>{season}</season>
	<year>{year}</year>
	<plot>{plot}</plot>
	{genres}
</tvshow>
"""

_EPISODE_TEMPLATE = """
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<episodedetails>
	<season>{season}</season>
	<displayseason>{displayseason}</displayseason>
	<episode>{episode}</episode>
	<title>{title}</title>
	<plot>{plot}</plot>
	<aired>{aired}</aired>
</episodedetails>
"""

_MOVIE_TEMPLATE = """
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<movie>
	<title>{title}</title>
	<year>{year}</year>
	<plot>{plot}</plot>
	<!-- Commented out so that no attempt is made to import from the web: <id>{id}</id> -->
	{genres}
</movie>
"""

def _CleanupNFO(data):
	return data.strip().replace('\r', '')

def MakeNFO(context):
	metadata = context.metadata
	if metadata is None:
		print('Warning:', context, 'has no metadata. Skipping.')
		return
	nfo = None
	if context.kind == data.Context.KIND_SERIES:
		nfo = _CleanupNFO(_TVSHOW_TEMPLATE.format(
			title=xml_escape(context.name_noprefix),
			year=xml_escape(str(metadata.get('year', ''))),
			plot=xml_escape(metadata.get('summary', '')),
			id=str(context.Get('tvdb')),
			genres=''.join(map(lambda s: '<genre>%s</genre>' % xml_escape(s), metadata.get('genres', ()))),
		))
	elif context.kind == data.Context.KIND_SEASON:
		# Per-season NFO.
		nfo = _CleanupNFO(_SEASON_TEMPLATE.format(
			title=xml_escape(context.name_noprefix),
			sorttitle=xml_escape(context.name),
			season=xml_escape(str(context.Get('season'))),
			year=xml_escape(str(metadata.get('year', ''))),
			plot=xml_escape(metadata.get('summary', '')),
			genres=''.join(map(lambda s: '<genre>%s</genre>' % xml_escape(s), metadata.get('genres', ()))),
		))
		# Per-episode NFOs.
		for ep in context.episodes:
			ep.OverwriteNFO(_CleanupNFO(_EPISODE_TEMPLATE.format(
				season=xml_escape(str(context.Get('season'))),
				displayseason=xml_escape(str(context.Get('season'))),
				episode=xml_escape(ep.index),
				title=xml_escape(ep.title),
				plot=xml_escape(ep.summary or ''),
				aired=xml_escape(ep.airdate or ''),
			)))
			yield ep.nfo_path
	elif context.kind == data.Context.KIND_MOVIE:
		if not context.is_in_series:
			nfo_path = context.tvshowlike_nfo_path
			yield nfo_path
			tvshow_nfo = _CleanupNFO(_TVSHOW_TEMPLATE.format(
				title=xml_escape(context.name_noprefix),
				year=xml_escape(str(metadata.get('year', ''))),
				plot=xml_escape(metadata.get('summary', '')),
				id=xml_escape(str(context.Get('imdb'))),
				genres=''.join(map(lambda s: '<genre>%s</genre>' % xml_escape(s), metadata.get('genres', ()))),
			))
			context.OverwriteNFO(tvshow_nfo, nfo_path=nfo_path)
		nfo = _CleanupNFO(_EPISODE_TEMPLATE.format(
			season='0',
			displayseason='99',
			episode='0',
			title=xml_escape(context.name_noprefix),
			plot=xml_escape(metadata.get('summary', '')),
			aired=xml_escape(str(metadata.get('year', ''))),
		))
	if nfo:
		context.OverwriteNFO(_CleanupNFO(nfo))
		yield context.nfo_path

def MakeReflection(context):
	if context.kind in (data.Context.KIND_SOUNDTRACK, data.Context.KIND_IGNORE):
		return
	for link, target in context.reflected_links:
		yield link
		if os.path.islink(link):
			if os.readlink(link) == target:
				continue
			os.unlink(link)
		print('ln', link, '->', target)
		os.symlink(target, link)

def DeleteNonInspected(context, inspected):
	path = context.path
	reflected_path = context.reflected_path
	for name in os.listdir(reflected_path):
		f = os.path.join(reflected_path, name)
		if f not in inspected and not os.path.exists(os.path.join(path, name)):
			if os.path.isdir(f):
				print('rm', '-f', f)
				shutil.rmtree(f)
			else:
				print('rm', f)
				os.remove(f)

if __name__ == '__main__':
	for path in sys.argv[1:]:
		for context in data.Traverse(path):
			print('Making reflected version:', context)
			inspected = set()
			for f in MakeReflection(context):
				inspected.add(f)
			for f in MakeNFO(context):
				inspected.add(f)
			DeleteNonInspected(context, inspected)
