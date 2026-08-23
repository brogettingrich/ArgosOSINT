from typing import List, Dict, Any

SITES_CATALOG: List[Dict[str, Any]] = [
    # 1. PRIMARY SOCIAL & MESSAGING
    {
        "name": "Instagram", "category": "Social",
        "url_template": "https://www.instagram.com/{}/",
        "check_type": "special_api", "special_handler": "instagram"
    },
    {
        "name": "Facebook", "category": "Social",
        "url_template": "https://www.facebook.com/{}",
        "check_type": "special_api", "special_handler": "facebook"
    },
    {
        "name": "TikTok", "category": "Social",
        "url_template": "https://www.tiktok.com/@{}",
        "check_type": "special_api", "special_handler": "tiktok"
    },
    {
        "name": "Twitter / X", "category": "Social",
        "url_template": "https://x.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Pinterest", "category": "Social",
        "url_template": "https://www.pinterest.com/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Telegram", "category": "Social",
        "url_template": "https://t.me/{}",
        "check_type": "special_api", "special_handler": "telegram"
    },
    {
        "name": "Snapchat", "category": "Social",
        "url_template": "https://www.snapchat.com/add/{}",
        "check_type": "special_api", "special_handler": "snapchat"
    },
    {
        "name": "Tumblr", "category": "Social",
        "url_template": "https://www.tumblr.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "VK", "category": "Social",
        "url_template": "https://vk.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Vero", "category": "Social",
        "url_template": "https://vero.co/{}",
        "check_type": "special_api", "special_handler": "vero"
    },
    {
        "name": "Reddit", "category": "Social",
        "url_template": "https://old.reddit.com/user/{}",
        "profile_url": "https://www.reddit.com/user/{}",
        "check_type": "special_api", "special_handler": "reddit"
    },
    {
        "name": "Quora", "category": "Social",
        "url_template": "https://www.quora.com/profile/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Mastodon Social", "category": "Social",
        "url_template": "https://mastodon.social/@{}",
        "check_type": "status_code",
        "error_code": 404
    },

    # 2. DEVELOPER & CODING
    {
        "name": "GitHub", "category": "Developer",
        "url_template": "https://github.com/{}",
        "check_type": "special_api", "special_handler": "github"
    },
    {
        "name": "GitLab", "category": "Developer",
        "url_template": "https://gitlab.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "HackerNews", "category": "Developer",
        "url_template": "https://hacker-news.firebaseio.com/v0/user/{}.json",
        "profile_url": "https://news.ycombinator.com/user?id={}",
        "check_type": "special_api", "special_handler": "hackernews"
    },
    {
        "name": "NPM", "category": "Developer",
        "url_template": "https://www.npmjs.com/~{}",
        "check_type": "status_code",
        "error_code": 404
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
    {
        "name": "DockerHub", "category": "Developer",
        "url_template": "https://hub.docker.com/u/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "HuggingFace", "category": "Developer",
        "url_template": "https://huggingface.co/{}",
        "check_type": "status_code",
        "error_code": 404
    },

    # 3. GAMING & STREAMING
    {
        "name": "Steam", "category": "Gaming",
        "url_template": "https://steamcommunity.com/id/{}",
        "check_type": "special_api", "special_handler": "steam"
    },
    {
        "name": "Twitch", "category": "Gaming",
        "url_template": "https://www.twitch.tv/{}",
        "check_type": "special_api", "special_handler": "twitch"
    },
    {
        "name": "Roblox", "category": "Gaming",
        "url_template": "https://www.roblox.com/user.aspx?username={}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Chess.com", "category": "Gaming",
        "url_template": "https://www.chess.com/member/{}",
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
        "url_template": "https://www.speedrun.com/user/{}",
        "check_type": "status_code",
        "error_code": 404
    },

    # 4. MEDIA, MUSIC & CREATIVE
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
        "url_template": "https://{}.bandcamp.com",
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
        "name": "Flickr", "category": "Media",
        "url_template": "https://www.flickr.com/photos/{}/",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Unsplash", "category": "Media",
        "url_template": "https://unsplash.com/@{}",
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
        "name": "ArtStation", "category": "Media",
        "url_template": "https://www.artstation.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Wattpad", "category": "Media",
        "url_template": "https://www.wattpad.com/user/{}",
        "check_type": "special_api", "special_handler": "wattpad"
    },
    {
        "name": "Substack", "category": "Media",
        "url_template": "https://{}.substack.com",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Medium", "category": "Media",
        "url_template": "https://medium.com/@{}",
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
        "name": "Goodreads", "category": "Media",
        "url_template": "https://www.goodreads.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Archive.org", "category": "Media",
        "url_template": "https://archive.org/details/@{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Linktree", "category": "Media",
        "url_template": "https://linktr.ee/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "About.me", "category": "Media",
        "url_template": "https://about.me/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "BuyMeACoffee", "category": "Media",
        "url_template": "https://www.buymeacoffee.com/{}",
        "check_type": "status_code",
        "error_code": 404
    },
    {
        "name": "Patreon", "category": "Media",
        "url_template": "https://www.patreon.com/{}",
        "check_type": "status_code",
        "error_code": 404
    }
]