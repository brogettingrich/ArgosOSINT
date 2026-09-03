from pythonforandroid.recipe import Recipe, MesonRecipe
from os.path import join
import shutil

NUMPY_NDK_MESSAGE = (
    "In order to build numpy, you must set minimum ndk api (minapi) to `24`.\n"
)


class NumpyRecipe(MesonRecipe):
    # Local override of p4a's bundled numpy recipe (via buildozer.spec's
    # p4a.local_recipes) -- identical except for `patches` below. Confirmed
    # real build failure: numpy/_core/src/multiarray/unique.cpp is missing
    # `#include <unordered_map>`, a genuine upstream numpy bug (same error
    # independently confirmed on macOS's Clang/libc++ in a Homebrew report --
    # https://github.com/orgs/Homebrew/discussions/6386 -- Android NDK hits
    # it for the same reason: both use strict libc++, unlike libstdc++ which
    # transitively pulls the header in and hides the bug). Upstream fix:
    # https://github.com/numpy/numpy/pull/29662 (one line, same fix applied
    # here as a patch since the p4a recipe pins an exact tag predating it).
    version = "v2.3.0"
    url = "git+https://github.com/numpy/numpy"
    extra_build_args = ["-Csetup-args=-Dblas=none", "-Csetup-args=-Dlapack=none"]
    need_stl_shared = True
    min_ndk_api_support = 24
    patches = ["fix_missing_unordered_map_include.patch"]

    def get_include(self, arch):
        return join(
            self.ctx.get_python_install_dir(arch.arch), "numpy/_core/include",
        )

    def get_recipe_meson_options(self, arch):
        options = super().get_recipe_meson_options(arch)
        options["properties"]["longdouble_format"] = (
            "IEEE_DOUBLE_LE" if arch.arch in ["armeabi-v7a", "x86"] else "IEEE_QUAD_LE"
        )
        return options

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)

        # _PYTHON_HOST_PLATFORM declares that we're cross-compiling
        # and avoids issues when building on macOS for Android targets.
        env["_PYTHON_HOST_PLATFORM"] = arch.command_prefix

        # NPY_DISABLE_SVML=1 allows numpy to build for non-AVX512 CPUs
        # See: https://github.com/numpy/numpy/issues/21196
        env["NPY_DISABLE_SVML"] = "1"
        env["TARGET_PYTHON_EXE"] = join(
            Recipe.get_recipe("python3", self.ctx).get_build_dir(arch.arch),
            "android-build",
            "python",
        )
        return env

    def get_hostrecipe_env(self, arch=None):
        env = super().get_hostrecipe_env(arch=arch)
        env["RANLIB"] = shutil.which("ranlib")
        return env


recipe = NumpyRecipe()
