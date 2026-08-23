[app]
title           = ArgosOSINT
package.name    = argososint
package.domain  = org.argos
source.dir      = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js,json,db,txt
source.include_patterns = app/**,data/**,requirements.txt
version         = 1.0

requirements    = python3,kivy,kivymd,pyjnius,android,\
                  fastapi,uvicorn,httpx,pydantic,\
                  python-multipart,dnspython,phonenumbers,\
                  certifi,anyio,starlette,sniffio,h11,\
                  idna,charset-normalizer

# Android
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api         = 34
android.minapi      = 26
android.ndk         = 25b
android.ndk_api     = 21
android.arch        = arm64-v8a
android.allow_backup = False
android.orientation  = portrait
android.wakelock     = False

# Allow cleartext to localhost (needed for 127.0.0.1 WebView)
android.manifest.uses_cleartext_traffic = True

# Splash / icon (uses default Kivy if not present)
# presplash.filename = %(source.dir)s/app/static/splash.png
# icon.filename      = %(source.dir)s/app/static/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
