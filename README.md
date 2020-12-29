# gPodder Extension for Spotify

The goal is to be able to add podcasts on Spotify to gPodder. Downloading the episodes will *not* be possible, but being notified of new episodes.


## Tested with

* gPodder 3.10.16 on Ubuntu 18.04 with Python 3.6.9/3.8.0
* gPodder 3.10.1 on Ubuntu 18.04 with Python 3.6.9/3.8.0


## Install

1. Copy `spotify.py` to `$HOME/gPodder/Extensions/`. Create the directory if it does not exist.
2. Create a Spotify account if you don't have one.
3. Create an application entry on: https://developer.spotify.com/dashboard/applications
4. From your application copy the Client ID and Client Secret and assign them in `spotify.py` to the variables `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` respectively.


## Uninstall

1. Remove the file `spotify.py` from `$HOME/gPodder/Extensions/`.
2. Remove the file `spotify_cache` from `$HOME/gPodder/`.


## TODO

* Load *all* episodes of a show, not just the last 50
	* The show info response contains the total number of episodes as "total"
* Login window: Close after success, show message
* "gtk-open" in context menu should not mark an episode as played (remove entry altogether?)
* Test again with gPodder 3.10.16
