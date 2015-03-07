#!/usr/bin/env python3

import os
import sys
import sqlite3
import xml.etree.ElementTree as ET
import data

_viewMode_lowList = 66037
_viewMode_posters = 458808

_viewMode_mapping = {
	data.Context.KIND_SERIES: _viewMode_posters,
	data.Context.KIND_SEASON: _viewMode_lowList,
	data.Context.KIND_MOVIE: _viewMode_lowList,
	data.Context.KIND_OVA: _viewMode_lowList,
}

_window = 10025  # "Files"
_sortMethod = 4 # File
_sortOrder = 1 # Ascending
_sortAttributes = 0 # Nothing special
_skin = 'skin.aeon.nox.5' # Aeon nox

_querySelect = 'SELECT idView, window, viewMode, sortMethod, sortOrder, sortAttributes, skin FROM view WHERE path = ?'
_queryInsert = 'INSERT INTO view (window, path, viewMode, sortMethod, sortOrder, sortAttributes, skin) VALUES(%d, ?, ?, %d, %d, %d, %r)' % (_window, _sortMethod, _sortOrder, _sortAttributes, _skin)
_queryUpdate = 'UPDATE view SET viewMode = ?, sortMethod = %d, sortOrder = %d, sortAttributes = %d WHERE idView = ?' % (_sortMethod, _sortOrder, _sortAttributes)

_backgroundKeys = (
	'skin.aeon.nox.5.System.Fallback',
	'skin.aeon.nox.5.Movies.Fallback',
	'skin.aeon.nox.5.TVShows.Fallback',
	'skin.aeon.nox.5.Videos.Fallback',
)

def _RunQuery(cursor, query, parameters):
	print('Running query: %r with parameters %r' % (query, parameters))
	cursor.execute(query, parameters)

def UpdateDatabase(context, cursor):
	mode = _viewMode_mapping.get(context.kind)
	if not mode:
		return
	reflected_path = context.reflected_path
	if not reflected_path.endswith(os.sep):
		reflected_path += os.sep
	row = cursor.execute(_querySelect, (reflected_path,)).fetchone()
	if row:
		idView, window, viewMode, sortMethod, sortOrder, sortAttributes, skin = row
		if (window, viewMode, sortMethod, sortOrder, sortAttributes, skin) != (_window, mode, _sortMethod, _sortOrder, _sortAttributes, _skin):
			_RunQuery(cursor, _queryUpdate, (mode, idView))
	else:
		_RunQuery(cursor, _queryInsert, (reflected_path, mode))

def UpdateKodiProfile(library, profile):
	guisettings = os.path.join(profile, 'userdata/guisettings.xml')
	tree = ET.parse(guisettings)
	changed = False
	for setting in tree.getroot().findall('.//setting'):
		if setting.get('name') in _backgroundKeys and setting.text != library.background:
			changed = True
			setting.text = library.background
	if changed:
		tree.write(guisettings)

if __name__ == '__main__':
	libraries = {}
	databases = {}
	try:
		for path in sys.argv[1:]:
			for context in data.Traverse(path):
				print('Updating database entry for:', context)
				library = context.library
				if library.path not in libraries:
					libraries[library.path] = library
					for profile in library.kodi_profiles:
						if profile in databases:
							continue
						database = os.path.join(profile, 'userdata/Database/ViewModes6.db')
						if not os.path.isfile(database):
							raise RuntimeError('Database file %r does not exist.' % (database,))
						conn = sqlite3.connect(database)
						cursor = conn.cursor()
						databases[profile] = (conn, cursor)
				for profile in library.kodi_profiles:
					UpdateDatabase(context, databases[profile][1])
	finally:
		for conn, _ in databases.values():
			conn.commit()
			conn.close()
	for library in libraries.values():
		print('Updating library settings for:', library)
		for profile in library.kodi_profiles:
			print('Updating Kodi profile for', library, 'at', profile)
			UpdateKodiProfile(library, profile)
