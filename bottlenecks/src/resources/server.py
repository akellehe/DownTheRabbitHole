import logging
import time
import random

import tornado.ioloop
import tornado.httpserver
import tornado.httpclient
import tornado.options
import tornado.web
import redis

from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)

logging.basicConfig(format='%(levelname)s - %(filename)s:L%(lineno)d pid=%(process)d - %(message)s')
logger = logging.getLogger('agent')
redis_cli = redis.StrictRedis()
big_random = "".join([random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                      for i in range(1024 * 1024)])
medium_random = "".join([random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                         for i in range(1024)])

TORNADO_SETTINGS = {'debug': True, 'autorestart': True}


class API(tornado.web.RequestHandler):
    pass


class BigNetwork(API):

    async def get(self):
        i = 0
        page = 1024 * 1024 # 1MB
        while i < len(big_random):
            self.write(big_random[i*page:(i+1)*page])
            i += page
            self.flush()
        self.finish()


class MediumNetwork(API):

    async def get(self):
        self.write(medium_random)  # 1KB
        self.finish()


class Lock(API):

    def get(self):
        with redis_cli.lock('block'):
            time.sleep(0.5)  # We want this to block. That is the point.
        self.write('done')
        self.finish()


def get_app():
    return tornado.web.Application([
        (r"/resource/network/big", BigNetwork),
        (r"/resource/network/medium", MediumNetwork),
        (r"/resource/lock", Lock),
    ], **TORNADO_SETTINGS)

    
def main():
    loop = tornado.ioloop.IOLoop.current()
    tornado.options.parse_command_line()
    server = tornado.httpserver.HTTPServer(get_app())
    server.listen(options.port)
    server.start()
    logger.info("Server listening on port %s", options.port)
    loop.start()


if __name__ == "__main__":
    main()
