# Copyright 2021 Coredump Labs
# https://github.com/coredumplabs/thingsboard-micropython.git
#
# SPDX-License-Identifier: Apache-2.0

import sys
import socketpool
import wifi
import ssl
import time
import adafruit_requests as requests
import binascii
__version__ = "0.0.1"
#__repo__ = ""

TELEMETRY_URL = '%s://%s/%s/'

class NRDeviceHttpMQTTClient:

    DEBUG = False

    def __init__(self, host:str, device_id:str, ssl:bool=True, request_session:requests.Session=None, username:str=None, password:str=None):
        self._request_session = request_session
        self._host = host
        self._device_id = device_id
        self._telemetry = None
        self._ssl = ssl
        self._is_connected = False
        self.header_list = {}
        if username or password:
            _tmp = ('%s:%s'% (username, password))
            _tmp = binascii.b2a_base64(_tmp.encode('utf-8'))
            _tmp = _tmp[:len(_tmp)-1]
            _tmp = _tmp.decode('utf-8')
            _auth_str = ('Basic %s' % _tmp)
            self.header_list['Authorization'] = _auth_str
        if self._ssl:
            self._url_telemetry = (TELEMETRY_URL % ('https', host, device_id))
        else:
            self._url_telemetry = (TELEMETRY_URL % ('http', host, device_id))

    def is_connected(self):
        return self._is_connected

    def connect(self):
        if self._request_session == None:
            socket = socketpool.SocketPool(wifi.radio)
            if self._ssl:
                self._request_session = requests.Session(socket, ssl.create_default_context())
            else:
                self._request_session = requests.Session(socket)

        self._is_connected = False
        for x in range(5):
            response = self._request_session.get(self._url_telemetry, timeout=10, headers=self.header_list)
            if response.status_code == 200:
                self._log('response.status from %s: %d', self._host, response.status_code)
                self._is_connected = True
                break
            time.sleep(1)
        return self._is_connected


    def disconnect(self):
        if self._is_connected:
            self._log('Disconnecting from %s', self._host)
            #self._client.disconnect()
            self._is_connected = False

    def send_telemetry(self, telemetry=None, topic=None, qos=0, retain=False):
        if not self._is_connected:
            self.connect()
        if not self._is_connected:
            return 0
        if telemetry==None:
            telemetry = self._telemetry
        if telemetry==None:
            return 0
        # if isinstance(telemetry, dict):
        #     telemetry = [telemetry]
        if topic==None:
            topic = self._device_id
       
        #print(telemetry)
        full_url = ("%s?topic=%s&qos=%s&retain=%s" % (self._url_telemetry, topic, qos, retain))
        #print(full_url)
        self._request_session._free_sockets()
        response = self._request_session.post(full_url, json=telemetry, timeout=10, headers=self.header_list)
        self._request_session._free_sockets()
        #print(response.status_code)
        if response.status_code == 200:
            self._log('response.status from %s: %d', self._host, response.status_code)
            self._is_connected = True
        else:
            self._log('response.status from %s: %d', self._host, response.status_code)
            self._is_connected = False
        return response.status_code


    def _log(self, msg, *args):
        if self.DEBUG:
            if not args:
                print(msg)
            else:
                print(msg % args)
