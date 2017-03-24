# SingStar Mic documentation
The SingStar Mic app for Android and iOS is an app that you can use to replace your SingStar microphones with. This is a handy feature and seeing as there are numerous other open source Karaoke programs available, it would make sense to have some interoperability with the SingStar Mic app as it a well written application.

This repository contains the full protocol definition and a simple proof of concept server in python to see how this could work.

## Quick start
If you have python3 installed you should be able to run this without any need for packages or dependencies. After you can open the app on your phone (**make sure you are on the same network**) and discover for services. You should see "Karaoke Party!" and the rest should work.
```
python main.py
```

## Commands
| Module    | Command     | Arguments | Description                                                                                                                                                                                      |
|-----------|-------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| appserver | performance | state     | state can be enable, disable, start or stop which sets the performance in the correct action. When starting a performance it will record the audio from the app into a file named `mic_<ip>.raw` |

## Architecture
```
                  +------------+
                  |  SingStar  |
                  |    App     |
                  |            |
                  |  Android   |
                  |    iOS     |
                  +------------+
                   ^     ^    ^
                 /       |      \
               /         |        \
             /           |          \
           v             v            v
+------------+    +------------+      +------------+
| Discovery  |    |  App/Game  |      | Catalogue  |
|  Service   |    |   Service  |<---->|  Service   |
| UDP 2155   |    | UDP 12000  |      | HTTP 10422 |
+------------+    +------------+      +------------+
```

## Discovery Service
- Port: 2155
- Protocol: UDP

The discovery service is a simple service that waits on UDP broadcasts packets with a specific HTTP kind of request. When it receives this request it returns a HTTP like response describing the name of the service and a host identifier.

### Request
The request looks like this but the `SRCH` keyword does not exists in the HTTP specifications
```
SRCH * HTTP/1.1
ST: device-discovery-protocol-version:00000000
```

### Response
The response looks like this which is actually somewhat according HTTP specifications. However, the headers are **space and case sensitive** which is not according to specs. The `host-type:mic` and `host-request-port:2155` is always the same and probably not being checked against.
```
HTTP/1.1 300 OK
host-name:This is the name
host-type:mic
host-request-port:2155
host-id:fa5fd316-5c1d-4e55-bbc8-b1534245da1e
```

## Catalogue Service
- Port: 10422
- Protocol: HTTP

The catalogue service is a "REST" service that is responsible for serving the playlist and catalogue information to the app. This feature can be used by all people who have the app and are on the same network to add, remove and reorder the songs in the playlist. This playlist information can then be used by the karaoke program to keep playing songs without having an individual do this.

### Data specifications
#### Catalogue
##### JSON Schema
```
{
	"title": "Catalogue",
	"type": "object",
	"properties": {
		"albumUrl": {
			"description": "An image URL where %d will be replaced with the song identifier.",
			"type": "string"
		},
		"songs": {
			"title": "Song",
			"description": "A dictionary of songs where the key is the song identifier. The id can only contain valid characters that are also valid in an URL as it will be used as a replacement for the %d in the albumUrl.",
			"type": "object",
			"properties": {
				"artist": {
					"type": "string"
				},
				"title": {
					"type": "string"
				}
			},
			"required": ["artist", "title"]
		}
	},
	"required": ["albumUrl", "songs"]
}
```

##### JSON Example
```
{
	"albumUrl": "http://192.168.1.100:10422/images/%d",
	"songs": {
		"song-gorillaz-humanz-ascension": {
			"artist": "Gorillaz",
			"title": "Ascension feat. Vince Staples"
		},
		"song-gorillaz-humanz-strobelite": {
			"artist": "Gorillaz",
			"title": "Strobelite feat. Peven Everett"
		},
		"song-gorillaz-humanz-saturnz-barz": {
			"artist": "Gorillaz",
			"title": "Saturnz Barz feat. Popcaan"
		}
	}
}
```

#### Playlist
##### JSON Schema
```
{
	"title": "Playlist",
	"type": "object",
	"properties": {
		"versionId": {
			"description": "A version number that can be used to keep track of version differences between different devices.",
			"type": "integer"
		},
		"array": {
			"title": "Array",
			"description": "An array of songs which also defined the order of the playlist.",
			"type": "array",
			"items": {
				"type": "object",
				"properties": {
					"entryId": {
						"type": "integer",
						"description": "Identifier of this song in the playlist, this will also be used as reference for moving and deletion."
					},
					"songId": {
						"type": "string",
						"description": "Exact same identifier as being used in the songs dictionary in the catalogue."
					},
					"state": {
						"type": "string",
						"enum": ["played", "nextup", "queued", "currentPlaying", "none"]
					}
				},
				"required": ["entryId", "songId", "state"]
			}
		}
	},
	"required": ["versionId", "array"]
}
```

##### JSON Example
```
{
	"versionId": 12,
	"array": [
		{
			"entryId": 1,
			"songId": "song-gorillaz-humanz-ascension",
			"state": "nextUp"
		},
		{
			"entryId": 0,
			"songId": "song-gorillaz-humanz-strobelite",
			"state": "currentPlaying"
		},
		{
			"entryId": 2,
			"songId": "song-gorillaz-humanz-saturnz-barz",
			"state": "none"
		}
	]
}
```

### Endpoints
#### GET getCatalogue
Returns the catalogue in the JSON specified above.

#### GET getPlaylist
Return the playlist in the JSON format specified above.

#### POST addPlaylist
This endpoint is responsible for adding zero or more songs from the catalogue to the current playlist. After this is done the app/game service has to tell all clients to refresh the playlist.

The body of the request will contain pseudo JSON in the following format `[song-id, song-id-2, etc]`. The identifiers are also not quoted which lets me to believe it actually should be numeric but this is not enforced.

This endpoint does not return data.

#### POST orderPlaylist
This endpoint is called when moving a song in the playlist to another position within the same playlist (drag and drop). After this is done the app/game service has to tell all clients to refresh the playlist.

The body of the request is actual JSON in the following format `{"versionId": x, "entryId": y, "offset": z}`. The offset can be positive or negative as it is the offset relative to the current position in the list.

This endpoint does not return data.

#### POST deletePlaylist
This endpoint is called when deleting zero or more songs from a playlist. After this is done the app/game service has to tell all clients to refresh the playlist.

The body of the request is actual JSON in the following format `{"versionId": x, "array": [entryId, entryId]}`. All the entries in the array should be deleted from the playlist.

This endpoint does not return data.

## App/Game Service
- Port: 12000
- Protocol: UDP
- Byte order: BIG_ENDIAN
- Packet size: 800
- Max packet size: 8000

### Audio format
- 16-bit PCM
- Default byte order
- Raw data
- Mono
- 16000 Hz

TODO

## Disclaimer
This work is completely done by me and purely for educational purposes.
