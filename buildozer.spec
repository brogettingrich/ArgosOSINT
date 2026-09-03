[app]
title = ArgosOSINT
package.name = argososint
package.domain = org.argos
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js,json,db,txt,tflite,onnx
source.include_patterns = app/**,data/**,requirements.txt
version = 1.0

# Dependencies: pure Starlette + uvicorn (zero pydantic / zero C-extensions)
# numpy, opencv, tflite-runtime: added for "Find With Face" (app/core/face_match.py).
# Both opencv and tflite-runtime compile from source via NDK/CMake on this
# build -- expect a much longer build time than before, and treat the first
# attempt as a real debugging pass, not a guaranteed clean build (verified
# recipes exist for all three, but tflite-runtime's is a niche one pinned to
# an old TensorFlow 2.8.0, not a mainstream/heavily-traveled path).
# charset-normalizer: bare name here, NOT ==3.4.3 -- that inline pin looked
# right but turned out to have zero effect (see
# p4a_local_recipes/charset-normalizer/__init__.py for why, and for where
# the actual 3.4.3 pin now lives). Kivy itself hard-depends on it
# (transitively, via Kivy's own 'requests' dependency) -- not something we
# added or can remove.
requirements = python3,kivy,pyjnius,android,starlette,uvicorn,httpx,python-multipart,dnspython,phonenumbers,certifi,anyio,sniffio,h11,idna,charset-normalizer,numpy,opencv,tflite-runtime

# Local recipe overrides -- see each folder's __init__.py for the specific
# real build failure it fixes and how that was confirmed, not guessed:
#   numpy/               unique.cpp missing #include <unordered_map>
#   charset-normalizer/  version pin ineffective without a real recipe
p4a.local_recipes = p4a_local_recipes

# Android specific
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK
android.api = 33
# 24 (not 21) -- numpy's p4a recipe hard-requires ndk api/minapi >= 24 (real
# error from the first Android build attempt after adding numpy/opencv/
# tflite-runtime: "In order to build 'numpy', you must set minimum ndk api
# (minapi) to 24."). API 24 = Android 7.0 (2016) -- effectively no real
# device in use today is below this, so no practical compatibility loss.
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a
android.allow_backup = True
orientation = portrait
android.orientation = portrait
android.wakelock = False
android.accept_sdk_license = True

# Cleartext traffic for local backend server
# (android.manifest.uses_cleartext_traffic is not a real buildozer option and
# was silently ignored -- verified against buildozer's source. The actual
# supported hook injects a file's contents into the <application> tag.)
android.extra_manifest_application_arguments = android_manifest_extra.xml

[buildozer]
log_level = 2
warn_on_root = 1
