import struct
from setuptools import Extension, find_packages, setup

from Cython.Build import cythonize

if struct.calcsize("P") * 8 != 64:
    raise RuntimeError("AltAPI Cython extension must be built with 64-bit Python.")


extensions = [
    Extension(
        "altapi.router",
        ["src/altapi/router.pyx"],
    ),
]


setup(
    name="altapi",
    version="1.2.1",
    author="amogus-gggy",
    description="A simple and fast ASGI microframework for Python with WebSocket support.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/amogus-gggy/AltAPI",
    project_urls={
        "Homepage": "https://github.com/amogus-gggy/AltAPI",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": 3,
            "boundscheck": False,
            "wraparound": False,
        },
    ),
    python_requires=">=3.10",
    install_requires=[
        "uvicorn[standard]>=0.30.0",
        "anyio>=4.0.0",
        "jinja2>=3.0.0",
        "ujson"
    ],
)