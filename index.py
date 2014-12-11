__all__ = ["Index"]

import pyconspack.types as T

class Index:
    def __init__(self, vals):
        def maybe_keyword(x):
            if (type(x) is str):
                return T.keyword(x)
            return x

        self.index = dict()
        self.vals = map(maybe_keyword, vals)

        for i, val in enumerate(self.vals):
            self.index[val] = i

    def __contains__(self, x):
        return x in self.index

    def __getitem__(self, x):
        return self.index[x]

    def index(self, i):
        return (i < len(self.vals)) and self.vals[i]

    def __str__(self):
        return '<Index: ' + self.index.__str__() + '>'
