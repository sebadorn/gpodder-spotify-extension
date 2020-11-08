# -*- coding: utf-8 -*-

from datetime import datetime
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

import base64, copy, importlib, json, logging, os, time

import gpodder
from gpodder import feedcore, model

from gi.repository import Gtk, WebKit2



# Spotify application information.
# An application can be created here for a client ID:
# https://developer.spotify.com/dashboard/applications
SPOTIFY_CLIENT_ID = ''

SPOTIFY_API_ACCOUNT = 'https://accounts.spotify.com/api/token'
SPOTIFY_API_V1 = 'https://api.spotify.com/v1'

SPOTIFY_REDIRECT_URI = 'gpodder://spotify-extension/callback/'

SPOTIFY_OAUTH = 'https://accounts.spotify.com/authorize'
SPOTIFY_OAUTH += '?response_type=code'
SPOTIFY_OAUTH += '&client_id=' + SPOTIFY_CLIENT_ID
SPOTIFY_OAUTH += '&redirect_uri=' + quote( SPOTIFY_REDIRECT_URI, safe = '~()*!.\'' )

# gPodder extension information.
__title__ = 'Spotify Extension'
__description__ = 'Check for new episodes in Spotify podcasts.'
__authors__ = 'Sebastian Dorn'
__doc__ = 'https://github.com/sebadorn/gpodder-spotify-extension'
__version__ = '1.0.0'



logger = logging.getLogger( __name__ )



class SpotifyAPI:


	def __init__( self ):
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

		logger.debug( 'Sending API request.' )

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


	def get_show_episodes( self, show_id ):
		"""
		Parameters
		----------
		show_id : str

		Returns
		-------
		list of dicts
		"""

		url = '%s/episodes?market=%s' % ( show_id, SPOTIFY_MARKET )

		return self.do_api_request( url )['items']


	def get_show_info( self, show_id ):
		"""
		Parameters
		----------
		show_id : str

		Returns
		-------
		dict
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



class SpotifyCacheHandler:


	def delete_podcast_info( self, show_id ):
		"""
		Parameters
		----------
		show_id : str
		"""

		if self.cache_info['podcasts'][show_id]:
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

		return self.cache_info['podcasts'][show_id]


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

		if not self.cache_info['podcasts']:
			self.cache_info['podcasts'] = {}

		if not self.cache_info['user']:
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



class SpotifyFeed( object ):


	def __init__( self, show_id ):
		"""
		Parameters
		----------
		show_id : str
		"""

		self.show_id = show_id


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
		""" """
		return None


	def get_http_last_modified(self):
		""" """
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

		episodes = spotify_api.get_show_episodes( self.show_id )

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

		return feedcore.Result( feedcore.UPDATED_FEED, cls.handle_url( channel.url ) )


	@classmethod
	def handle_url( cls, url ):
		"""
		Parameters
		----------
		url : str
		"""

		show_id = cls.extract_show_id( url )

		if isinstance( show_id, str ):
			return cls( show_id )


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


	def _open_settings( self ):
		""" """

		settings = WebKit2.Settings()
		settings.set_enable_java( False )
		settings.set_enable_plugins( False )
		settings.set_enable_javascript( True )

		webview_oauth = WebKit2.WebView.new_with_settings( settings )
		webview_oauth.set_property( 'expand', True )
		webview_oauth.connect( 'load-changed', self._webview_oauth_changed )
		webview_oauth.load_uri( SPOTIFY_OAUTH )

		btn_save = Gtk.Button.new_with_label( 'Save' )

		vbox = Gtk.Box(
			orientation = Gtk.Orientation.VERTICAL,
			spacing = 6
		)
		vbox.pack_start( webview_oauth, True, True, 0 )
		vbox.pack_start( btn_save, False, False, 0 )

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
				uri_dict = urlparse( uri )
				query = parse_qs( uri_dict.query )

				# TODO:
				logger.debug( 'OAuth refresh token: ' + query['code'][0] )


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
