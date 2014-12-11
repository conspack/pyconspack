from array import array
import pyconspack.error as E

BOOL = 0x00
BOOL_MASK = 0xFE

NIL = 0x00
FALSE = 0x00
TRUE = 0x01

NUMBER = 0x10
NUMBER_MASK = 0xF0
NUMBER_TYPE_MASK = 0x0F

CONTAINER = 0x20
CONTAINER_MASK = 0xE0

STRING = 0x40
STRING_MASK = 0xFC

REF = 0x60
REF_MASK = 0xFC
REF_INLINE_MASK = 0xF0

REMOTE_REF = 0x64
REMOTE_REF_MASK = 0xFF

POINTER = 0x68
POINTER_MASK = 0xFC

TAG = 0xE0
TAG_MASK = 0xFC
TAG_INLINE_MASK = 0xF0

CONS = 0x80
CONS_MASK = 0xFF

PACKAGE = 0x81
PACKAGE_MASK = 0xFF

SYMBOL = 0x82
SYMBOL_MASK = 0xFE

CHARACTER = 0x84
CHARACTER_MASK = 0xFC

PROPERTIES = 0x88
PROPERTIES_MASK = 0xFF

INDEX = 0xA0
INDEX_MASK = 0xE0

SIZE_8 = 0x00
SIZE_16 = 0x01
SIZE_32 = 0x02
SIZE_64 = 0x03
SIZE_MASK = 0x03

CONTAINER_VECTOR = 0x00
CONTAINER_LIST = 0x08
CONTAINER_MAP = 0x10
CONTAINER_TMAP = 0x18
CONTAINER_TYPE_MASK = 0x18
CONTAINER_FIXED = 0x04

REFTAG_INLINE = 0x10
REFTAG_INLINE_VALUE = 0xF
SYMBOL_KEYWORD = 0x01

INT8 = 0x0
INT16 = 0x1
INT32 = 0x2
INT64 = 0x3
UINT8 = 0x4
UINT16 = 0x5
UINT32 = 0x6
UINT64 = 0x7
SINGLE_FLOAT = 0x8
DOUBLE_FLOAT = 0x9
INT128 = 0xA
UINT128 = 0xB
COMPLEX = 0xC
RATIONAL = 0xF

def is_bool(h):
    return (h & BOOL_MASK) == BOOL

def is_number(h):
    return (h & NUMBER_MASK) == NUMBER

def is_container(h):
    return (h & CONTAINER_MASK) == CONTAINER

def is_string(h):
    return (h & STRING_MASK) == STRING

def is_ref(h):
    return ((h & REF_MASK) == REF) or \
           ((h & REF_INLINE_MASK) == (REF | REFTAG_INLINE))

def is_rref(h):
    return (h & REMOTE_REF_MASK) == REMOTE_REF

def is_pointer(h):
    return (h & POINTER_MASK) == POINTER

def is_tag(h):
    return ((h & TAG_MASK) == TAG) or \
           ((h & TAG_INLINE_MASK) == (TAG | REFTAG_INLINE))

def is_cons(h):
    return (h & CONS_MASK) == CONS

def is_package(h):
    return (h & PACKAGE_MASK) == PACKAGE

def is_symbol(h):
    return (h & SYMBOL_MASK) == SYMBOL

def is_keyword(h):
    return is_symbol(h) and ((h & SYMBOL_KEYWORD) == SYMBOL_KEYWORD)

def is_character(h):
    return (h & CHARACTER_MASK) == CHARACTER

def is_properties(h):
    return (h & PROPERTIES_MASK) == PROPERTIES

def is_index(h):
    return (h & INDEX_MASK) == INDEX

def guess_int(i):
    if(i >= -2**7 and i <= 2**7-1):           return (INT8, '>b')
    elif(i >= 0 and i <= 2**8-1):             return (UINT8, '>B')
    elif(i >= -2**15 and i <= 2**15-1):       return (INT16, '>h')
    elif(i >= 0 and i <= 2**16-1):            return (UINT16, '>H')
    elif(i >= -2**31 and i < 2**31-1):        return (INT32, '>i')
    elif(i >= 0 and i < 2**32-1):             return (UINT32, '>I')
    elif(i >= -2**63 and i < 2**63-1):        return (INT64, '>q')
    elif(i >= 0 and i < 2**64-1):             return (UINT64, '>Q')
    elif(i >= -2**127 and i <= 2**127-2):     return (INT128, None)
    elif(i >= 0 and i <= 2**128-1):           return (UINT128, None)
    else:
        raise E.OutOfRange("{n} is out of range".format(n=i))

def size_bytes(n):
    if(n < 2**8):
        return (SIZE_8, '>B')
    elif(n < 2**16):
        return (SIZE_16, '>H')
    elif(n < 2**32):
        return (SIZE_32, '>I')
    elif(n < 2**64):
        return (SIZE_64, '>Q')
    else:
        raise E.OutOfRange("{n} is out of range".format(n=n))

def fixed_type(a, force_floats=False):
    if(isinstance(a, (bytes, bytearray))):
        return NUMBER|UINT8

    if(not isinstance(a, array)):
        return None

    c = a.typecode
    if  (c == 'b'): return INT8|NUMBER
    elif(c == 'B'): return UINT8|NUMBER
    elif(c == 'h'): return INT16|NUMBER
    elif(c == 'H'): return UINT16|NUMBER
    elif(c == 'i'): return INT32|NUMBER
    elif(c == 'I'): return UINT32|NUMBER
    elif(c == 'l'): return INT32|NUMBER
    elif(c == 'L'): return UINT32|NUMBER
    elif(c == 'q'): return INT64|NUMBER
    elif(c == 'Q'): return UINT64|NUMBER
    elif(c == 'f'): return SINGLE_FLOAT|NUMBER
    elif(c == 'd'):
        if(force_floats):
            return SINGLE_FLOAT|NUMBER
        else:
            return DOUBLE_FLOAT|NUMBER
    # Of course, UTF-8 isn't fixed-length
    else:
        return None

def fixed_type_fmt(h):
    t = h & NUMBER_TYPE_MASK

    if  (t == INT8):    return (1, 'b')
    elif(t == UINT8):   return (1, 'B')
    elif(t == INT16):   return (2, 'h')
    elif(t == UINT16):  return (2, 'H')
    elif(t == INT32):   return (4, 'i')
    elif(t == UINT32):  return (4, 'I')
    elif(t == INT64):   return (8, 'q')
    elif(t == UINT64):  return (8, 'Q')
    elif(t == INT128):  return (16, None)
    elif(t == UINT128): return (16, None)
    elif(t == SINGLE_FLOAT): return (4, 'f')
    elif(t == DOUBLE_FLOAT): return (8, 'd')
