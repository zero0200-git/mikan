# Mikan
A web GUI manga downloader written in Python using only the standard library

[Source(Github)](https://github.com/zero0200-git/mikan) or [Download](https://github.com/zero0200-git/mikan/archive/refs/heads/main.zip)

<details>
    <summary>Supported Sources</summary>

* ### Mangadex
</details>

<details>
    <summary>WebUI Screenshot</summary>

![search page option](/ss/01_add.png "search page option")
![search page](/ss/02_search.png "search page")
![series page option](/ss/03_serie-opt.png "series page option")
![series page filter](/ss/04_serie-filter.png "series page filter")
![series page sort](/ss/05_series-sort.png "series page sort")
![progress page](/ss/06_queue.png "progress page")
![progress page complete](/ss/07_queue-complete.png "progress page complete")
![settings page](/ss/08_settings.png "settings page")

</details>

## How to Use

### 1. Setup config.ini file
Run `python mdcli.py setup` to configure and add/reset users.  
**Note:** SSL certificate is required for functionality.

<details>
    <summary>Using config file from different location</summary>

Provide file path via `MIKAN_CONFIG_FILE` environment variable
</details>

### Configuration Options
- `db_location` - Manga database location
- `ssl_crt_location` - SSL certificate file location  
- `ssl_key_location` - SSL key file location
- `port` - Server port
- `host` - Server host address
- `secret` - Secret key for login hash
- `token_valid_time` - Login token validity duration
- `strictlogin` - Enable stricter token validation

### 2. Start Server
Choose one of these methods:
- Run `runauto.sh`
- Run `run.sh` 
- Run `python mdweb.py`

### 3. Access Web Interface
1. Open `https://<host>:<port>/web` in your browser
2. Login with your configured user credentials

### 4. Configure Save Settings
Click on "Settings" tab to configure save locations.


#### Format Variables
##### Available in both `Save format` and `Cover image location`:
- `_%{serie}%_` - Manga title
- `_%{authors}%_` - Author names
- `_%{artists}%_` - Artist names

##### Available only in `Save format`:
- `_%{group}%_` - Translation group name
- `_%{volume}%_` - Chapter volume number
- `_%{chapter}%_` - Chapter number
- `_%{title}%_` - Chapter title
- `_%{page}%_` - Image page number
- `_%{extension}%_` - Image file extension
- `_%{lang_short}%_` - Language code (e.g. en, jp)

#### Format Modifiers
- `_%x{value}x%_` - Adds `x` if value exists
  - Example: `_%group [{group}]%_` (`_%{group}%_`) becomes `group ["translate_group"]` or empty string
- `_%{value:>0x}%_` - Zero-pads value to x digits
  - Example: `_%{page:>03}%_` (`_%{page}%_`) becomes `023` or `004.5`

### 5. Add Manga
1. Go to Search tab
2. Search and add your first manga
3. *Right-click table entries for additional options*