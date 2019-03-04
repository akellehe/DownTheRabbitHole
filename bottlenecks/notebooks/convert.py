import sys
import pickle


filename = sys.argv[1]
with open(filename, 'rb') as fp:
    unpickled = pickle.loads(fp.read())
    with open(filename + '.2', 'wb') as fp:
       fp.write(pickle.dumps(unpickled, protocol=2)) 
