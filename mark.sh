#!/usr/bin/env bash

# Useful to seed the .info file for a bunch of media directories.

set -e

kind="$1"
if [ "$kind" != series -a "$kind" != season -a "$kind" != movie -a "$kind" != ova -a "$kind" != soundtrack -a "$kind" != missing ]; then
	echo "Usage: $0 <series|season|movie|missing> dir1 dir2 ..."
	exit 1
fi
shift

missing=''
if [ "$kind" == missing ]; then
	missing=true
	kind=''
fi

for d; do
	infoFile="$d/.info"
	if [ -e "$infoFile" ]; then
		existingKind="$(grep -P '^(series|season|movie|ova|soundtrack):' "$infoFile" | cut -d: -f1 || true)"
		if [ -z "$existingKind" ]; then
			echo "Error: '$infoFile' exists but does not have a recognized kind. Exitting."
			exit 1
		fi
		if [ "$missing" != true -a "$kind" != "$existingKind" ]; then
			echo "Error: '$infoFile' exists but has kind '$existingKind', while you asked for it to be marked as kind '$kind'. Exitting."
			exit 1
		else
			echo "'$infoFile' already exists. Skipping."
		fi
		if [ "$missing" == true ]; then
			kind="$existingKind"
		fi
	else
		if [ "$missing" == true ]; then
			echo '' # Blank line
			echo -n "Kind for '$d' (default=series, 'skip' to skip): "
			read kind
			if [ -z "$kind" ]; then
				kind='series'
			fi
			if [ "$kind" != series -a "$kind" != season -a "$kind" != movie -a "$kind" != ova -a "$kind" != soundtrack -a "$subKind" != skip ]; then
				echo "Invalid kind '$kind'. Exitting."
				exit 1
			fi
		fi
		if [ "$kind" != skip ]; then
			echo "$kind:" > "$infoFile"
			echo "Marked '$infoFile' as kind '$kind'."
		fi
	fi
	if [ "$kind" == series ]; then
		echo "'$d' is a series; checking subdirectories."
		for subDir in "$d"/*; do
			subFilename="$(basename "$subDir")"
			if [ -d "$subDir" ]; then
				subInfo="$subDir/.info"
				if [ -e "$subInfo" ]; then
					echo "Sub-info '$subInfo' already exists. Skipping."
				else
					default='season'
					if echo "$subFilename" | grep -qi 'o[nv]a'; then
						default='ova'
					elif echo "$subFilename" | grep -qi movie; then
						default='movie'
					elif echo "$subFilename" | grep -qi soundtrack; then
						default='soundtrack'
					elif echo "$subFilename" | grep -qi ost; then
						default='soundtrack'
					elif [ "$(ls -1 "$subDir" | wc -l)" -le 2 ]; then
						default='movie'
					fi
					echo '' # Blank line
					echo -n "Kind for '$subDir' (default=$default, 'skip' to skip): "
					read subKind
					if [ -z "$subKind" ]; then
						subKind="$default"
					fi
					if [ "$subKind" != series -a "$subKind" != season -a "$subKind" != movie -a "$subKind" != ova -a "$subKind" != soundtrack -a "$subKind" != skip ]; then
						echo "Invalid kind '$subKind'. Exitting."
						exit 1
					fi
					if [ "$subKind" != skip ]; then
						echo "$subKind:" > "$subInfo"
						echo "Marked sub-info '$subInfo' as kind '$subKind'."
					fi
				fi
			else
				if [ "$subFilename" != poster.jpg -a "$subFilename" != fanart.jpg -a "$subFilename" != banner.jpg ]; then
					echo "Warning: Not a subdirectory: '$subDir'. Skipping."
				fi
			fi
		done
	fi
done
