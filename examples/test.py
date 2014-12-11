#!/usr/bin/python3.4

import pyconspack as cpk
import pyconspack.types as T
from pyconspack import Conspack
from array import array

class SomeClass:
    def __init__(self, *data, **kw):
        for d in data:
            for key in d:
                setattr(self, key.name.lower(), d[key])

        for key in kw:
            setattr(self, key, kw[key])

    def encode(self):
        return self.__dict__

    def __repr__(self):
        return "SomeClass({n})".format(n=self.__dict__)

Conspack.register(SomeClass, T.intern('some-class', 'cl-user'),
                  encoder=SomeClass.encode,
                  decoder=SomeClass)

dupe = T.intern('foo', 'cl-user')
value = [SomeClass(foo=dupe), SomeClass(foo=dupe)]

with open("/home/rpav/test.cpk", "wb") as f:
    ba = Conspack.encode(value,
                         index = ['x', 'y', 'z'])
                         
    print("value =", value.__repr__())
    print(ba)
    f.write(ba)

    v = Conspack.decode(ba)
    print("Decoded:", v, v.__class__)
