[app]
title = ArgosOSINT
package.name = argososint
package.domain = org.argos
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js,json,db,txt
source.include_patterns = app/**,data/**,requirements.txt
version = 1.0

# Dependencies: using fastapi 0.95.2 with pure Python pydantic v1 (no pydantic_core rust binary needed on ARM64)
requirements = python3,kivy,pyjnius,android,fastapi==0.95.2,pydantic<2.0.0,uvicorn,httpx,python-multipart,dnspython,phonenumbers,certifi,anyio,starlette,sniffio,h11,idna,charset-normalizer

# Android specific
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a
android.allow_backup = True
orientation = portrait
android.orientation = portrait
android.wakelock = False
android.accept_sdk_license = True

# Cleartext traffic for local backend server
android.manifest.uses_cleartext_traffic = True

[buildozer]
log_level = 2
warn_on_root = 1
