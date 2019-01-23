import json
import threading
import os
import operator
import logging

import tornado.httpserver
import tornado.httpclient
import tornado.ioloop
import tornado.web
import tornado.netutil
import tornado.process
import requests
import collections
from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)

logging.getLogger().setLevel(logging.DEBUG)
my_list = []
ports = [8888, 8889, 8890, 8891]
clock = 0
threads = collections.deque()


def increment_clock():
    global clock
    clock += 1


def process_event(request):
    payload = json.loads(request.body)
    if 'clock' not in payload:
        payload['clock'] = clock
    my_list.append(payload)
    return payload.get('value')


def send_message(message, port):
    url = 'http://0.0.0.0:{}/message'
    threads.append(
        threading.Thread(
            target=lambda: requests.post(
                url.format(port),
                headers={
                    'Content-Type': 'application/json'},
                data=json.dumps(message), timeout=1)))



def fanout(message):
    global threads
    for port in ports:
        if port == options.port:
            continue
        send_message(message, port)
    for thread in threads:
        thread.start()


class AppendHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(json.dumps(
            [e for e in sorted(my_list, key=operator.itemgetter('clock'))])
        )

    def post(self):
        while threads:
            thread = threads.popleft()
            thread.join()

        increment_clock()
        value = process_event(self.request)
        fanout({'value': value, 'clock': clock})

        self.write("200 OK")


class MessageHandler(tornado.web.RequestHandler):

    def post(self):
        # 1) Set the counter to the greater of the incoming counter and this process' plus 1
        global clock
        while threads:
            thread = threads.popleft()
            thread.join()
        
        process_event(self.request)

        message = json.loads(self.request.body)
        clock = max(int(message.get('clock')), clock) + 1

        self.write(json.dumps({"status": "200 OK"}))


if __name__ == '__main__':
    tornado.options.parse_command_line()
    application = tornado.web.Application([
        (r"/append", AppendHandler),
        (r"/message", MessageHandler)], debug=True)

    server = tornado.httpserver.HTTPServer(application)
    server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()
