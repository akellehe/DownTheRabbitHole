import multiprocessing
import time
import random

import redis
import requests


ENDPOINT = 'http://api.io:8080/bounded/cpu'


def send():
    print("Starting new process...")
    redis_cli = redis.StrictRedis('localhost', 63799)
    while True:
        time.sleep(0.5 + random.random())
        redis_cli.incr('client_requests')
        try:
            resp = requests.get(ENDPOINT)
            if 200 <= resp.status_code < 300:
                redis_cli.incr('client_requests_succeeded')
            else:
                print("request failed with code", resp.status_code)
                redis_cli.incr('client_requests_failed')
        except Exception as e:
            print('got exception', e) 
            redis_cli.incr('client_requests_failed')


threads = []
try:
    for i in range(100):
        t = multiprocessing.Process(target=send)
        t.start()
        threads.append(t)
        time.sleep(10)
except KeyboardInterrupt:
    for t in threads:
        t.join()

