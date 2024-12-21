FROM python:3.9.18-bookworm

# Get dependencies
RUN apt update
RUN apt install -y libudev-dev libusb-1.0-0-dev libhidapi-libusb0 libjpeg-dev zlib1g-dev libopenjp2-7 libtiff5-dev libgtk-3-dev
RUN apt clean
RUN rm -rf /var/lib/apt/lists/*

COPY . /streamdeckapi
WORKDIR /streamdeckapi

# Install the pip package
RUN pip install --no-cache-dir .

EXPOSE 6153

# Run the server
CMD [ "streamdeckapi-server" ]
