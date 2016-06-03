#
#  archiver.py - archive a Final Cut Pro X library into a generic structure for long term
#		storage and recovery.
#
#  Get a list of all events within the archive, compare with the events in the library
#		Anything in the library takes precedence over the archiver- nothing is ever
#		deleted- only added (e.g. if a new clip is added to library, it gets added to
#		archive automatically.  If clip removed from library, it stays in archive).
#  
#
import subprocess
import json
import os
import argparse
import sys
from pathlib import Path

# Valid file types we want to archive
types = ("*.mov", "*.m4v", "*.avi", "*.wmv", "*.mp4")

parser = argparse.ArgumentParser(description='Video Archiver.')
parser.add_argument("library", help='name of library to be archived')
parser.add_argument("-a", "--archiveDir", help="directory where archive should be created (defaults to ./archive)")
parser.add_argument("-t", "--test", help="test the creation, only make directories and thumbnails, don't copy any files", action="store_true")
args = parser.parse_args()

#
def generate_event_information(library, eventPath):
	print('Creating Event Info for ' + str(eventPath))

	clipPaths = []			# List of Paths to all clips in Event
	for files in types:
		clipPaths.extend(eventPath.glob(files))

	dbase = { "library" : library, "event" : eventPath.name, "clips" : [] }

	for p in clipPaths:
		proc = subprocess.Popen(['mediainfo', str(p)], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
		stdout, stderr = proc.communicate()

		if ( proc.returncode == 0 ):

			# Save metadata for database
			lines = stdout.decode('utf-8').splitlines()
			mdata = {}
			for l in lines:
				#print(l)
				lhs, sep, rhs = l.partition(":")
				if ( sep != "" ):
					mdata[lhs.strip()] = rhs.strip()
			clipdata = { "name" : str(p), "metadata" : mdata }
			dbase["clips"].append(clipdata)

			# Create the thumbnail
			thumbPath = eventPath.joinpath('thumbs');
			clip_name, sep, suffix = p.name.rpartition(".")
			thumbPattern = clip_name + '-%2d.jpg'
			thumbFilePath = thumbPath.joinpath(thumbPattern)
			# Default thumbnail to HD 720, but use SD format if it looks like should
			thumbSize = 'hd720'
			aspectRatio = mdata.get('Display aspect ratio')
			#print('Thumb ' + clip_name + ' has aspect ratio ' + aspectRatio)
			if ( aspectRatio != None and mdata['Display aspect ratio'] == '4:3' ):
				thumbSize = 'vga'
			print('Creating thumbnail  ' + str(thumbFilePath))
			cmdline = ['ffmpeg', '-i', str(p), '-r', '1', '-t', '0.03', '-s', thumbSize, str(thumbFilePath)]
			proc = subprocess.Popen(cmdline, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
			stdout, stderr = proc.communicate()
			if ( proc.returncode != 0 ):
				print('Error creating thumbnail for ' + str(p) + ' ' + stderr.decode('utf-8'))
		else:
			print('Error creating metadata for Event ' + stderr.decode('utf-8'))
	
	databasePath = eventPath.joinpath(eventPath.name + '.json')
	print('Writing Event database file ' + str(databasePath))
	f = open(str(databasePath), 'w')
	json.dump(dbase, f, sort_keys=True, indent=4)
	f.close()

#
#	Create necessary folder space for thumbs for this event
#
def prepare_for_thumbnails(eventPath):
	print('Preparing Thumbnails for ' + str(eventPath))
	thumbPath = eventPath.joinpath('thumbs');
	if ( not thumbPath.exists() ):
		print("Creating thumb diretory " + str(thumbPath))
		os.makedirs(str(thumbPath))	# HANDLE CREATION ERROR?
	else:
		# Clean out the thumb folder, start fresh
		print('Cleaning out thumb directory ' + str(thumbPath))
		allThumbFiles = thumbPath.glob('*.jpg')
		for f in allThumbFiles:
			os.remove(str(f))

#	clipPaths = []			# List of Paths to all clips in Event
#	for files in types:
#		clipPaths.extend(eventPath.glob(files))
#
#	for p in clipPaths:
#		#Creating thumbnails in ffmpeg
#		#~/ffmpeg -i "Clip #146.mov" -r 1 -t 0.03 -s hd720 frame-%2d.jpg
#		clip_name, sep, suffix = p.name.partition(".")
#		thumbPattern = clip_name + '-%2d.jpg'
#		thumbFilePath = thumbPath.joinpath(thumbPattern)
#		# TODO: WE SHOULD PICK THUMBSIZE APPROPRIATE FOR FORMAT:
#		#		HD - 16x9
#		#		SD - 4X3
#		cmdline = ['ffmpeg', '-i', str(p), '-r', '1', '-t', '0.03', '-s', 'hd720', str(thumbFilePath)]
#		proc = subprocess.Popen(cmdline, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
#		stdout, stderr = proc.communicate()
#
#		if ( proc.returncode != 0 ):
#			print('Error creating thumbnail for ' + str(p) + ' ' + stderr.decode('utf-8'))



# Set up Paths & ensure directories are where we need them
libPath = Path(os.path.join(os.getcwd(), args.library))
if ( not libPath.exists() ):
	print("Cannot open " + str(libPath))
	sys.exit()
# Pull off the ".fcpbundle" suffix on the library name (if it is there)
library_name, sep, suffix = libPath.name.partition(".")
# TODO: NEED TO USE args.archiveDir IF GIVEN...
archivePath = Path(os.path.join(os.getcwd(), "archive", library_name))
if ( not archivePath.exists() ):
	print("Creating " + str(archivePath))
	os.makedirs(str(archivePath))	# HANDLE CREATION ERROR??

# Get list of Events in the Library
events = [x for x in libPath.iterdir()]
# Take out special files/directories from Library
#	(We can try to use globbing for this like below?
events = [x for x in events if \
	not x.name.startswith('.') and not x.name.startswith('_') and \
	not x.name.endswith('.flexolibrary') and not x.name.endswith('.plist')]

# Process all Events found in Library
for e in events:
	eventName = e.name
	print('Looking in Event ' + eventName)
	mediaPath = e / "Original Media"
	# Check that we have clips in the library Event to put in archive
	if ( mediaPath.exists() ):
		print('Clips in library event' + str(e))
		libraryClips = []			# List of clip names
		libraryClipPaths = []		# List of clip paths
		# Create a set of all clips in library event
		for files in types:
			libraryClipPaths.extend(mediaPath.glob(files))
		# I'm sure there's a much nicer way to do this with lambda functions
		for c in libraryClipPaths:
			libraryClips.append(c.name)	

		# See if event already exists in archive, and if so, find out if it has any clips
		#	Build a list of these clips so we can determine what hasn't been archived already
		archiveEventPath = archivePath.joinpath(eventName)
		archiveClips = []
		# Create archive Event if not already there
		if ( not archiveEventPath.exists() ):
			print("Creating archive event " + archiveEventPath.name)
			os.makedirs(str(archiveEventPath))	# HANDLE CREATION ERROR?
		else:
			archiveClipPaths = []
			for files in types:
				archiveClipPaths.extend(archiveEventPath.glob(files))
			print('Clips found in archive already')
			for c in archiveClipPaths:
				archiveClips.append(c.name)

		# Now construct the target set of clips that need to be copied from the
		#	library to the archive.  Should be difference between libraryClips minus archiveClips
		targetClips = set(libraryClips) - set(archiveClips)
		print('Clips to be copied')
		for c in targetClips:
			print(c);

		# Kick off the copying
		for c in targetClips:
			sourcePath = mediaPath.joinpath(c)
			destPath = archiveEventPath.joinpath(c)
			print('Copying ' + str(sourcePath) + " to " + str(destPath))
			if ( args.test != True ):
				proc = subprocess.Popen(['cp', str(sourcePath), str(destPath)], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
				stdout, stderr = proc.communicate()
				if ( proc.returncode != 0 ):
					print('\tError: ' + stderr.decode('utf-8'))

		prepare_for_thumbnails(archiveEventPath)

		generate_event_information(library_name, archiveEventPath)

		#generate_thumbnails(archiveEventPath)

	else:
		print('No Clips in ' + str(e))
