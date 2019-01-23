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


messages = collections.deque()


class MessageHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    def post(self):
        payload = json.loads(self.request.body)
        messages.append(payload)
        self.write("OK")


if __name__ == '__main__':
    tornado.options.parse_command_line()
    application = tornado.web.Application([
        (r"/message", MessageHandler)], debug=True)

    server = tornado.httpserver.HTTPServer(application)
    server.bind(options.port)
    server.start()
    tornado.ioloop.IOLoop.current().start()
