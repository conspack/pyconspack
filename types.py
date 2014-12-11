__all__ = ["DottedList", "SingleFloat", "Char", "Vector", "Cons",
           "Pointer", "RRef", "Index",
           "Package", "Symbol", "package", "intern", "keyword"]

import pyconspack
import pyconspack.error as E

class CustomType:
    def __repr__(self):
        return "pyconspack." + self.__class__.__name__ + "(" + self.base_repr() + self.extra_repr() + ")"

    def base_repr(self): return ""
    def extra_repr(self): return ""

class CustomBuiltinType(CustomType):
    def base_repr(self):
        base = self.__class__.__bases__[1]
        return base.__repr__(self)
    
class DottedList(CustomBuiltinType, list): pass
class SingleFloat(CustomBuiltinType, float): pass
class Char(CustomBuiltinType, str): pass
class Vector(CustomBuiltinType, list): pass
class Pointer(CustomBuiltinType, int): pass
class Index(CustomBuiltinType, int): pass
class Cons(CustomBuiltinType, tuple): pass

class RRef(CustomType):
    def __init__(self, val):
        self.value = val

    def extra_repr(self):
        return self.value.__repr__()

class Package(CustomType):
    packages = dict()

    def find(name, keepcase=False):
        if(not name):
            return name
        elif(type(name) is Package):
            return name
        elif(not keepcase):
            name = name.upper()
            
        if(name in Package.packages):
            return Package.packages[name]

    def __init__(self, name, keepcase=False):
        if(not keepcase):
            name = name.upper()

        if(name in Package.packages):
            raise E.PackageExists("Package called {n} already exists".format(n=name))

        self.name = name
        self.symbols = dict()
        Package.packages[name] = self

    def intern(self, symbol):
        if(type(symbol) is str):
            symbol = Symbol(symbol)

        name = symbol.name
        if(name in self.symbols and symbol.package == self):
            return self.symbols[name]

        self.symbols[name] = symbol
        symbol.package = self
        return symbol

    def find_symbol(self, name):
        if(name in self.symbols):
            return self.symbols[name]

    def unintern(self, symbol):
        if(symbol.name in self.symbols):
            del self.symbols[name]

    def extra_repr(self):
        return self.name.__repr__()

    def __str__(self):
        return '<pyconspack.Package ' + self.name + '>'

def package(name, keepcase=False):
    return name and (Package.find(name) or Package(name, keepcase))

def intern(name, pkg=None, keepcase=False):
    if(not isinstance(name, str)):
        raise E.BadValue('{n} is not a string'.format(n=name))

    if(not keepcase):
        name = name.upper()

    if(pkg):
        return package(pkg).find_symbol(name) or \
            Symbol(name, package(pkg))
    else:
        return Symbol(name)

def keyword(name, keepcase=False):
    kw = pyconspack.types.package('KEYWORD')

    if(not keepcase):
        name = name.upper()

    return kw.find_symbol(name) or \
        pyconspack.types.intern(name, 'KEYWORD', keepcase)
    
class Symbol(CustomType):
    # None is a valid package, this represents uninterned symbols
    def __init__(self, name, pkg=None, keepcase=False):
        if(keepcase):
            self.name = name
        else:
            self.name = name.upper()

        self.package = None
        pkg = package(pkg)
        pkg and pkg.intern(self)

    def __str__(self):
        if(self.package is package('keyword')):
            return ':' + self.name
        elif(not self.package):
            return '#:' + self.name
        else:
            return self.package.name + '::' + self.name

    def extra_repr(self):
        s = self.name.__repr__()
        if(self.package is None):
            return s + ", None"
        else:
            return s + ", '" + self.package.name + "'"

    def is_keyword(self):
        return self.package == pyconspack.types.package('KEYWORD')
