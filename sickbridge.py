from sickbridge import sickbeard
from sickbridge import jdownloader
from sickbridge import serienjunkies
from sickbridge import sickbridge

import sys
import time

def parseOptions():
	'''Using command line arguments to change config file'''
	import argparse
	# set up the parser
	parser = argparse.ArgumentParser(description='Adds your sickbeard backlog to JDownloader by search serienjunkies.org.')
	parser.add_argument('-o', action='store', dest='host', help='set prefered hoster')
	parser.add_argument('-s', action='store', metavar='URL', dest='sburl', help='set sickbeard url')
	parser.add_argument('-j', action='store', metavar='URL', dest='jdurl', help='set jdownloader url')
	parser.add_argument('-n', action='store', metavar='NAME', dest='sbname', help='set sickbeard username (optional)')
	parser.add_argument('-p', action='store', metavar='PASSWORD', dest='sbpass', help='set sickbeard password (optional)')
	parser.add_argument('-l', action='store', choices=['en', 'de', 'both'], dest='language', help='set language')
	parser.add_argument('-d', action='store_true', dest='defaults', help='use default settings (use -w to reset config. file)')
	parser.add_argument('-w', action='store_true', dest='save', help='write arguments to the configuration file and exit')
	parser.add_argument('--delete', action='store_true', dest='clear', help='delete history and exit')

	# parse
	return vars(parser.parse_args())

def action_default(config, history):
	# if name and / or password are saved, build the right url
	SICKBEARD_URL = config.get('sburl')

	if config.get('sbpass') != None and config.get('sbname') != None:
		SICKBEARD_URL_C = SICKBEARD_URL.replace('://', '://%s:%s@' % (config.get('sbname'), config.get('sbpass')))
	elif config.get('sbname') != None:
		SICKBEARD_URL_C = SICKBEARD_URL.replace('://', '://%s@' % config.get('sbname'))
	else:
		SICKBEARD_URL_C = SICKBEARD_URL

	# Counters for stat printing
	cBacklogSize = 0
	cNotDownloadedDueToCache = 0
	cAddedToDownloader = 0
	cSkippedDueQualityLanguageMismatch = 0

	if not jdownloader.is_available(config.get('jdurl')):
		print '[ERROR] Unable to connect to JDownloader. Check the following:'
		print ' 1) Make sure JDownloader is running'
		print ' 2) RemoteControl Plugin is active'
		print ' 3) The setting in the sickbridge config is properly configured (currently: %s)' % config.get('jdurl')
		print ' Exiting.'
		sys.exit(1)

	print "Scanning %s's backlog" % config.get('sburl')

	episodes = sickbeard.get_backlog_list(SICKBEARD_URL_C)
	cBacklogSize = len(episodes)
	
	print '[INFO] Found %d items in your sickbeard backlog' % (cBacklogSize)
	
	# Foreach episode in the backlog
	for (seriesName, seriesId, episodeName, episodeNo) in episodes:
		print

		# Fetch the show-settings from sickbeard
		(showId, showName, showLocation, showQuality, showLanguage, showStatus, showActive, showAirByDate, showSeasonFolders) = sickbeard.get_show_settings(SICKBEARD_URL_C, seriesId)

		# Print info header

		print "+-----------------------------------------------------------------------------+"
		print "| Name: %s " % showName
		print "| Language: %s " % showLanguage
		print "| Quality: %s " % showQuality
		print "|"
		print "| Episode: S%02dE%02d - %s" % (episodeNo[0], episodeNo[1], episodeName)
		print "+-----------------------------------------------------------------------------+"

		# Skip episode, if the history shows we already added it once to jdownloader
		# Possible reason for still beeing in the backlog:
		# - JDownloader is still downloading
		# - Files are offline
		# - many more ...
		if history.has_downloaded(seriesName, episodeNo, episodeName):
			print "[FINE] Already in history. Delete %s to download again." % history.get_path(seriesName, episodeNo, episodeName)
			cNotDownloadedDueToCache = cNotDownloadedDueToCache + 1
			continue

		# Check if we have a specific URL to check for this TV-Serie (Sometimes the script cannot guess the page url correctly)
		# None if no specific URL is available
		specificUrl = config.get_mapping(seriesName)

		# Grab the page and parse it into a list of available episodes
		downloads = serienjunkies.get_download_links(seriesName, seriesId, episodeName, episodeNo, url=specificUrl)

		# Filter out downloads that do not match our requirements (format, quality, language)
		filtereDownloads = sickbridge.filter_download(downloads, showQuality, showLanguage)

		if len(downloads) != len(filtereDownloads):
			print "[INFO] %d Downloads dropped because of quality/language mismatch." % (len(downloads) - len(filtereDownloads))
			cSkippedDueQualityLanguageMismatch = cSkippedDueQualityLanguageMismatch + 1

		# If none are found => Abort
		if filtereDownloads == None or len(filtereDownloads) == 0:
			print "[INFO] No downloads found."
		# We found some downloads for our wished episode :D
		else:
			# Sort them (If we have a preferred hoster, this sorts it to the top)
			sortedDownloads = sorted(filtereDownloads, key=sickbridge.download_sorter(config))

			# Another check if we might already be downloading this file
			if jdownloader.in_queue(config.get('jdurl'), sortedDownloads[0][5]):
				print "[INFO] Already in queue"
			else:
				# Schedule the top download
				sickbridge.schedule_download(config, sortedDownloads[0])
				# Mark episode as downloaded by SickBridge
				history.add_download(seriesName, episodeNo, episodeName)
				cAddedToDownloader = cAddedToDownloader + 1
				
				time.sleep(1) # sleep 1s to give jdownloader and others time act and relax :P

	# Print final results
	print
	print
	print "==============================================================================="
	print "= %3d of %3d were previously added to queue.									 =" % (cNotDownloadedDueToCache, cBacklogSize)
	print "= Successfully added %3d new links to queue.									 =" % (cAddedToDownloader)
	print "= %2d skipped due to quality/language mismatch.   							 =" % (cSkippedDueQualityLanguageMismatch)	
	print "==============================================================================="

def action_clear(config, history):
	history.clear()
	print "Cleared History"

def action_save(config, history):
	config.write_config()

def main():
	print "#============#"
	print "| Sickbridge |"
	print "#============#"
	config = sickbridge.SickbridgeConfig()
	if config.get('firsttime') == 'yes':
		config.set('firsttime', 'no')
		config.write_config()

		print "Welcome to Sickbridge. "
		print "We created a config file for you at %s" % config.configFile
		print "Please edit it and run this script again"
		sys.exit()

	history = sickbridge.SickbridgeHistory(config)


	# Parse Options
	vargs = parseOptions()

	# react
	if vargs['defaults']:
		config.set('jdurl', "http://localhost:7151/")
		config.set('sburl', "http://localhost:8081/")
		config.set('sbname', None)
		config.set('sbpass', None)
		config.set('preferredhost', None)
		config.set('language', None)

	if vargs['sburl'] != None:
		config.set('sburl', vargs['sburl'])
	if vargs['sbname'] != None:
		config.set('sbname', vargs['sbname'])
	if vargs['sbpass'] != None:
		config.set('sbpass', vargs['sbpass'])
	if vargs['jdurl'] != None:
		config.set('jdurl', vargs['jdurl'])
	if vargs['host'] != None:
		config.set('preferredhost', vargs['host'])
	if vargs['language'] != None:
		if vargs['language'] == 'en':
			config.set('language', 'Englisch')
		elif vargs['language'] == 'de':
			config.set('language', 'Deutsch')
		else:
			config.set('language', None)


	if vargs['save']:
		action_save(config, history)
	elif vargs['clear']:
		action_clear(config, history)
	else:
		action_default(config, history)

if __name__ == "__main__":
	main()
