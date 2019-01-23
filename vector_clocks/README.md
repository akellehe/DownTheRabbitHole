# Vector Clocks

This is the code referenced in our [meetup on vector clocks](https://www.meetup.com/Down-the-Rabbit-Hole-Exploring-Distributed-Systems/events/252937134/). There are some caveats to this implementation.

You can find the slides [here](https://docs.google.com/presentation/d/1PDpi-YhWodwFhATr2ulT-O9ibq6hdj2SAuy_LE2SQ-o/edit?usp=sharing).

These implementations all run in `python3`. Compatibility with `python2.x` is untested, and probably doesn't work.

## Lamport's Algorithm

As one of our attendees, the man in the third row, pointed out: there is a bit of erratta on Lamport's algorithm. I have to apologize for that, I implemented the [wikipedia version](https://en.wikipedia.org/wiki/Lamport_timestamps) of the algorithm, which incorrectly states that you should set the time (upon receiving a message) to the `max(current_time, incoming_time)` _plus one_. That "plus one" caused an off-by-one error on the slides. 

I've since corrected that on the slides, but this code for Lamport's algorithm still suffers that malady.

You should run four instances of the `lamport-server.py` process. They should be listening on your local ports `8888-8891`. You can pass the port name on the CLI with the kwarg `--port=8888`, for example. 

Once the servers are running, you can use the `lamport-client.py` process to send them messages. This process runs synchronously, it's a really "nice" client. If you run concurrently you'll encounter deadlock conditions as the API nodes try to communicate with each other as they're sending messages back and forth over the same ports (thanks to python's GIL). This issue is remedied in the implementaiton of vector clocks.


## Vector Clocks Algorithm

This implementation works as expected. I'm sorry I didn't use the best programming paradigms as I was developing it, I did it in a few hours as I was studying, and didn't take great care to clean it up afterwards. If someone would like to submit a pull request to clean it up (or even write unit tests!) it would be a really great exercise to make sure you really understand the material.

To run this implementation it works a lot like the `lamport-server.py` process. Start four instances of `vc-server.py` as `python3 vc-server.py --port=8888` for ports `8888-8891`. 

Once your servers are all running you can send messages with the client, `vc-client.py`. This one has two code blocks. One is synchronous, the other is very asynchronous. You'll find in the first case the messages are nicely ordered, but in the second case there are all kinds of conflicts.

Conflicts can occur after full syncs before any messages are sent, or anytime _between_ syncs of nodes. A conflict arises any time two messages don't satisfy the binary condition in the definition of our poset (partially ordered set).

## Contributing

If you would like to fix the Lamport implementation, clean up code, or add anything else to this repo (e.g. unit tests) please feel free!! Just fork it and submit a pull request. Since we're all just messing around here I won't hold your code to any strict guidelines. All contributions are welcomed.


