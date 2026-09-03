from pythonforandroid.recipe import PyProjectRecipe

# Local recipe override for charset-normalizer, an unavoidable transitive
# dependency of Kivy itself (Kivy's own PyPI metadata hard-depends on
# 'requests', which depends on charset-normalizer -- not something we
# added or chose).
#
# Two real, confirmed build failures led here, in order:
#
# 1. A plain version pin in buildozer.spec's requirements string
#    (charset-normalizer==3.4.3) had NO effect: p4a only honors a pin for
#    packages with a real recipe. Fixed by making this a recipe at all
#    (PyProjectRecipe correctly does a pinned, per-package pip install).
#
# 2. Recipe-based install then worked (3.4.3 installed successfully) --
#    but p4a runs a SEPARATE, later dependency-completion pass (to catch
#    transitive needs like click/typing_extensions that an earlier
#    --no-deps bulk install skipped) that re-resolves charset-normalizer
#    from scratch, with no awareness the recipe already installed it.
#    That pass hit version 3.5.1's real, correctly-tagged Android wheel
#    (charset_normalizer-3.5.1-cp314-cp314-android_24_arm64_v8a.whl --
#    confirmed to genuinely exist and download fine) and rejected it
#    anyway: "not a supported wheel on this platform". That's an upstream
#    pip/packaging bug in very new PEP 738 Android wheel-tag validation,
#    not anything about this package or version specifically.
#
# Fix: pin to 2.1.1, a version that publishes exactly ONE wheel total (the
# universal py3-none-any one, zero platform-specific competitors) --
# confirmed via PyPI's own file listing. With nothing else to even
# consider, pip cannot hit the buggy tag-matching path at all, regardless
# of which of p4a's two separate resolution passes triggers the install.
class CharsetNormalizerRecipe(PyProjectRecipe):
    version = "2.1.1"
    depends = ["python3"]


recipe = CharsetNormalizerRecipe()
