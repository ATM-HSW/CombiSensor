# Copyright 2021 Coredump Labs
# https://github.com/coredumplabs/thingsboard-micropython.git
#
# SPDX-License-Identifier: Apache-2.0

import json
import sys
import socketpool
import wifi
import ssl
import adafruit_requests as requests

__version__ = "0.1.1"
__repo__ = "https://github.com/ATM-HSW/CircuitPython_ThingsBoard.git"

TELEMETRY_URL = '%s://%s/api/v1/%s/telemetry'
ATTRIBUTES_URL = '%s://%s/api/v1/%s/attributes'
#TELEMETRY_URL_TLS = 'https://%s/api/v1/%s/telemetry'

#RPC_RESPONSE_TOPIC = 'v1/devices/me/rpc/response/'
#RPC_REQUEST_TOPIC = 'v1/devices/me/rpc/request/'
#ATTRIBUTES_TOPIC = 'v1/devices/me/attributes'
#ATTRIBUTES_TOPIC_REQUEST = 'v1/devices/me/attributes/request/'
#ATTRIBUTES_TOPIC_RESPONSE = 'v1/devices/me/attributes/response/'
#CLAIMING_TOPIC = 'v1/devices/me/claim'
#PROVISION_TOPIC_REQUEST = '/provision/request'
#PROVISION_TOPIC_RESPONSE = '/provision/response'


class TBDeviceHttpClient:

    DEBUG = False

    def __init__(self, host, device_id, ssl=True, request_session=None):
        #self._socket = socket_pool
        self._request_session = request_session
        self._host = host
        self._device_id = device_id
        self._ssl = ssl
        self._is_connected = False
        self._telemetry = None
        self._attributes_client = None
        self._attributes_shared = None
        if self._ssl:
            self._url_telemetry = (TELEMETRY_URL % ('https', host, device_id))
            self._url_attributes = (ATTRIBUTES_URL % ('https', host, device_id))
        else:
            self._url_telemetry = (TELEMETRY_URL % ('http', host, device_id))
            self._url_attributes = (ATTRIBUTES_URL % ('http', host, device_id))
        #self._attr_request_dict = {}
        #self._device_on_server_side_rpc_response = None
        #self._device_max_sub_id = 0
        #self._device_client_rpc_number = 0
        #self._device_sub_dict = {}
        #self._device_client_rpc_dict = {}
        #self._attr_request_number = 0
        #self._client.set_callback(self._on_message)

    def is_connected(self):
        return self._is_connected

    def connect(self, write_connect_key=True):
        if self._is_connected:
            return self._is_connected

        if self._request_session == None:
            socket = socketpool.SocketPool(wifi.radio)
            if self._ssl:
                self._request_session = requests.Session(socket, ssl.create_default_context())
            else:
                self._request_session = requests.Session(socket)

        if write_connect_key:
            data = json.dumps({ "connect": 1})
            #print(self._url_telemetry)
            response = self._request_session.post(self._url_telemetry, data=data, timeout=10)
            #print(response.status_code)
            if response.status_code == 200:
                self._log('response.status from ThingsBoard %d', response.status_code)
                self._is_connected = True
            return self._is_connected
        else:
            self._is_connected = True
            return self._is_connected

    #def reconnect(self):
    #    self._log('Reconnecting to ThingsBoard')
    #    return self._client.reconnect()

    def disconnect(self):
        if self._is_connected:
            self._log('Disconnecting from ThingsBoard')
            #self._client.disconnect()
            self._is_connected = False

    #def claim(self, secret_key, duration=30000):
    #    claiming_request = {
    #        'secretKey': secret_key,
    #        'durationMs': duration
    #    }
    #    self._client.publish(CLAIMING_TOPIC, json.dumps(
    #        claiming_request), qos=self._qos)
    #
    #def send_rpc_reply(self, req_id, resp, qos=0):
    #    validate_qos(qos)
    #    self._client.publish(RPC_RESPONSE_TOPIC + req_id, resp, qos=qos)
    #
    #def send_rpc_call(self, method, params, callback):
    #    self._device_client_rpc_number += 1
    #    self._device_client_rpc_dict.update(
    #        {self._device_client_rpc_number: callback})
    #    rpc_request_id = self._device_client_rpc_number
    #    payload = {'method': method, 'params': params}
    #    self._client.publish(RPC_REQUEST_TOPIC + str(rpc_request_id),
    #                         json.dumps(payload),
    #                         qos=self._qos)
    #
    #def set_server_side_rpc_request_handler(self, handler):
    #    # handler signature is callback(req_id, method, params)
    #    self._device_on_server_side_rpc_response = handler

    def send_telemetry(self, telemetry=None):
        if not self._is_connected:
            self.connect()
        if not self._is_connected:
            return 0
        if telemetry==None:
            telemetry = self._telemetry
        if telemetry==None:
            return 0
        if isinstance(telemetry, dict):
            telemetry = [telemetry]

        data = json.dumps(telemetry)
        #print(self._url_telemetry)
        #print(data)
        self._request_session._free_sockets()
        response = self._request_session.post(self._url_telemetry, data=data, timeout=10)
        self._request_session._free_sockets()
        #print(response.status_code)
        if response.status_code == 200:
            self._log('response.status from ThingsBoard %d', response.status_code)
            self._is_connected = True
        return response.status_code

    def send_attributes(self, attributes):
        if not self._is_connected:
            self.connect()
        if not self._is_connected:
            return 0
        if attributes==None:
            attributes = self._attributes_client
        if attributes==None:
            return 0

        data = json.dumps(attributes)
        #print(self._url_attributes)
        #print(data)
        response = self._request_session.post(self._url_attributes, data=data, timeout=10)
        #print(response.status_code)
        if response.status_code == 200:
            self._log('response.status from ThingsBoard %d', response.status_code)
            self._is_connected = True
        return response.status_code

    def request_attributes(self, client_keys=None, shared_keys=None):
        response = self._request_session.get(self._url_attributes, timeout=10)
        if response.status_code == 200:
            self._log('response.status from ThingsBoard %d', response.status_code)
            self._is_connected = True
            #print(response.json())
            if "client" in response.json():
                self._attributes_client = response.json()["client"]
            if "shared" in response.json():
                self._attributes_shared = response.json()["shared"]
            #print(self._attributes_client)
            #print(self._attributes_shared)
        return response.status_code

    def get_shared_attribute(self, key=None):
        if key==None:
            return self._attributes_client
        if self._attributes_client==None:
            return None
        if key in self._attributes_client:
            return self._attributes_client[key]
        else:
            return None

    def get_client_attribute(self, key=None):
        if key==None:
            return self._attributes_shared
        if self._attributes_shared==None:
            return None
        if key in self._attributes_shared:
            return self._attributes_client[key]
        else:
            return None

    def _log(self, msg, *args):
        if self.DEBUG:
            stream = sys.stderr.write('%s:%s:' % (self.__name__))
            if not args:
                print(msg, file=stream)
            else:
                print(msg % args, file=stream)
