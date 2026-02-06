# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from setuptools import setup, find_packages


setup_args = dict(
    name="picosvgx",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "console_scripts": [
            "picosvgx=picosvgx.picosvgx:main",
        ],
    },
    setup_requires=["setuptools"],
    install_requires=[
        "absl-py>=0.9.0",
        "lxml>=4.0",
        "skia-pathops>=0.6.0",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-clarity",
            "black==23.3.0",
            "pytype==2020.11.23; python_version < '3.9'",
        ],
    },
    # this is so we can use the built-in dataclasses module
    python_requires=">=3.8",
    # this is for type checker to use our inline type hints:
    # https://www.python.org/dev/peps/pep-0561/#id18
    package_data={"picosvgx": ["py.typed"]},
    # metadata to display on PyPI
    author="Ximing Xing",
    author_email="ximingxing@gmail.com",
    description=(
        "An extended fork of Google's picosvg with better real-world SVG compatibility"
    ),
)


if __name__ == "__main__":
    setup(**setup_args)
