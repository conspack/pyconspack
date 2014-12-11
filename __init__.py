from pyconspack.types import *
from pyconspack.encode import *
from pyconspack.decode import *

class FileLikeBytes:
    def __init__(self, ba):
        self.bytes = ba
        self.pos = 0

    def read(self, n):
        b = self.bytes[self.pos:self.pos+n]
        self.pos += n
        return b

    def seek(self, n):
        self.pos = n

    def tell(self):
        return self.pos

class Conspack:
    def encode(val, **kw):
        encoder = Encoder(**kw)
        encoder.encode(val)
        return encoder.bytes

    def encoder(**kw):
        return Encoder(**kw)

    def decoder(**kw):
        return Decoder(**kw)

    def _decode(f, **kw):
        decoder = Decoder(**kw)
        return decoder.decode(f)

    def decode(b, **kw):
        return Conspack._decode(FileLikeBytes(b), **kw)

    def encode_file(filename, val, **kw):
        with open(filename, "wb") as f:
            f.write(Conspack.encode(val, **kw))
            
    def decode_file(filename, **kw):
        with open(filename, "rb") as f:
            return Conspack._decode(f, **kw)

    def register(c, symbol, encoder, decoder):
        Encoder.register(c, symbol, encoder)
        Decoder.register(symbol, decoder)

    def deregister(c):
        (symbol,) = Encoder.class_encoders[c]
        Encoder.deregister(c)
        Decoder.deregister(symbol)
