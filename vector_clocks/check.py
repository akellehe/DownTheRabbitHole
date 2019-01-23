import requests
import operator
import json

ports = [8888, 8889, 8890, 8891]
for port in ports:
    resp = requests.get('http://localhost:{}/append'.format(port),
        headers={'Content-Type': 'application/json'}).text
    print(port, json.dumps(resp, indent=2))

    
