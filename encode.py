__all__ = ["Encoder"]

import re

import struct
from array import array

import pyconspack.header as H
import pyconspack.types as T
import pyconspack.error as E
import pyconspack.index as I

class EncodedObject:
    def __init__(self, typename, val):
        self.typename = typename
        self.val = val

class Encoder:
    def __init__(self, **kw):
        self.opt = kw
        self.bytes = bytearray()
        self.refs = set()
        self.tmaps = dict()
        self.tags = dict()
        self.written = set()
        self.tag = 0
        self.index = self._opt('index')

        if(self.index):
            self.index = I.Index(self.index)

    def encode(self, val):
        self._notice(val)
        return self._encode(val)

    def _encode(self, val, fixed=False):
        if(id(val) in self.tags and id(val) in self.written):
            return self.encode_ref(self.tags[id(val)], fixed)
        elif(id(val) in self.tags):
            self.encode_tag(self.tags[id(val)])

        if(val.__class__ in self.encoders):
            encoder = self.encoders[val.__class__]
        else:
            newval = self.encode_object(val)
            return self._encode(newval, fixed)

        self.written.add(id(val))
        encoder(self, val, fixed)

    def _write(self, b):
        bytes = self.bytes
        if(type(b) is int):
            bytes.append(b)
        else:
            bytes[len(bytes):len(bytes)] = b

    def _opt(self, name):
        return (name in self.opt) and (self.opt[name])

    def _refable(self, val):
        return \
            not (type(val) is int or
                 type(val) is float or
                 (type(val) is str and len(val) == 1 and
                  not self._opt('single_char_strings')))

    def encode_bool(self, val, fixed=False):
        if(val):
            self._write(1)
        else:
            self._write(0)

    def encode_int(self, val, fixed=False):
        if(fixed is False):
            code, fmt = H.guess_int(val)
            self._write(H.NUMBER | code)
        else:
            code, fmt = H.fixed_type_fmt(fixed)
            fmt = '>' + fmt

        if fmt:
            self._write(struct.pack(fmt, val))
        elif(code == H.INT128 or code == H.UINT128):
            if(val < 0):
                val += 2**128

            for i in reversed(range(16)):
                self._write((val >> (i * 8)) & 0xFF)

    def encode_double(self, val, fixed=False):
        if(self._opt('all_floats_single') or
           (fixed is not False and ((fixed & H.NUMBER_TYPE_MASK) == H.SINGLE_FLOAT))):
            return self.encode_float(val, fixed)

        if(not fixed):
            self._write(H.NUMBER | H.DOUBLE_FLOAT)
        self._write(struct.pack('>d', val))

    def encode_float(self, val, fixed=False):
        if(not fixed):
            self._write(H.NUMBER | H.SINGLE_FLOAT)
        self._write(struct.pack('>f', val))

    def encode_string(self, val, fixed=False):
        if(not self._opt('single_char_strings') and len(val) == 1):
            return self.encode_char(val)

        data = val.encode(encoding='utf-8', errors='strict')
        size_bytes, fmt = H.size_bytes(len(data))
        if(not fixed):
            self._write(H.STRING | size_bytes)
        self._write(struct.pack(fmt, len(data)))
        self._write(data)

    def encode_char(self, val, fixed=False):
        if(len(val) > 1):
            raise E.BadValue("{s} is not a character", val)

        data = val.encode(encoding='utf-8', errors='strict')
        if(not fixed):
            self._write(H.CHARACTER | len(data))
        self._write(data)

    def encode_list(self, val, fixed=False):
        if(self._opt('lists_are_vectors') and type(val) is list):
            return self.encode_vector(val)

        l = len(val)
        if(l == 0):
            return self.encode_bool(None)

        if((l == 2 and type(val) is T.DottedList) or (l == 1)):
            return self.encode_cons(val, fixed)

        if(type(val) is not T.DottedList):
            l += 1
        size_bytes, fmt = H.size_bytes(l)

        if(not fixed):
            self._write(H.CONTAINER | H.CONTAINER_LIST | size_bytes)
        self._write(struct.pack(fmt, l))
        for item in val:
            self._encode(item)

        if(type(val) is not T.DottedList):
            self._encode(None)

    def encode_vector(self, val, fixed=False):
        l = len(val)
        size_bytes, fmt = H.size_bytes(l)

        if(not fixed):
            self._write(H.CONTAINER | H.CONTAINER_VECTOR | size_bytes)
        self._write(struct.pack(fmt, l))
        for item in val:
            self._encode(item)

    def encode_fixed_vector(self, val, fixed=False):
        fixed_type = H.fixed_type(val, force_floats=self._opt('all_floats_single'))

        if(fixed_type is None):
            return self.encode_vector(val)

        l = len(val)
        size_bytes, fmt = H.size_bytes(l)
        if(not fixed):
            self._write(H.CONTAINER | H.CONTAINER_VECTOR | H.CONTAINER_FIXED |
                        size_bytes)
        self._write(struct.pack(fmt, l))
        self._write(fixed_type)

        for i in val:
            self._encode(i, fixed_type)

    def encode_map(self, val, fixed=False):
        self.encode_map_values(val, ((not fixed) and H.CONTAINER_MAP))

    def encode_object(self, val):
        if(id(val) in self.tmaps):
            return self.tmaps[id(val)]

        encoders = self._opt('encoders')
        if(not encoders or type(val) not in encoders):
            if(type(val) in Encoder.class_encoders):
                encoders = Encoder.class_encoders
            else:
                raise E.NoEncoder("Encoder for {v} (type {t}) not found".format(v=val, t=type(val)))

        typename, func = encoders[type(val)]
        encoded = EncodedObject(typename, func(val))
        self.tmaps[id(val)] = encoded
        self._notice(typename)
        self._notice(encoded)

        return encoded

    def dict_to_alist(self, d):
        return [T.Cons((k, v)) for (k,v) in d.items()]

    def encode_tmap(self, val, fixed=False):
        self.encode_map_values(val.val, ((not fixed) and H.CONTAINER_TMAP),
                               is_tmap=True, type_ob=val.typename)

    def encode_map_values(self, val, header=False, is_tmap=False,
                          type_ob=None):
        keys = val.keys()
        l = len(keys)
        size_bytes, fmt = H.size_bytes(l)

        if(header is not False):
            self._write(H.CONTAINER | header | size_bytes)

        self._write(struct.pack(fmt, l))

        if(is_tmap):
            self._encode(type_ob)

        for k in keys:
            # Key
            if(isinstance(k, str)):
                new_k = k
                if(not self._opt('no_sub_underscores') and k[0] != '_'):
                    new_k = re.sub(r'_', r'-', k)

                if(type_ob):
                    self._encode(T.intern(new_k, type_ob.package))
                else:
                    self._encode(T.keyword(new_k))
            else:
                self._encode(k)

            # Value
            self._encode(val[k])

    def encode_package(self, val, fixed=False):
        if(not fixed):
            self._write(H.PACKAGE)
        self._encode(val.name)

    def encode_symbol(self, val, fixed=False):
        if(self.index and val in self.index):
            return self.encode_index(self.index[val])

        if(val.package is T.package('keyword')):
            return self.encode_keyword(val, fixed)

        if(not fixed):
            self._write(H.SYMBOL)
        self._encode(val.name)
        self._encode(val.package)

    def encode_keyword(self, val, fixed=False):
        if(not fixed):
            self._write(H.SYMBOL | H.SYMBOL_KEYWORD)
        self._encode(val.name)

    def encode_pointer(self, val, fixed=False):
        size_bytes, fmt = H.size_bytes(val)
        if(not fixed):
            self._write(H.POINTER | size_bytes)
        self._write(struct.pack(fmt, val))

    def encode_cons(self, val, fixed=False):
        l = len(val)
        if(not fixed):
            self._write(H.CONS)

        if(l > 0): self._encode(val[0])
        else:      self._encode(None)

        if(l > 1): self._encode(val[1])
        else:      self._encode(None)

    def encode_rref(self, val, fixed=False):
        if(not fixed):
            self._write(H.REMOTE_REF)
        self._encode(val.value)

    def encode_index(self, val, fixed=False):
        if(val < 0):
            raise E.OutOfBounds("Invalid index {n}, index values must be positive".format(n=val))

        if(not fixed):
            if(val < 16):
                return self._write(H.INDEX | H.REFTAG_INLINE | val)

            size_bytes, fmt = H.size_bytes(val)
            self._write(H.INDEX | size_bytes)
        self._write(struct.pack(fmt, val))

    def encode_tag(self, val, fixed=False):
        if(not fixed):
            if(val < 16):
                return self._write(H.TAG | H.REFTAG_INLINE | val)

            size_bytes, fmt = H.size_bytes(val)
            self._write(H.TAG | size_bytes)
        self._write(struct.pack(fmt, val))

    def encode_ref(self, val, fixed=False):
        if(not fixed):
            if(val < 16):
                return self._write(H.REF | H.REFTAG_INLINE | val)

            size_bytes, fmt = H.size_bytes(val)
            self._write(H.REF | size_bytes)
        self._write(struct.pack(fmt, val))

    def _notice(self, val):
        if(self._opt('norefs')):
            return

        if(not self._refable(val)):
            return

        if(id(val) in self.refs):
            if(not id(val) in self.tags):
                self.tags[id(val)] = self.tag
                self.tag += 1
            return
        else:
            self.refs.add(id(val))

        if(isinstance(val, list) or
           isinstance(val, tuple)):
            for i in val:
                self._notice(i)
        elif(isinstance(val, dict)):
            for i in val:
                if(type(i) is not str):
                    self._notice(i)
                self._notice(val[i])
        elif(isinstance(val, T.Symbol)):
            self._notice(val.name)
            self._notice(val.package)
        elif(isinstance(val, EncodedObject)):
            self._notice(val.val)
        elif(val.__class__ not in self.encoders):
            self.encode_object(val)

    class_encoders = dict()
    def register(c, symbol, func):
        Encoder.class_encoders[c] = (symbol, func)

    def deregister(c):
        del Encoder.class_encoders[c]

    encoders = {
        bool: encode_bool,
        type(None): encode_bool,
        int: encode_int,
        T.SingleFloat: encode_float,
        float: encode_double,
        str: encode_string,
        T.Char: encode_char,
        tuple: encode_list,
        list: encode_list,
        T.Cons: encode_cons,
        T.DottedList: encode_list,
        array: encode_fixed_vector,
        bytes: encode_fixed_vector,
        bytearray: encode_fixed_vector,
        T.Vector: encode_vector,
        dict: encode_map,
        T.Package: encode_package,
        T.Symbol: encode_symbol,
        T.Pointer: encode_pointer,
        EncodedObject: encode_tmap,
        T.RRef: encode_rref,
        T.Index: encode_index,
    }
