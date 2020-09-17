# gPodder Extension for Spotify

The goal is to be able to add podcasts on Spotify to gPodder. Downloading the episodes will *not* be possible, but being notified of new episodes.


## Tested with

* gPodder 3.10.1 on Ubuntu 18.04


## Install

1. Copy `spotify.py` to `$HOME/gPodder/Extensions/`. Create the directory if it does not exist.
2. Create a Spotify account if you don't have one.
3. Create an application entry on: https://developer.spotify.com/dashboard/applications
4. From your application copy the Client ID and Client Secret and assign them in `spotify.py` to the variables `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` respectively.


## Uninstall

1. Remove the file `spotify.py` from `$HOME/gPodder/Extensions/`.
2. Remove the file `spotify_cache` from `$HOME/gPodder/`.


## curl example

```bash
$ curl --basic -u <CLIENT_ID>:<CLIENT_SECRET> \
	--request POST \
	-d grant_type=client_credentials \
	https://accounts.spotify.com/api/token
{"access_token":"<TOKEN>","token_type":"Bearer","expires_in":3600,"scope":""}
```

`<CLIENT_ID>` and `<CLIENT_SECRET>` have to be replaced with the values for your application.

```bash
$ curl -X "GET" "https://api.spotify.com/v1/shows/<SHOW_ID>/episodes?market=DE" \
	-H "Accept: application/json" \
	-H "Content-Type: application/json" \
	-H "Authorization: Bearer <TOKEN>"
```
