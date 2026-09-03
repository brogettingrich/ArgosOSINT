from pythonforandroid.recipe import PyProjectRecipe

# Local recipe override, needed because buildozer.spec's inline version pin
# (charset-normalizer==3.4.3) turned out to have NO effect: p4a only
# respects a version pin for packages that have a real recipe (bundled or
# local) -- charset-normalizer has neither, so it falls into p4a's generic
# "install every non-recipe pip module in one bulk call, by bare name only"
# path, which silently drops the pin and always resolves whatever's newest
# (confirmed directly in a build log: "Recipe charset-normalizer: version
# '3.4.3' requested" followed immediately by "were not found as recipes,
# they will be installed with pip" -- the requested version never reaches
# the actual pip invocation for that path).
#
# charset-normalizer itself isn't a choice we made -- it's a hard,
# unconditional dependency of Kivy itself (see Kivy's own PyPI metadata:
# requires_dist includes 'requests', which pulls in charset-normalizer).
#
# This recipe exists purely to force the version through p4a's OTHER
# install path (PyProjectRecipe's own per-package dry-run + pinned pip
# install), which is what respects `version` correctly -- same reasoning
# as the numpy local recipe alongside this one, different mechanism.
class CharsetNormalizerRecipe(PyProjectRecipe):
    version = "3.4.3"
    depends = ["python3"]


recipe = CharsetNormalizerRecipe()
