__all__ = ["Decoder"]

import struct
from array import array

import pyconspack.header as H
import pyconspack.types as T
import pyconspack.error as E
import pyconspack.index as I

class ForwardRef:
    def __init__(self, tag):
        self.tag = tag

    def set(self, place, index = None, is_key = False):
        self.place = place
        self.index = index
        self.is_key = is_key

    def replace(self, value):
        # Note that FREF=FREF doesn't really work... but a dict()
        # can't currently be a key anyway, so stupidity prevents this
        # from really being used at all.
        if(self.is_key):
            oldval = self.place[self]
            del self.place[self]
            self.place[value] = oldval
        else:
            self.place[self.index] = value

class Decoder:
    def __init__(self, **kw):
        self.opt = kw
        self.frefs = dict()
        self.tags = dict()
        self.index = self._opt('index')

        if(self.index):
            self.index = I.Index(self.index)

    def read_header(self, f):
        return f.read(1)[0]

    def read_size(self, h, f):
        size_bytes = h & H.SIZE_MASK
        if  (size_bytes == 0): return struct.unpack('B', f.read(1))[0]
        elif(size_bytes == 1): return struct.unpack('>H', f.read(2))[0]
        elif(size_bytes == 2): return struct.unpack('>I', f.read(4))[0]
        elif(size_bytes == 3): return struct.unpack('>Q', f.read(8))[0]

    def _opt(self, name):
        return (name in self.opt) and (self.opt[name])

    def _push_fref(self, tag):
        fref = ForwardRef(tag)
        if(tag in self.frefs):
            self.frefs[tag].append(fref)
        else:
            self.frefs[tag] = [fref]

        return fref

    def _maybe_fref(self, val, place, index=None, is_key=False):
        if(not type(val) is ForwardRef):
            return

        val.set(place, index, is_key)

    def decode(self, f):
        return self._decode(f)

    def _decode(self, f, fixed=None):
        if(not fixed):
            h = self.read_header(f)
        else:
            h = fixed

        if  (H.is_bool(h)):      return self.decode_bool(h)
        elif(H.is_number(h)):    return self.decode_number(h, f)
        elif(H.is_index(h)):     return self.decode_index(h, f)
        elif(H.is_container(h)): return self.decode_container(h, f)
        elif(H.is_cons(h)):      return self.decode_cons(h, f)
        elif(H.is_string(h)):    return self.decode_string(h, f)
        elif(H.is_character(h)): return self.decode_character(h, f)
        elif(H.is_rref(h)):      return self.decode_rref(h, f)
        elif(H.is_pointer(h)):   return self.decode_pointer(h, f)
        elif(H.is_package(h)):   return self.decode_package(h, f)
        elif(H.is_symbol(h)):    return self.decode_symbol(h, f)
        elif(H.is_tag(h)):       return self.decode_tag(h, f)
        elif(H.is_ref(h)):       return self.decode_ref(h, f)
        else:
            raise E.BadHeader("Bad header byte: 0b{h:08b}".format(h=h))

    def decode_bool(self, h):
        if(h == 0x00): return ()
        else:          return True

    def decode_n(self, f, c):
        n = 0
        for i in range(c):
            n <<= 8
            n |= f.read(1)[0]
        return n

    def decode_number(self, h, f):
        c, fmt = H.fixed_type_fmt(h)

        if(fmt): return struct.unpack('>'+fmt, f.read(c))[0]
        elif(t == H.INT128):
            n = self.decode_n(f, 16)
            if(n > 2**127):
                n -= 2**128
            return n
        elif(t == H.UINT128):
            return self.decode_n(f, 16)

    def decode_container(self, h, f):
        t = h & H.CONTAINER_TYPE_MASK

        if  (t == H.CONTAINER_VECTOR): return self.decode_vector(h, f)
        elif(t == H.CONTAINER_LIST):   return self.decode_list(h, f)
        elif(t == H.CONTAINER_MAP):    return self.decode_map(h, f)
        elif(t == H.CONTAINER_TMAP):   return self.decode_map(h, f)

    def decode_list(self, h, f):
        size = self.read_size(h, f)
        fixed = None
        if(h & H.CONTAINER_FIXED):
            fixed = f.read(1)[0]

        l = []
        for i in range(size-1):
            val = self._decode(f, fixed)
            l.append(val)
            self._maybe_fref(val, l, i)

        final = self._decode(f, fixed)
        
        if(final == () or
           not (h & H.CONTAINER_TYPE_MASK) == H.CONTAINER_LIST):
            return l
        else:
            l = T.DottedList(l)
            l.append(final)
            self._maybe_fref(final, l, len(l)-1)
            return T.DottedList(l)

    def decode_vector(self, h, f):
        if(not (h & H.CONTAINER_FIXED)):
            return T.Vector(self.decode_list(self, h, f))
        
        size = self.read_size(h, f)
        fixed = f.read(1)[0]
        c, fmt = H.fixed_type_fmt(fixed)
        a = array(fmt)

        for i in range(size):
            val = self._decode(f, fixed)
            a.append(val)
            self._maybe_fref(val, a, i)

        return a

    def decode_map(self, h, f):
        size = self.read_size(h, f)

        fixed = None
        if(h & H.CONTAINER_FIXED):
            fixed = self.read_header(f)

        tmap_type = None
        if((h & H.CONTAINER_TYPE_MASK) == H.CONTAINER_TMAP):
            tmap_type = self._decode(f)

        d = dict()
        for i in range(size):
            k = self._decode(f, fixed)
            v = self._decode(f)
            self._maybe_fref(k, d, is_key=True)
            self._maybe_fref(v, d, k)
            d[k] = v

        if(tmap_type):
            decoders = self._opt('decoders')
            if(not decoders or tmap_type not in decoders):
                if(tmap_type in Decoder.class_decoders):
                    decoders = Decoder.class_decoders
                else:
                    raise E.NoDecoder("Decoder for {t} not found".format(t=tmap_type))

            return decoders[tmap_type](d)
        else:
            return d

    def decode_string(self, h, f):
        size = self.read_size(h, f)
        return f.read(size).decode(encoding='utf-8', errors='strict')

    def decode_character(self, h, f):
        size = h & H.SIZE_MASK
        return f.read(size).decode(encoding='utf-8', errors='strict')

    def decode_package(self, h, f):
        name = self._decode(f)
        return T.package(name)
        
    def decode_symbol(self, h, f):
        name = self._decode(f)
        package = None
        
        if(H.is_keyword(h)):
            package = "KEYWORD"
        else:
            package = self._decode(f)

        return T.intern(name, package)

    def decode_rref(self, h, f):
        decoder = self._opt('rref_decoder')
        rref = self._decode(f);

        if(decoder):
            return decoder(rref)
        else:
            return T.RRef(rref)

    def decode_pointer(self, h, f):
        decoder = self._opt('pointer_decoder')
        val = self.read_size(h, f)

        if(decoder):
            return decoder(val)
        else:
            return T.Pointer(val)

    def decode_cons(self, h, f):
        car = self._decode(f)
        cdr = self._decode(f)

        if(not cdr):
            return [car]
        else:
            return T.DottedList([car,cdr])

    def decode_tag(self, h, f):
        tag = None
        if(h & H.REFTAG_INLINE):
            tag = h & H.REFTAG_INLINE_VALUE
        else:
            tag = self.read_size(h, f)

        ob = self._decode(f)
        self.tags[tag] = ob

        if(tag in self.frefs):
            self.replace_frefs(tag, ob)
        
        return ob

    def decode_ref(self, h, f):
        tag = None
        if(h & H.REFTAG_INLINE):
            tag = h & H.REFTAG_INLINE_VALUE
        else:
            tag = self.read_size(h, f)

        if(tag in self.tags):
            return self.tags[tag]

        return self._push_fref(tag)

    def replace_frefs(self, tag, val):
        for f in self.frefs[tag]:
            f.replace(val)

    def decode_index(self, h, f):
        val = None
        if(h & H.REFTAG_INLINE):
            val = h & H.REFTAG_INLINE_VALUE
        else:
            tag = self.read_size(h, f)

        if(self.index):
            return self.index.index(val) or T.Index(val)
        else:
            return T.Index(val)
        

    class_decoders = dict()
    def register(symbol, func):
        Decoder.class_decoders[symbol] = func

    def deregister(symbol):
        del Decoder.class_decoders[symbol]
