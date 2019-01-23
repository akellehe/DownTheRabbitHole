import random
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

client = tornado.httpclient.AsyncHTTPClient()

def handle_response(value, r):
    if r.code == 200:
        print(value, 'complete')
"""
@tornado.gen.coroutine
def append(value):
    while True:
        try:
            request = tornado.httpclient.HTTPRequest(
                url = random.choice(endpoints),
                method = 'POST',
                headers = {'Content-Type': 'application/json'},
                body = json.dumps({'value': value})
            )
            responder = functools.partial(handle_response, value)
            resp = yield client.fetch(request, callback=responder)
            if resp.code == 200: break
        except Exception as e:
            pass

ioloop = tornado.ioloop.IOLoop.current()
for i in range(10):
    print("Adding ", i)
    ioloop.add_callback(functools.partial(append, i))
try:
    ioloop.start()
except KeyboardInterrupt as e:
    pass





















"""
def append(value):
    requests.post(random.choice(endpoints),
                  headers={'Content-Type': 'application/json'},
                  data=json.dumps({'value': value}))


for i in range(5):
    print("Sending", i)
    append(i)

