import random
import time
import functools
import json

import requests
import tornado.httpclient
import tornado.ioloop

endpoints = [
    'http://localhost:8888/append',
    'http://localhost:8889/append',
    'http://localhost:8890/append',
    'http://localhost:8891/append']

def append(value):
    requests.post(random.choice(endpoints),
                  headers={'Content-Type': 'application/json'},
                  data=json.dumps({'value': value}))


for i in range(5):
    print("Sending", i)
    append(i)
    time.sleep(1)
"""

client = tornado.httpclient.AsyncHTTPClient()

@tornado.gen.coroutine
def append(value):
    request = tornado.httpclient.HTTPRequest(
        url = random.choice(endpoints),
        method = 'POST',
        headers = {'Content-Type': 'application/json'},
        body = json.dumps({'value': value})
    )
    resp = yield client.fetch(request, callback=lambda r: print(value, 'complete'))

ioloop = tornado.ioloop.IOLoop.current()
for i in range(8):
    print("Adding ", i)
    ioloop.add_callback(functools.partial(append, i))
ioloop.start()

"""
