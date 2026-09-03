from pythonforandroid.recipe import PyProjectRecipe

# The actual root cause of the charset-normalizer saga, found by reading
# python-for-android's own build.py (process_python_modules /
# run_pymodules_install), not guessed:
#
# requests is a hard, unconditional dependency of Kivy itself (see Kivy's
# own PyPI requires_dist -- 'requests' with no extras marker). It has no
# recipe, so it lands in p4a's generic "install every leftover pip module
# together" bucket. That bucket gets resolved as ONE JOINT, UNCONSTRAINED
# pip solve (process_python_modules -> `pip install *modules --dry-run
# --report`), which naturally discovers requests' real transitive need for
# charset-normalizer and resolves it to whatever's newest (3.5.1) --
# completely independent of the separate charset-normalizer recipe sitting
# right next to this one, which only controls ITS OWN install.
#
# p4a does try to skip re-adding anything that already has a recipe
# (`if mname.lower().replace("-", "_") in _requirement_names: continue`),
# but `_requirement_names` is built from `Requirement(module).name`, which
# preserves "charset-normalizer" (hyphenated) -- so the comparison against
# the underscored "charset_normalizer" never matches. That's a genuine bug
# in p4a itself, not something fixable from buildozer.spec or a recipe's
# own version pin.
#
# The actual fix: make requests a recipe too, so it's removed from the
# pip-only bucket BEFORE that joint resolve ever runs -- charset-normalizer
# then never gets rediscovered as a transitive need in the first place,
# regardless of the filter bug. 2.31.0 is a long-established requests
# release, pure Python (only a py3-none-any wheel + sdist exist for it --
# confirmed on PyPI, same "nothing else for a buggy tag-matcher to
# mis-select" property the charset-normalizer recipe relies on).
class RequestsRecipe(PyProjectRecipe):
    version = "2.31.0"
    depends = ["python3", "charset-normalizer"]


recipe = RequestsRecipe()
