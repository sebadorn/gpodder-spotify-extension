# -*- coding: utf-8 -*-

from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import base64, json, logging

import gpodder
from gpodder import feedcore, model


logger = logging.getLogger( __name__ )


# gPodder extension information.
__title__ = 'Spotify Extension'
__description__ = 'Check for new episodes in Spotify podcasts.'
__authors__ = 'Sebastian Dorn'


# Spotify application information.
# You will have to create an application on:
# https://developer.spotify.com/dashboard/applications
#
# Then copy the displayed Client ID and Client Secret.
# Do not share those and make sure not to commit them
# to your version control system.
SPOTIFY_CLIENT_ID = ''
SPOTIFY_CLIENT_SECRET = ''

# The market is listed as optional in the API, but that
# is wrong. Without this the request will return 404,
# at least using Client Credentials. With OAuth the market
# parameter seems to be optionally.
SPOTIFY_MARKET = 'DE'

SPOTIFY_API_ACCOUNT = 'https://accounts.spotify.com/api/token'
SPOTIFY_API_V1 = 'https://api.spotify.com/v1'



class SpotifyFeed( model.Feed ):


	def __init__( self, url, cover_url, description, max_episodes, ie_result ):
		""" """

		self._url = url
		self._cover_url = cover_url
		self._description = description
		self._max_episodes = max_episodes
		# ie_result['entries'] = self._process_entries(ie_result.get('entries', []))
		self._ie_result = ie_result



class gPodderExtension:


	def __init__( self, container ):
		"""
		Parameters
		----------
		container : gpodder.extensions.ExtensionContainer
		"""

		self.container = container
		self.token = None
		self.token_timestamp = None
		self.token_expires_in = 3600


	def do_api_request( self, url_path ):
		"""
		Parameters
		----------
		url_path : str
		"""

		self.get_token()

		url = '%s/shows/%s' % ( SPOTIFY_API_V1, url_path )

		logger.debug( 'API request to: %s' % url )

		request = Request(
			url,
			headers = {
				'Accept': 'application/json',
				'Authorization': 'Bearer ' + self.token,
				'Content-Type': 'application/json'
			}
		)

		resource = urlopen( request )
		charset = resource.headers.get_content_charset()
		json_data = resource.read().decode( charset )

		return json.loads( json_data )


	def fetch_episodes( self, channel, max_episodes = 0 ):
		"""
		Called by model.gPodderFetcher to get a custom feed.

		Returns
		-------
		gpodder.feedcore.Result
		"""

		feed = SpotifyFeed()
		feedcore.Result( feedcore.UPDATED_FEED, feed )


	def get_show_episodes( self, show_id ):
		"""
		Parameters
		----------
		show_id : str
		"""

		url = '%s/episodes?market=%s' % ( show_id, SPOTIFY_MARKET )

		return self.do_api_request( url )


	def get_show_info( self, show_id ):
		"""
		Parameters
		----------
		show_id : str
		"""

		url_path = '%s?market=%s' % ( show_id, SPOTIFY_MARKET )

		return self.do_api_request( url_path )


	def get_token( self ):
		""" Get a token to use in API requests. """

		if not self.is_token_expired():
			logger.debug( 'No need to refresh token.' )
			return;

		base64_auth = base64.b64encode(
			bytes( '%s:%s' % ( SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET ), 'ascii' )
		).decode( 'utf-8' )

		post_data = urlencode( { 'grant_type': 'client_credentials' } )

		request = Request(
			SPOTIFY_API_ACCOUNT,
			data = post_data.encode(),
			headers = {
				'Authorization': 'Basic ' + base64_auth,
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			method = 'POST'
		)
		json_response = urlopen( request ).read().decode()
		dict_response = json.loads( json_response )

		self.token = dict_response['access_token']

		if self.token:
			self.token_expires_in = dict_response['expires_in']
			self.token_timestamp = datetime.now()

		logger.debug( 'Refreshed the access token.' )


	def is_token_expired( self ):
		"""
		Check if the token is expired.

		Returns
		-------
		bool
		"""

		if not self.token:
			return True

		if self.token_timestamp:
			delta = datetime.now() - self.token_timestamp

			if delta.total_seconds() < self.token_expires_in:
				return False

		return True


	def on_load( self ):
		""" Load extension. """

		logger.debug( 'Loading Spotify extension.' )
		registry.feed_handler.register( self.fetch_episodes )


	def on_podcast_save( self, podcast ):
		"""
		Parameters
		----------
		podcast : gpodder.model.PodcastChannel
		"""

		if not isinstance( podcast.url, str ):
			return

		if not podcast.url.startswith( 'https://open.spotify.com/show/' ):
			return

		show_id = podcast.url.replace( 'https://open.spotify.com/show/', '' )
		show_id = show_id.replace( '/', '' )

		logger.debug( 'Show ID: %s' % show_id )

		info = self.get_show_info( show_id )
		podcast.link = podcast.url
		podcast.title = info['name']
		podcast.description = info['description']
		podcast.sync_to_mp3_player = False
		podcast.cover_url = info['images'][1]['url']


	def on_unload( self ):
		""" Unload extension. """

		logger.debug( 'Unloading Spotify extension.' )
		self.token = None

		try:
			registry.feed_handler.unregister( self.fetch_episodes )
		except ValueError:
			pass

