from typing import Dict, Any, List

# High-Signal, Verified Platforms with Strict Zero-False-Positive Rules
SITES_CATALOG: List[Dict[str, Any]] = [
    # --- SOCIAL PLATFORMS ---
    {
        "name": "Instagram", "category": "Social",
        "url_template": "https://www.instagram.com/{}/",
        "check_type": "special_api", "special_handler": "instagram"
    },
    {
        "name": "TikTok", "category": "Social",
        "url_template": "https://www.tiktok.com/@{}",
        "check_type": "special_api", "special_handler": "tiktok"
    },
    {
        "name": "Twitter / X", "category": "Social",
        "url_template": "https://x.com/{}",
        "check_type": "special_api", "special_handler": "twitter"
    },
    {
        "name": "Pinterest", "category": "Social",
        "url_template": "https://www.pinterest.com/{}/",
        "check_type": "special_api", "special_handler": "pinterest"
    },
    {
        "name": "Facebook", "category": "Social",
        "url_template": "https://www.facebook.com/{}",
        "check_type": "special_api", "special_handler": "facebook"
    },
    {
        "name": "Reddit", "category": "Social",
        "url_template": "https://www.reddit.com/user/{}/",
        "profile_url": "https://www.reddit.com/user/{}/",
        "check_type": "special_api", "special_handler": "reddit"
    },
    {
        "name": "Telegram", "category": "Social",
        "url_template": "https://t.me/{}",
        "check_type": "special_api", "special_handler": "telegram"
    },
    {
        "name": "Bluesky", "category": "Social",
        "url_template": "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={}.bsky.social",
        "profile_url": "https://bsky.app/profile/{}.bsky.social",
        "check_type": "special_api", "special_handler": "bluesky"
    },
    {
        "name": "Snapchat", "category": "Social",
        "url_template": "https://www.snapchat.com/add/{}",
        "check_type": "special_api", "special_handler": "snapchat"
    },
    {
        "name": "Tumblr", "category": "Social",
        "url_template": "https://{}.tumblr.com",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Quora", "category": "Social",
        "url_template": "https://www.quora.com/profile/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Patreon", "category": "Social",
        "url_template": "https://www.patreon.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Disqus", "category": "Social",
        "url_template": "https://disqus.com/by/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Flickr", "category": "Social",
        "url_template": "https://www.flickr.com/people/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Wattpad", "category": "Social",
        "url_template": "https://www.wattpad.com/user/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Goodreads", "category": "Social",
        "url_template": "https://www.goodreads.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Linktree", "category": "Social",
        "url_template": "https://linktr.ee/{}",
        "check_type": "status_code",
        "error_code": 404
    },

    # --- DEVELOPER & TECH ---
    {
        "name": "GitHub", "category": "Developer",
        "url_template": "https://api.github.com/users/{}",
        "profile_url": "https://github.com/{}",
        "check_type": "special_api", "special_handler": "github"
    },
    {
        "name": "GitLab", "category": "Developer",
        "url_template": "https://gitlab.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Bitbucket", "category": "Developer",
        "url_template": "https://bitbucket.org/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "StackOverflow", "category": "Developer",
        "url_template": "https://stackoverflow.com/users/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "DockerHub", "category": "Developer",
        "url_template": "https://hub.docker.com/u/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "NPM", "category": "Developer",
        "url_template": "https://www.npmjs.com/~{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "PyPI", "category": "Developer",
        "url_template": "https://pypi.org/user/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "HackerNews", "category": "Developer",
        "url_template": "https://news.ycombinator.com/user?id={}",
        "check_type": "message",
        "error_message": "No such user"
    },
    {
        "name": "Dev.to", "category": "Developer",
        "url_template": "https://dev.to/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Replit", "category": "Developer",
        "url_template": "https://replit.com/@{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "CodePen", "category": "Developer",
        "url_template": "https://codepen.io/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "LeetCode", "category": "Developer",
        "url_template": "https://leetcode.com/u/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Codeforces", "category": "Developer",
        "url_template": "https://codeforces.com/profile/{}",
        "check_type": "status_code",
        "error_code": 404
    },

    # --- GAMING PLATFORMS ---
    {
        "name": "Steam", "category": "Gaming",
        "url_template": "https://steamcommunity.com/id/{}/?xml=1",
        "profile_url": "https://steamcommunity.com/id/{}/",
        "check_type": "special_api", "special_handler": "steam"
    },
    {
        "name": "Twitch", "category": "Gaming",
        "url_template": "https://www.twitch.tv/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Roblox", "category": "Gaming",
        "url_template": "https://www.roblox.com/user.aspx?username={}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Chess.com", "category": "Gaming",
        "url_template": "https://api.chess.com/pub/player/{}",
        "profile_url": "https://www.chess.com/member/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Lichess", "category": "Gaming",
        "url_template": "https://lichess.org/@/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Speedrun.com", "category": "Gaming",
        "url_template": "https://speedrun.com/user/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Newgrounds", "category": "Gaming",
        "url_template": "https://{}.newgrounds.com",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "OSU!", "category": "Gaming",
        "url_template": "https://osu.ppy.sh/users/{}",
        "check_type": "status_code",
        "error_code": 404
    },

    # --- MEDIA & MUSIC ---
    {
        "name": "Spotify", "category": "Media",
        "url_template": "https://open.spotify.com/user/{}",
        "check_type": "special_api", "special_handler": "spotify"
    },
    {
        "name": "SoundCloud", "category": "Media",
        "url_template": "https://soundcloud.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Bandcamp", "category": "Media",
        "url_template": "https://bandcamp.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Behance", "category": "Media",
        "url_template": "https://www.behance.net/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Dribbble", "category": "Media",
        "url_template": "https://dribbble.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "DeviantArt", "category": "Media",
        "url_template": "https://www.deviantart.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Vimeo", "category": "Media",
        "url_template": "https://vimeo.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Letterboxd", "category": "Media",
        "url_template": "https://letterboxd.com/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Last.fm", "category": "Media",
        "url_template": "https://www.last.fm/user/{}",
        "check_type": "status_code",
        "error_code": 404
    },

    # --- CRYPTO ---
    {
        "name": "OpenSea", "category": "Crypto",
        "url_template": "https://opensea.io/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Keybase", "category": "Crypto",
        "url_template": "https://keybase.io/{}",
        "check_type": "status_code",
        "error_code": 404
    },

    # --- REGIONAL PACKS (Strictly gated by target country) ---
    {
        "name": "FXP", "category": "Regional", "country": "il",
        "url_template": "https://www.fxp.co.il/member.php?username={}",
        "check_type": "status_code", "error_code": 404
    },
    {
        "name": "Tapuz", "category": "Regional", "country": "il",
        "url_template": "https://www.tapuz.co.il/members/{}/",
        "check_type": "status_code", "error_code": 404
    },
    {
        "name": "Stips", "category": "Regional", "country": "il",
        "url_template": "https://stips.co.il/profile/{}",
        "check_type": "status_code", "error_code": 404
    },
    {
        "name": "Rotter.net", "category": "Regional", "country": "il",
        "url_template": "https://rotter.net/forum/user/{}",
        "check_type": "status_code", "error_code": 404
    },
    {
        "name": "Xing", "category": "Regional", "country": "de",
        "url_template": "https://www.xing.com/profile/{}",
        "check_type": "status_code", "error_code": 404
    },
    {
        "name": "VKontakte", "category": "Regional", "country": "ru",
        "url_template": "https://vk.com/{}",
        "check_type": "status_code", "error_code": 404
    },
    {
        "name": "Habr", "category": "Regional", "country": "ru",
        "url_template": "https://habr.com/ru/users/{}/",
        "check_type": "status_code", "error_code": 404
    },
    {
        "name": "Bilibili", "category": "Regional", "country": "cn",
        "url_template": "https://space.bilibili.com/{}",
        "check_type": "status_code", "error_code": 404
    }
]