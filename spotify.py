# -*- coding: utf-8 -*-

from datetime import datetime
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

import base64
import copy
import hashlib
import importlib
import json
import logging
import os
import secrets
import time

import gpodder
from gpodder import feedcore, model

from gi.repository import Gtk, WebKit2



# Spotify application information.
# An application can be created here for a client ID:
# https://developer.spotify.com/dashboard/applications
SPOTIFY_CLIENT_ID = 'afe692b6116c4eeca210be215bc88d62'

SPOTIFY_API_ACCOUNT = 'https://accounts.spotify.com/api/token'
SPOTIFY_API_V1 = 'https://api.spotify.com/v1'

SPOTIFY_REDIRECT_URI = 'gpodder://spotify-extension/callback/'

SPOTIFY_OAUTH = 'https://accounts.spotify.com/authorize'
SPOTIFY_OAUTH += '?response_type=code'
SPOTIFY_OAUTH += '&client_id=' + SPOTIFY_CLIENT_ID
SPOTIFY_OAUTH += '&redirect_uri=' + quote( SPOTIFY_REDIRECT_URI, safe = '~()*!.\'' )
SPOTIFY_OAUTH += '&code_challenge_method=S256'

# gPodder extension information.
__title__ = 'Spotify Extension'
__description__ = 'Check for new episodes in Spotify podcasts.'
__authors__ = 'Sebastian Dorn'
__doc__ = 'https://github.com/sebadorn/gpodder-spotify-extension'
__version__ = '1.1.0'



logger = logging.getLogger( __name__ )



class SpotifyAPI:


	def do_api_request( self, url_path ):
		"""
		Parameters
		----------
		url_path : str

		Returns
		-------
		dict
		"""

		token = self.get_token()

		if not token:
			logger.error( 'Cannot do API request. No token available.' )
			return None

		url = '%s/shows/%s' % ( SPOTIFY_API_V1, url_path )

		logger.debug( 'Sending API request.' )

		request = Request(
			url,
			headers = {
				'Accept': 'application/json',
				'Authorization': 'Bearer ' + token,
				'Content-Type': 'application/json'
			}
		)

		resource = urlopen( request )
		charset = resource.headers.get_content_charset()
		json_data = resource.read().decode( charset )

		response_dict = json.loads( json_data )
		response_dict['_headers'] = {}

		etag = resource.headers.get( 'etag' )
		last_modified = resource.headers.get( 'last-modified' )

		if etag:
			response_dict['_headers']['etag'] = etag

		if last_modified:
			response_dict['_headers']['last_modified'] = last_modified

		return response_dict


	def get_show_episodes( self, show_id, max_episodes = 0 ):
		"""
		Parameters
		----------
		show_id      : str
		max_episodes : int

		Returns
		-------
		list of dicts
		"""

		# 50 episodes at once is currently the maximum.
		LIMIT_MAX = 50

		if max_episodes == 0:
			max_episodes = LIMIT_MAX
		else:
			max_episodes = max( 1, min( LIMIT_MAX, max_episodes ) )

		url = '%s/episodes?limit=%d' % ( show_id, max_episodes )

		return self.do_api_request( url )['items']


	def get_show_info( self, show_id ):
		"""
		Parameters
		----------
		show_id : str

		Returns
		-------
		dict, dict
		"""

		return self.do_api_request( show_id )


	def get_token( self ):
		"""
		Get a token to use in API requests.

		Returns
		-------
		str or None
		"""

		user = spotify_cache.get_user()

		if not SpotifyAPI.is_token_expired( user ) and 'access_token' in user:
			return user['access_token'];

		logger.debug( 'Refreshing access token...' )

		post_data = urlencode( {
			'grant_type': 'refresh_token',
			'refresh_token': user['refresh_token'],
			'client_id': SPOTIFY_CLIENT_ID
		} )

		request = Request(
			SPOTIFY_API_ACCOUNT,
			data = post_data.encode(),
			headers = {
				'Accept': 'application/json',
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			method = 'POST'
		)

		json_response = urlopen( request ).read().decode()
		dict_response = json.loads( json_response )

		if 'access_token' not in dict_response:
			logger.error( 'Server response did not contain an access token.' )
			return None

		spotify_cache.set_user_info( dict_response )

		logger.debug( 'Refreshed the access token.' )

		return dict_response['access_token']


	@staticmethod
	def is_token_expired( user ):
		"""
		Check if the token is expired.

		Parameters
		----------
		user : dict

		Returns
		-------
		bool
		"""

		if 'expires_at' not in user:
			return True

		now_seconds = int( time.time() )
		is_expired = now_seconds >= int( user['expires_at'] )

		if is_expired:
			logger.debug( 'Token is expired.' )

		return is_expired


	@staticmethod
	def build_oauth_url():
		"""
		Returns
		-------
		str
		"""

		verifier = SpotifyAPI.generate_code_verifier()
		challenge = SpotifyAPI.generate_code_challenge( verifier )
		state = SpotifyAPI.generate_state()

		url = SPOTIFY_OAUTH
		url += '&code_challenge=' + challenge
		url += '&state=' + state

		return url


	@staticmethod
	def generate_code_challenge( verifier ):
		"""
		Parameters
		----------
		verifier : str

		Returns
		-------
		str
		"""

		verifier_sha256 = hashlib.sha256( verifier.encode( 'utf-8' ) ).digest()

		code_challenge = base64.urlsafe_b64encode( verifier_sha256 ).decode( 'utf-8' )
		code_challenge = code_challenge.replace( '=', '' )

		return code_challenge


	@staticmethod
	def generate_code_verifier():
		"""
		Generates a verifier for use in OAuth2. The value will be
		cached for runtime and returned in all further calls.

		Returns
		-------
		str
		"""

		if SpotifyAPI._verifier:
			return SpotifyAPI._verifier

		verifier = secrets.token_urlsafe( nbytes = 64 )

		SpotifyAPI._verifier = verifier

		return verifier


	@staticmethod
	def generate_state():
		"""
		Generates a state for use in OAuth2. The value will be
		cached for runtime and returned in all further calls.

		Returns
		-------
		str
		"""

		if SpotifyAPI._oauth_state:
			return SpotifyAPI._oauth_state

		SpotifyAPI._oauth_state = secrets.token_urlsafe( nbytes = 16 )

		return SpotifyAPI._oauth_state


	@staticmethod
	def request_access_token( authorization_code ):
		"""
		Parameters
		----------
		authorization_code : str
		"""

		logger.debug( 'Requesting access token.' )

		post_data = urlencode( {
			'client_id': SPOTIFY_CLIENT_ID,
			'grant_type': 'authorization_code',
			'code': authorization_code,
			'code_verifier': SpotifyAPI.generate_code_verifier(),
			'redirect_uri': SPOTIFY_REDIRECT_URI
		} )

		request = Request(
			SPOTIFY_API_ACCOUNT,
			data = post_data.encode(),
			headers = {
				'Accept': 'application/json',
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			method = 'POST'
		)

		json_response = urlopen( request ).read().decode()
		dict_response = json.loads( json_response )

		logger.debug( 'Received access token.' )

		spotify_cache.set_user_info( dict_response )

		# We have the tokens and can now forget
		# the OAuth2 verifier and state.
		SpotifyAPI.reset_oauth_temp_data()


	@staticmethod
	def reset_oauth_temp_data():
		""" """

		SpotifyAPI._oauth_state = None
		SpotifyAPI._verifier = None


SpotifyAPI.reset_oauth_temp_data()



class SpotifyCacheHandler:


	def delete_podcast_info( self, show_id ):
		"""
		Parameters
		----------
		show_id : str
		"""

		if show_id in self.cache_info['podcasts']:
			self.cache_info['podcasts'].pop( show_id, None )
			self.save_cache_file()


	def get_podcast( self, show_id ):
		"""
		Parameters
		----------
		show_id : str

		Returns
		-------
		dict or None
		"""

		if show_id in self.cache_info['podcasts']:
			return self.cache_info['podcasts'][show_id]

		return None


	def get_user( self ):
		"""
		Returns
		-------
		dict or None
		"""

		return self.cache_info['user']


	def load( self ):
		""" """

		self.cache_file = os.path.join( gpodder.home, 'spotify_cache' )

		if os.path.exists( self.cache_file ):
			try:
				with open( self.cache_file, 'r' ) as f:
					self.cache_info = json.load( f )
			except:
				self.cache_info = None
		else:
			self.cache_info = None

		if not self.cache_info:
			self.cache_info = {}

		if 'podcasts' not in self.cache_info:
			self.cache_info['podcasts'] = {}

		if 'user' not in self.cache_info:
			self.cache_info['user'] = {}


	def save_cache_file( self ):
		""" """

		try:
			with open( self.cache_file, 'w' ) as f:
				json.dump( self.cache_info, f )
		except Exception as exc:
			logger.error( exc )


	def set_podcast_info( self, show_id, info ):
		"""
		Parameters
		----------
		show_id : str
		info    : dict
		"""

		# Copy the info dictionary and remove
		# some big, but unnecessary attributes.
		info_copy = copy.deepcopy( info )
		info_copy.pop( 'available_markets', None )
		info_copy.pop( 'episodes', None )

		self.cache_info['podcasts'][show_id] = info_copy
		self.save_cache_file()


	def set_user_info( self, info ):
		"""
		Parameters
		----------
		info : dict
		"""

		if 'access_token' in info:
			self.cache_info['user']['access_token'] = info['access_token']

		if 'refresh_token' in info:
			self.cache_info['user']['refresh_token'] = info['refresh_token']

		if 'scope' in info:
			self.cache_info['user']['scope'] = info['scope']

		# Time period in seconds the token is valid for.
		if 'expires_in' in info:
			now_seconds = int( time.time() )
			self.cache_info['user']['expires_at'] = now_seconds + int( info['expires_in'] )

		self.save_cache_file()



class SpotifyFeed( object ):


	def __init__( self, show_id, max_episodes = 0 ):
		"""
		Parameters
		----------
		show_id      : str
		max_episodes : int
		"""

		self.show_id = show_id
		self.max_episodes = int( max_episodes )


	def get_cover_url( self ):
		"""
		Returns
		-------
		str
		"""

		return self.get_image()


	def get_description( self ):
		"""
		Returns
		-------
		str
		"""

		info = spotify_cache.get_podcast( self.show_id )

		if info:
			return info['description']

		info = spotify_api.get_show_info( self.show_id )
		spotify_cache.set_podcast_info( self.show_id, info )

		return info['description']


	def get_http_etag( self ):
		"""
		Returns
		-------
		str or None
		"""

		info = spotify_cache.get_podcast( self.show_id )

		if info and '_headers' in info:
			if 'etag' in info['_headers']:
				return info['_headers']['etag']

		return None


	def get_http_last_modified( self ):
		"""
		Returns
		-------
		str or None
		"""

		info = spotify_cache.get_podcast( self.show_id )

		if info and '_headers' in info:
			if 'last_modified' in info['_headers']:
				return info['_headers']['last_modified']

		return None


	def get_image( self ):
		"""
		Returns
		-------
		str
		"""

		info = spotify_cache.get_podcast( self.show_id )

		if info:
			return info['images'][1]['url']

		info = spotify_api.get_show_info( self.show_id )
		spotify_cache.set_podcast_info( self.show_id, info )

		return info['images'][1]['url']


	def get_link( self ):
		"""
		Returns
		-------
		str
		"""

		return 'https://open.spotify.com/show/%s' % self.show_id


	def get_next_page( self, channel, max_episodes ):
		""" """

		return None


	def get_payment_url( self ):
		""" """

		return None


	def get_title( self ):
		"""
		Returns
		-------
		str
		"""

		info = spotify_cache.get_podcast( self.show_id )

		if info:
			return info['name']

		info = spotify_api.get_show_info( self.show_id )
		spotify_cache.set_podcast_info( self.show_id, info )

		return info['name']


	def get_new_episodes( self, channel, existing_guids ):
		"""
		Parameters
		----------
		channel        : gpodder.model.PodcastChannel
		existing_guids : list of str

		Returns
		-------
		list of dicts, list of str
		"""

		episodes = spotify_api.get_show_episodes( self.show_id, self.max_episodes )

		new_episodes = []
		seen_guids = []

		for episode in episodes:
			seen_guids.append( episode['id'] )

			if episode['id'] not in existing_guids:
				rd = episode['release_date'].split( '-' )
				published = time.mktime( ( int( rd[0] ), int( rd[1] ), int( rd[2] ), 0, 0, 0, 0, 0, 0 ) )

				new_episode = channel.episode_factory( {
					'description': episode.get('description', ''),
					'file_size': -1,
					'guid': episode['id'],
					'link': episode['external_urls']['spotify'],
					'mime_type': 'text/html',
					'published': published,
					'title': episode['name'],
					'total_time': episode.get('duration_ms', 0) / 1000,
					'url': episode['external_urls']['spotify']
				} )
				new_episode.save()
				new_episodes.append( new_episode )

		return new_episodes, seen_guids


	@classmethod
	def fetch_episodes( cls, channel, max_episodes = 0 ):
		"""
		Used in gPodder 3.10.16 but not 3.10.1.

		Parameters
		----------
		channel      : gpodder.model.PodcastChannel
		max_episodes : int
		"""

		return feedcore.Result( feedcore.UPDATED_FEED, cls.handle_url( channel.url, max_episodes ) )


	@classmethod
	def handle_url( cls, url, max_episodes = 0 ):
		"""
		Parameters
		----------
		url          : str
		max_episodes : int
		"""

		show_id = cls.extract_show_id( url )

		if isinstance( show_id, str ):
			return cls( show_id, max_episodes )


	@staticmethod
	def extract_show_id( url ):
		"""
		Parameters
		----------
		url : str
		"""

		if not isinstance( url, str ):
			return None

		if not url.startswith( 'https://open.spotify.com/show/' ):
			return None

		show_id = url.replace( 'https://open.spotify.com/show/', '' )
		show_id = show_id.replace( '/', '' )

		if len( show_id ) < 1:
			return None

		return show_id



class gPodderExtension:


	def __init__( self, container ):
		"""
		Parameters
		----------
		container : gpodder.extensions.ExtensionContainer
		"""

		self.container = container


	def _handle_oauth_redirect( self, uri ):
		"""
		Parameters
		----------
		uri : str
		"""

		uri_dict = urlparse( uri )
		query = parse_qs( uri_dict.query )

		is_valid = True

		if 'state' in query:
			state = query['state'][0]

			if state != SpotifyAPI.generate_state():
				logger.error( 'State in response does not match send state. OAuth failed.' )
				is_valid = False
		else:
			logger.error( 'State missing in response. OAuth failed.' )
			is_valid = False

		if 'error' in query:
			error = query['error'][0]
			logger.error( 'Failed to authorize. Error response: %s' % error )
			is_valid = False

		if not is_valid:
			return

		if 'code' in query:
			authorization_code = query['code'][0]
			logger.debug( 'Received authorization code.' )

		if authorization_code:
			SpotifyAPI.request_access_token( authorization_code )
		else:
			logger.error( 'No authorization code received in response.' )


	def _open_settings( self ):
		""" """

		settings = WebKit2.Settings()
		settings.set_enable_java( False )
		settings.set_enable_plugins( False )
		settings.set_enable_javascript( True )

		webview_oauth = WebKit2.WebView.new_with_settings( settings )
		webview_oauth.set_property( 'expand', True )
		webview_oauth.connect( 'load-changed', self._webview_oauth_changed )
		webview_oauth.load_uri( SpotifyAPI.build_oauth_url() )

		vbox = Gtk.Box(
			orientation = Gtk.Orientation.VERTICAL,
			spacing = 6
		)
		vbox.pack_start( webview_oauth, True, True, 0 )

		win = Gtk.Window( title = 'Extension: Spotify' )
		win.set_border_width( 10 )
		win.add( vbox )

		win.show_all()


	def _webview_oauth_changed( self, webview, load_event ):
		"""
		Parameters
		----------
		webview    : gi.repository.WebKit2.WebView
		load_event : gi.repository.WebKit2.LoadEvent
		"""

		if load_event is WebKit2.LoadEvent.REDIRECTED:
			uri = webview.get_uri()

			if uri.startswith( SPOTIFY_REDIRECT_URI ):
				self._handle_oauth_redirect( uri )


	def on_create_menu( self ):
		""" """

		menu_item = (
			'Spotify: Settings',
			self._open_settings
		)

		return [menu_item]


	def on_episodes_context_menu( self, episodes ):
		"""
		Parameters
		----------
		episodes : list of gpodder.model.PodcastEpisode

		Returns
		-------
		list of tupels
		"""

		def openInBrowser( episodes ):
			for episode in episodes:
				gpodder.util.open_website( episode.link )

		return [(
			'Open in web browser',
			openInBrowser
		)]


	def on_load( self ):
		""" Load extension. """

		logger.debug( 'Loading Spotify extension.' )

		spotify_cache.load()

		try:
			# gPodder 3.10.16
			registry = importlib.import_module( 'gpodder.registry' )
			registry.feed_handler.register( SpotifyFeed.fetch_episodes )
		except ModuleNotFoundError:
			# gPodder 3.10.1
			logger.debug( 'gpodder.registry module not found. Using fallback to "register_custom_handler".' )
			model.register_custom_handler( SpotifyFeed )


	def on_podcast_delete( self, channel ):
		"""
		Parameters
		----------
		channel : gpodder.model.Model (3.10.1) or
				  gpodder.model.PodcastChannel (3.10.16)
		"""

		# NOTE (gPodder 3.10.1):
		# Theoretically that is how it should be done. But
		# gPodder does not actually passes the channel,
		# only a model without any channel information. We do
		# not know which podcast/channel has been removed.

		if not isinstance( channel, gpodder.model.PodcastChannel ):
			return

		show_id = SpotifyFeed.extract_show_id( channel.url )

		if isinstance( show_id, str ):
			feed = SpotifyFeed( show_id )
			spotify_cache.delete_podcast_info( show_id )


	def on_podcast_save( self, channel ):
		"""
		Parameters
		----------
		channel : gpodder.model.PodcastChannel
		"""

		channel.sync_to_mp3_player = False


	def on_unload( self ):
		""" Unload extension. """

		logger.debug( 'Unloading Spotify extension.' )

		try:
			# gPodder 3.10.16
			registry = importlib.import_module( 'gpodder.registry' )
			registry.feed_handler.unregister( SpotifyFeed.fetch_episodes )
		except ModuleNotFoundError:
			logger.debug( 'gpodder.registry module not found.' )



spotify_cache = SpotifyCacheHandler()
spotify_api = SpotifyAPI()
