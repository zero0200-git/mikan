# How to use
## 1. Setup config.ini file
### Run `python mdcli.py setup` to config and add/reset user
### *need ssl certificate to function*
#### `db_location` is a manga db location
#### `ssl_crt_location` is a ssl cert file location
#### `ssl_key_location` is a ssl key file location
#### `port` is a server port
#### `host` is a server host
#### `secret` is a secret for login hash
#### `token_valid_time` is a login token valid use time
#### `strictlogin` is for more strict token usage request
## 2. Start server by run `runauto.sh`
#### or `run.sh` or `python mdweb.py` or `python3 mdweb.py`
## 3. Go to https://`host`:`port`/web
And login with previous setup user
## 4. Go to Settings tab and config location
### usable format for `Save format` and `Cover image location`
##### `_%{serie}%_` will replace with manga title
##### `_%{authors}%_` will replace with authors
##### `_%{artists}%_` will replace with artists
### usable format for `Save format`
##### `_%{group}%_` will replace with chapter translation group
##### `_%{volume}%_` will replace with chapter volume number
##### `_%{chapter}%_` will replace with chapter number
##### `_%{title}%_` will replace with chapter title
##### `_%{page}%_` will replace with chapter image page
##### `_%{extension}%_` will replace with chapter image extension
##### `_%{lang_short}%_` will replace with short chapter language (eg. en, jp)
### additional format
##### `_%x{value}x%_` will add `x` if have value eg. `_%group [{group}]%_` will be `group ["translate_group"]` if have translate group name in chapter or ` `(nothing) if it not have
#### `_%{value:>0x}%_` will add 0 if value length less than x eg. `_%{page:>03}%_` will be `023` or `004.5` if it has decimal
## 5. Go to Search tab to start adding first manga
#### `right click for more action`
