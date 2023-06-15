"""Unittests for API client."""

import unittest
import streamdeckapi


class TestApi(unittest.TestCase):
    """Api Test Case."""

    def test_constructor(self):
        """Constructor test."""
        host = "host.local"

        # Test valid types
        api = streamdeckapi.StreamDeckApi(host)
        self.assertEqual(api.host, host)

        streamdeckapi.StreamDeckApi(host, on_button_press=None)
        streamdeckapi.StreamDeckApi(host, on_button_release=None)
        streamdeckapi.StreamDeckApi(host, on_status_update=None)
        streamdeckapi.StreamDeckApi(host, on_ws_connect=None)
        streamdeckapi.StreamDeckApi(host, on_ws_message=None)

        # Test some invalid types
        for i_type in ["string", 2345, [321, 6457], {"key": "value"}]:
            with self.assertRaises(TypeError):
                _ = streamdeckapi.StreamDeckApi(host, on_button_press=i_type)
            with self.assertRaises(TypeError):
                _ = streamdeckapi.StreamDeckApi(host, on_button_release=i_type)
            with self.assertRaises(TypeError):
                _ = streamdeckapi.StreamDeckApi(host, on_status_update=i_type)
            with self.assertRaises(TypeError):
                _ = streamdeckapi.StreamDeckApi(host, on_ws_connect=i_type)
            with self.assertRaises(TypeError):
                _ = streamdeckapi.StreamDeckApi(host, on_ws_message=i_type)
