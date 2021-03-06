"""# PyPatt - Function Implementation

## Notes

* Rather than adding `when` clause, just use `and`
  match(value, (bind.first, bind.second)) and bound.first < bound.second

## Development

* Should anyof(*patterns) be added?
  * "match(value, anyof('foo', 'bar'))"
  * Should the short-form of this just override any.__call__?
* Should allof(*patterns) be added?
  * "match(value, allof((0, _, _), (_, _, 1)))"
  * "match(value, (allof(anyof('grant', 'shannon'), bind.name), bind.name))"
* todo: bind.many
  class Many(object):
      def __init__(self, name, count=slice(None), values=(Anything,)):
          self.count = count
          self.values = values
          self.name = name
      def __getitem__(self, index):
          "Index may be any of:
          name
          twople ~ (name, slice)
          threeple ~ (name, slice, value-spec)
          "
          # todo
  many = Many()
  * Many should have special significance in _sequence_rule which permits
    binding to multiple values.
  * To be really powerful, this should support backtracking in the style of
    regular expressions.
  * Maybe the third argument to slice could be True / False to indicate greedy
    or non-greedy matching.
  * If second argument is a tuple, does that work like a character class and
    match any of the stated objects? How then to match a tuple? Put it in
    another tuple!
  * This is close to supporting the full power of regular languages. If it were
    possible to `or` expressions (as done with `(A|B)`) then it would be
    feature-complete.
    Actually, that's possible with:
        bind.many(1, (0, 1), 'zeroorone')
    But could you put a `bind.many` within a `bind.many` like:
        bind.many(1, (bind.many(:, int), bind.many(:, float)), 'intsorfloats')
    And does that recurse? So you could have bind.many nested three times over?
    That sounds pretty difficult to achieve. How does naming of the nested
    nested groups sound? Lol, Python's regex package has this same difficulty.
    It's hard to imagine why anyone would create such complex data structure
    queries and want to express them in this way.
  * Why not instead map patterns to letters and do traditional regex-matching?

"""

from sys import hexversion
from collections import namedtuple, Sequence

Case = namedtuple('Case', 'name predicate rule')
_cases = []

class Mismatch(Exception):
    pass

###############################################################################
# Match anything
###############################################################################

class Anything(object): pass

def _anything_predicate(matcher, value, pattern):
    return isinstance(pattern, Anything)

def _anything_rule(matcher, value, pattern):
    return value

_cases.append(Case('anything', _anything_predicate, _anything_rule))

###############################################################################
# Match names
###############################################################################

Name = namedtuple('Name', 'value')

class Binder(object):
    def __getattr__(self, name):
        if name == 'any':
            return Anything()
        elif name in ('_push', '_pop', 'restore'):
            raise AttributeError
        else:
            return Name(name)

bind = Binder()

def _name_predicate(matcher, value, pattern):
    return isinstance(pattern, Name)
    
def _name_store(matcher, name, value):
    if name in matcher.names:
        if value != matcher.names[name]:
            raise Mismatch
    matcher.names[name] = value

def _name_rule(matcher, value, pattern):
    _name_store(matcher, pattern.value, value)
    return value

_cases.append(Case('names', _name_predicate, _name_rule))

###############################################################################
# Match patterns
###############################################################################

Pattern = namedtuple('Pattern', 'pattern name')

def like(pattern, name='result'):
    return Pattern(pattern, name)

def _pattern_predicate(matcher, value, pattern):
    return isinstance(pattern, Pattern)

import re

if hexversion > 0x03000000:
    unicode = str

_pattern_errors = (
    AttributeError, LookupError, NotImplementedError, TypeError, ValueError
)

def _pattern_rule(matcher, value, pattern):
    name = pattern.name
    pattern = pattern.pattern

    if isinstance(pattern, (str, unicode)):
        if not isinstance(value, (str, unicode)):
            raise Mismatch
        func = lambda value: re.match(pattern, value)
    else:
        func = pattern

    try:
        result = func(value)
    except _pattern_errors:
        raise Mismatch

    if not result:
        raise Mismatch

    if name is not None:
        _name_store(matcher, name, result)

    return result

_cases.append(Case('patterns', _pattern_predicate, _pattern_rule))

###############################################################################
# Match types
###############################################################################

def _type_predicate(matcher, value, pattern):
    return type(pattern) == type

def _type_rule(matcher, value, pattern):
    if type(value) == type and issubclass(value, pattern):
        return value
    elif isinstance(value, pattern):
        return value
    else:
        raise Mismatch

_cases.append(Case('types', _type_predicate, _type_rule))

###############################################################################
# Match literals
###############################################################################

if hexversion < 0x03000000:
    _literal_types = (type(None), bool, int, float, long, complex, basestring)
else:
    _literal_types = (type(None), bool, int, float, complex, str, bytes)

def _literal_predicate(matcher, value, pattern):
    return (
        isinstance(pattern, _literal_types)
        and isinstance(value, _literal_types)
    )

def _literal_rule(matcher, value, pattern):
    if value != pattern:
        raise Mismatch
    return value

_cases.append(Case('literals', _literal_predicate, _literal_rule))

###############################################################################
# Match sequences
###############################################################################

def _sequence_predicate(matcher, value, pattern):
    return (
        isinstance(value, type(pattern))
        and isinstance(value, Sequence)
        and len(value) == len(pattern)
    )

if hexversion < 0x03000000:
    from itertools import izip as zip

def _sequence_rule(matcher, value, pattern):
    args = (matcher.visit(one, two) for one, two in zip(value, pattern))
    type_value = type(value)
    if issubclass(type_value, tuple) and hasattr(type_value, '_make'):
        return type_value._make(args) # namedtuple case
    else:
        return type_value(args)

_cases.append(Case('sequences', _sequence_predicate, _sequence_rule))

###############################################################################
# Matching algorithm
###############################################################################

class Matcher(object):
    def __init__(self, cases=_cases):
        self.names = {}
        self.cases = _cases
    def __call__(self):
        return self.__class__(cases=self.cases)
    def visit(self, value, pattern):
        for name, predicate, rule in self.cases:
            if predicate(self, value, pattern):
                return rule(self, value, pattern)
        raise Mismatch

matcher = Matcher()

###############################################################################
# Bound names
###############################################################################

class AttrMap(object):
    def __init__(self, names):
        self._attrs = names
    def __getitem__(self, name):
        return self._attrs[name]
    def __repr__(self):
        return repr(self._attrs)

from functools import wraps

class Bounder(object):
    def __init__(self):
        self._maps = []
    def __getitem__(self, index):
        return self._maps[index]
    def __getattr__(self, name):
        return self[-1][name]
    def __len__(self):
        return len(self._maps)
    def __repr__(self):
        return repr(self._maps)
    def _push(self, names):
        self._maps.append(AttrMap(names))
    def _pop(self):
        return self._maps.pop()
    def restore(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = len(self)
            try:
                return func(*args, **kwargs)
            finally:
                while len(self) > start:
                    self._pop()
        return wrapper

bound = Bounder()

###############################################################################
# Match function
###############################################################################

def match(value, pattern, matcher=matcher):
    try:
        matcher = matcher()
        result = matcher.visit(value, pattern)
        names = matcher.names
        if names:
            bound._push(names)
        return True
    except Mismatch:
        return False
