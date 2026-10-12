"""
Utility script run during Docker image build to compile all Python modules in app/
into native C-extension shared objects (.so) using Cython, then deletes the original
.py source files. This ensures ZERO proprietary Python source code exists in the image.
"""
import os
import sys
from setuptools import setup
from setuptools.extension import Extension
from Cython.Build import cythonize

def find_py_modules(root_dir="app"):
    modules = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith(".py") and not f.startswith("__init__"):
                full_path = os.path.join(dirpath, f)
                # module path
                mod_name = full_path.replace(os.sep, ".").rstrip(".py")
                modules.append(Extension(mod_name, [full_path]))
    return modules

if __name__ == "__main__":
    ext_modules = find_py_modules("app")
    print(f"Found {len(ext_modules)} modules to compile into binary .so files...")
    setup(
        ext_modules=cythonize(
            ext_modules,
            compiler_directives={"language_level": "3", "always_allow_keywords": True},
            quiet=True,
        ),
        script_args=["build_ext", "--inplace"],
    )
    print("Compilation complete. Removing source .py and temporary .c files...")
    # Clean up .py (except __init__.py) and .c files in app/
    removed_count = 0
    for dirpath, _, filenames in os.walk("app"):
        for f in filenames:
            if (f.endswith(".py") and not f.startswith("__init__")) or f.endswith(".c"):
                os.remove(os.path.join(dirpath, f))
                removed_count += 1
    print(f"Successfully deleted {removed_count} source/intermediate files. Protected binaries (.so) preserved.")
