#
# Only used for development!
#

# Start a server
#docker run -v /dev/hidraw7:/dev/hidraw7 -p 6153:6153 --privileged --detached ghcr.io/patrick762/streamdeckapi:main

# Run python tests
python test.py
