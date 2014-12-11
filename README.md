# pyconspack

This is an implementation of [CONSPACK](https://github.com/conspack/) for Python.

CONSPACK was inspired by MessagePack, and by the general lack of
features among prominent serial/wire formats:

* JSON isn't terrible, but can become rather large, and may be susceptible to parsing exploits and is usually unable to be allocation-restricted.

* BSON (binary JSON) doesn't really solve much; though it encodes
  numbers, it's not particularly smaller or more featureful than JSON.

* MessagePack is small, but lacks significant features; it can
  essentially encode arrays or maps of numbers, and any interpretation
  beyond that is up to the receiver.

* Protobufs and Thrift are static.

It should be noted that, significantly, **none** of these support
references.  Of course, references can be implemented at a higher
layer (e.g., JSPON), but this requires implemeting an entire
additional layer of abstraction and escaping, including rewalking the
parsed object hierarchy and looking for specific signatures, which can
be error-prone, and hurt performance.

Additionally, none of these appear to have much in the way of
security, and communicating with an untrusted peer is probably not
recommended.

CONSPACK, on the other hand, attempts to be a more robust solution:

* Richer set of data types, differentiating between arrays, lists,
  maps, typed-maps (for encoding classes/structures etc), numbers,
  strings, symbols, and a few more.

* Very compact representation that can be smaller than MessagePack.

* In-stream references, including optional forward references, which
  can allow for shared or circular data structures.  Additionally,
  remote references allow the receiver the flexibility to parse and
  return its own objects without further passes on the output.

* Security, including byte-counting for (estimated) maximum output
  size, and the elimination of circular data structures. **(Not yet
  implemented.)**

See [SPEC](https://github.com/conspack/cl-conspack/blob/master/doc/SPEC) for
complete details on encoding.

**Note:** This is mostly complete, but nt all features may yet be implemented, such as byte-counting or Properties.

## Usage

Usage is relatively straightforward:

```python
from pyconspack import Conspack

with open("test.cpk", "wb") as f:
    bytes = Conspack.encode([1, 2, 3, "hello conspack"])
    f.write(bytes)

    value = Conspack.decode(bytes)
    print("Decoded:", value)
```

The `Conspack` object has a number of ways to encode and decode
values.  See below for encoder and decoder options.

* `Conspack.encode(val, **options)`: Encode `val`, returning a bytearray.
* `Conspack.decode(val, **options)`: Decode the bytearray `val`, returning an object
* `Conspack.encode_file(filename, val, **options)`: Trivially encode `val` and write to `filename`.
* `Conspack.decode_file(filename, **options)`: Trivially decode from `filename`.
* `Conspack.encoder(**options)`: Create and return an encoder.
* `Conspack.decoder(**options)`: Create and return a decoder.

For simple uses, encoding and decoding single values may suffice.  If
you wish to encode or decode multiple values on a stream, particularly
if you wish to preserve references between values, you will likely
need to use the `Encoder` or `Decoder` manually.

## Options

The following options may be specified as keywords to encoders:

* `all_floats_single`: This will encode all floats as single-precision.  By default, floats are encoded with full double precision, and only `pyconspack.SingleFloat` values are encoded as single.
* `single_char_strings`: Encode single-character strings as strings, rather than characters.  By default, a single-character string is treated as a character.  With this option, only `pyconspack.Char` values are treated as characters.
* `lists_are_vectors`: This will treat all values that are exactly of type `list` as a vector.  By default, only `array`, `bytearray`, `bytes`, and `pyconspack.Vector` are treated as vectors.
* `norefs`: Do not generate tags or references.
* `encoders`: A dictionary of CLASS to FUNCTION.  FUNCTION is called with an instance of CLASS, and should return a tuple of (SYMBOL, DICT), where SYMBOL will be encoded as the type specifier, and DICT as the map for a TMAP.
* `no_sub_underscores`: When encoding dictionaries, when keys are strings, they are converted implicitly to CONSPACK keywords, and underscores are substituted with dashes, e.g. "foo_bar" becomes `:foo-bar`, unless the string also *starts* with an underscore, e.g., "__foo__" becomes `:__foo__`.  If this option is specified, substitution will not happen, e.g., "foo_bar" becomes `:foo_bar`.

The following options may be specified as keywords to decoders:

* `decoders`: A dictionary of CLASS to FUNCTION.  FUNCTION is called with a symbol and dictionary, which are the type specifier and map for a TMAP.
* `rref_decoder`: A function which processes objects in RRefs encountered.  This takes the object encountered, not a T.RRef.
* `pointer_decoder`: A function which processes values in Pointers encountered.
This takes the (integer) value, not a T.Pointer

## Types

Default python types do not quite have enough variety to encode all CONSPACK types.  For example, lists seem to be used predominantly in Python as "lists or arrays", but CONSPACK makes a distinction between vectors and lists.  Thus, numerous "type wrappers" are provided in `pyconspack.types`, which, along with other python types such as `array` and `bytearray`, allow for complete encoding.

```python
import pyconspack.types as T
```

* `T.DottedList`: This represents a list whose last element is considered "not NIL".  Normally, Python lists are encoded as lists, with a final, implicit "NIL" element, as per Lisp lists, e.g. `(1 2 3 4)`.  However, to properly distinguish Lisp "dotted lists", e.g. `(1 2 3 . 4)`, one may use `DottedList`.  You should almost certainly never do this.
* `T.SingleFloat`: By default, all Python floats are doubles.  They are also encoded this way; however this is often overkill.  In cases where `all_floats_single` is undesirable, one may wrap a float with `SingleFloat`, and it will be encoded as such.
* `T.Char`: Python doesn't have a "character" type, but pyconspack encodes single-character-strings as CONSPACK characters, and decodes them as strings.  However, other languages may *not* decode them as strings.  You may wish to specify `single_char_strings`, and use `Char` to wrap strings specifically as characters.
* `T.Vector`: Python lists are encoded as lists.  `array` and `bytearray` are encoded as fixed-type vectors.  However, you may wish to encode a vector that is *not* of a fixed type, which is what `Vector` allows.
* `T.Pointer`: This encodes a numeric as a CONSPACK "pointer" type.  (As per the spec, pointers have no semantics, but are intended for use in nonlinear file  formats, where it may be desirable to distinguish and update a value of fixed length.)
* `T.Index`: This is used primarily internally to encode a numeric value as an INDEX value.
* `T.Cons`: Python doesn't have a CONS type, though lists of length 1, or DottedLists of length 2, are encoded as such as an optimization.  `Cons` may be used to do this explicitly, e.g. for tree-like structures.
* `T.RRef`: This is used to encode an RREF, and may be given a value which is the RREF's value.  As per Remote References, semantics are left to the user.
* `T.Package` and `T.Symbol`: Python does not have the concept of packages and symbols, though dictionary keys that are strings are implicitly converted to Symbols in the "KEYWORD" package.  These add the explicit ability to encode Symbols and Packages.  Use `T.package`, `T.intern`, and (as a convenience) `T.keyword` to create and manage these.  It is also possible to create an "uninterned" Symbol, and it will be encoded with a `NIL` package, if necessary.

## Notes

* This is not 100% complete, but would be fairly trivial to fill in the last few features.

* This makes a number of assumptions and does various implicit conversions, but works rather well in practice, in my experience.

* Python has `None`, `False`, and various other values that are "false-like".  CONSPACK only encodes one, `NIL`, which is also the zero-length list.  Conveniently, the zero-length list in Python is one of many "false-like" values, so `NIL` is decoded as such!

* Python is, obviously, not my "native" language.  I have tried to follow Python idioms I've seen, but I don't promise to have done so.  Patches for improvement welcomed!

* This was made primarily for [`io_scene_consmodel`](https://github.com/rpav/io_scene_consmodel/), a blender plugin for exporting CONSPACK-format model data.
