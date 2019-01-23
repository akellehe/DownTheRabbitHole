import logging
import time
import tempfile
import json
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
redis_cli = redis.StrictRedis('192.168.50.5', 6379)
http_client = tornado.httpclient.AsyncHTTPClient()

TORNADO_SETTINGS = {'debug': True, 'autorestart': True}


def get_float(key, default=1.):
    return float(redis_cli.get(key) or default) or default


class API(tornado.web.RequestHandler):

    def respond(self, start):
        with redis_cli.lock('statlock', timeout=0.5):
            self.write(json.dumps({
                't_ms': time.time() * 1000.,
                'duration': time.time() - start,
                'server_requests': get_float('server_requests', default=0),
                'client_requests': {
                    'sent': get_float('client_requests', default=0),
                    'successful': get_float('client_requests_succeeded', default=0),
                    'failed': get_float('client_requests_failed', default=0),
                },
                'cpu': {
                    'user': get_float('user_cpu', default=0),
                    'system': get_float('system_cpu', default=0),
                    'nice': get_float('nice_cpu', default=0),

                },
                'soft_interrupts': get_float('soft_interrupts', default=0.),
                'hard_interrupts': get_float('hard_interrupts', default=0.),
                'context_switches': get_float('context_switches', default=0.),
                'io_wait': get_float('io_wait', default=0.),
            }, indent=2, sort_keys=True))

        self.set_header('Content-Type', 'application/json')
        self.finish()

    def prepare(self):
        redis_cli.incr('server_requests')

    def get(self):
        start = time.time()
        self.respond(start)


class CPUBound(API):

    async def get(self):
        start = time.time()
        total = 0
        for i in range(100000):
            total = total * random.random()
            total = total / random.random()
        self.respond(start)


class FileIOBound(API):

    async def get(self):
        try:
            start = time.time()
            f = tempfile.NamedTemporaryFile()
            for i in range(10000):
                f.write(str(i).encode('utf-8'))
                f.flush()
        finally:
            f.close()
        self.respond(start)


class NetworkIOBound(API):

    async def get(self):
        start = time.time()
        response = await http_client.fetch('http://resources.io/resource/network/big')
        self.respond(start)


class LockBound(API):

    async def get(self):
        start = time.time()
        response = await http_client.fetch('http://resources.io/resource/lock')
        self.respond(start)


def get_app():
    return tornado.web.Application([
        (r"/bounded/cpu", CPUBound),
        (r"/bounded/file_io", FileIOBound),
        (r"/bounded/network_io", NetworkIOBound),
        (r"/bounded/lock", LockBound),
    ], **TORNADO_SETTINGS)

    
def main():
    loop = tornado.ioloop.IOLoop.current()
    tornado.options.parse_command_line()
    server = tornado.httpserver.HTTPServer(get_app())
    server.listen(options.port)
    server.start(num_processes=2)
    logger.info("Server listening on port %s", options.port)
    loop.start()


if __name__ == "__main__":
    main()
