from setuptools import setup, find_packages
import codecs
import os

from streamdeckapi.const import VERSION

here = os.path.abspath(os.path.dirname(__file__))

with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

DESCRIPTION = "Stream Deck API Library"

# Setting up
setup(
    name="streamdeckapi",
    version=VERSION,
    author="Patrick762",
    author_email="<pip-stream-deck-api@hosting-rt.de>",
    description=DESCRIPTION,
    long_description_content_type="text/markdown",
    long_description=long_description,
    url="https://github.com/Patrick762/streamdeckapi",
    packages=find_packages(),
    install_requires=[
        "requests==2.28.2",
        "websockets==11.0.2",
        "aiohttp==3.8.4",
        "human-readable-ids==0.1.3",
        "streamdeck==0.9.3",
        "pillow>=9.4.0,<10.0.0",
    ],
    keywords=[],
    entry_points={
        "console_scripts": ["streamdeckapi-server = streamdeckapi.server:start"]
    },
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Operating System :: Unix",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ],
)
