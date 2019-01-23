import json
import time
import threading
import os
import operator
import logging

import tornado.httpserver
import tornado.httpclient
import tornado.ioloop
import tornado.web
import tornado.netutil
import tornado.gen
import tornado.process
import requests
import collections
from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)

logging.getLogger().setLevel(logging.DEBUG)
my_list = []
ports = [8888, 8889, 8890, 8891]
vector_clock = {8888:0, 8889:0, 8890:0, 8891:0}

threads = collections.deque()

def frozen(clock):
    return {k: int(v) for k, v in clock.items()}


def increment_clock():
    global vector_clock
    vector_clock[options.port] += 1


def send_message_sync(message, port):
    """
    Synchronously sends a message to a process listening on 0.0.0.0:[port]. If anything
    but 200 comes back we're probably still in the process of handling events on that node.
    In that case it's API will return 503 (Service Unavailable) and we'll try again.

    :param message: A dict of the form
        ..code-block: json
            {
                "sender": [port],
                "vector_clock": <dict<port>, <timestamp>>,
                "value": <int>
            }
    :param port: The port to which the message should be sent.
    :return: Nothing.
    """
    url = 'http://0.0.0.0:{}/message'
    while True:
        try:
            resp = requests.post(url.format(port),
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(message), timeout=1)
            if resp.status_code == 200: break
        except Exception as e:
            print(e)
            time.sleep(0.1)
            continue


def fanout_sync(message):
    """
    Synchronously issues requests to all nodes in the list of ports above. Sorry, no service discovery.

    :param message: A dict of the form
        ..code-block: json
            {
                "sender": [port],
                "vector_clock": <dict<port>, <timestamp>>,
                "value": <int>
            }
    """
    for port in ports:
        if port == options.port:
            continue
        send_message_sync(message, port)


def process_event(request):
    """
    This method incorporates an `append` event into the list hosted in the state of this API. I know, we're handling
    state in an API. Just don't tell the 12factor.net guys.

    A novel thing about this method is that it freeze the current logical time to the event. This ensures all
    processes have a snapshot of the most accurate time we have available for this process, so it can be ordered
    consistently across all nodes.

    :param request: tornado.httpclient.HTTPRequest
    :return: The value of the event parsed out. It will be an integer.
    """
    global vector_clock
    event = json.loads(request.body)
    if 'vector_clock' in event:
        raise Exception("Vector clock passed in client event")
    my_list.append({'value': event.get('value'), 'vector_clock': frozen(vector_clock)})
    return event.get('value')


def update_times(sender, last_knowns):
    """
    Incorporates the last known times for all processes based on the value in the latest message. The rule is

        1) For every time listed in the incoming vector, set the time in the local vector equal to the maximum of the two.
        2) Increment the sender by an extra 1, to account for transit time.

    :param last_knowns:
    :return: Nothing. Almost everything happens by side effect. I'm so sorry.
    """
    global vector_clock
    last_knowns[str(sender)] += 1 # Algorithm says adjust for transit time.
    for port, t in last_knowns.items():
        port = int(port)
        if int(last_knowns[str(port)]) > int(vector_clock[port]):
            vector_clock[port] = int(last_knowns[str(port)])


def process_message(message):
    """
    Parses the message, appends to the global list (with the appropriate timestamp), and incorporates our new
    knowledge of timestamps across the system.

    :param message: The message send by another API node, after receiving a client facing /append.
        ..code-block:
            {
                'vector_clock': <dict<int>, <int>> ,
                'sender': <int>,
                'value': <int>
            }
    :return: Nada. Again, I'm so sorry.
    """
    global vector_clock
    last_known = message.get('vector_clock', vector_clock)
    sender = message.get('sender')
    val = message.get('value')

    my_list.append({'value': val, 'vector_clock': frozen(last_known)})
    update_times(sender, last_known)


def process_messages():
    """
    Processing one message is an "atomic action" as defined in Fidge's paper. For this we have to increment the local
    clock by 1. This method goes through all the messages awaiting processing, and kicks off their processing. The
    side effects are updating our local vector, and actually adding elements to the globally maintained `my_list`.

    :return: Nothing.
    """
    global messages
    while messages:
        message = messages.popleft()
        increment_clock()
        process_message(message)


class AppendHandler(tornado.web.RequestHandler):

    def busy(self):
        """
        Ends a request while messages are still being sent.
        :return:
        """
        self.clear()
        self.set_status(503)
        self.finish()

    def get(self):
        """
        This method returns to the user the global `my_list`. Before it does that it processes messages with
        `process_messages` just in case there is anything lingering.
        :return:
        """
        process_messages()
        self.write(json.dumps(my_list))

    def post(self):
        """
        Appends an element to the globally maintained `my_list`.
        """
        while threads:
            thread = threads.popleft()
            if thread.is_alive():
                threads.append(thread)
                return self.busy()
        process_messages() # Increments happen per-message.
        increment_clock() # This one is separate for the client-requested append.
        value = process_event(self.request)
        thread = threading.Thread(target=lambda: fanout_sync({'value': value, 'sender': options.port, 'vector_clock': frozen(vector_clock)}))
        thread.start()
        threads.append(thread)
        self.write("OK")


class MessageHandler(tornado.web.RequestHandler):

    def post(self):
        """
        Queues a message from another API for processing.
        :return:
        """
        messages.append(json.loads(self.request.body))
        self.write("OK")


if __name__ == '__main__':
    try:
        global messages
        messages = collections.deque()
        tornado.options.parse_command_line()
        application = tornado.web.Application([
            (r"/append", AppendHandler),
            (r"/message", MessageHandler)], debug=True)

        server = tornado.httpserver.HTTPServer(application)
        server.bind(options.port)
        server.start()
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        process_messages()
        print("Vector Clock", vector_clock)
        print(json.dumps(my_list, indent=2))
