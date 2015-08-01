from __future__ import print_function

import re
import itertools
import operator
import fnmatch
import datetime, dateutil.parser

def flattened(l):
    result = _flatten(l, lambda x: x)

    while type(result) == list and len(result) and callable(result[0]):
        if result[1] != []:
            yield result[1]

        result = result[0]([])
        yield result

def _flatten(l, fn, val=[]):
    if type(l) != list:
        return fn(l)

    if len(l) == 0:
        return fn(val)

    return [lambda x: _flatten(l[0], lambda y: _flatten(l[1:],fn,y), x), val]

class FilterBase(object):
    def __repr__(self):
        return "<%s (%s) %s>" % (self.__class__.__name__, id(self), self.field if hasattr(self, 'field') else "")

    def __call__(self, row):
        raise NotImplementedError('How did you call %s directly!?!? This is a logic error in the program!' % self.__class__)

class FilterAggrigator(FilterBase):
    def __init__(self, *filters):
        self.filters = list(filters)

    def __repr__(self):
        return "<%s(%s) [%s]>" % (self.__class__.__name__, id(self), ", ".join(map(repr, self.filters)) if len(self.filters) > 0 else "")

    def __len__(self):
        return len(self.filters)

    def add_filter(self, filter):
        self.filters.append(filter)

class AndFilter(FilterAggrigator):
    def __call__(self, row):
        return all(
            flattened(
                map(lambda f: f(row), self.filters)))

class FilterStack(AndFilter):
    def __init__(self):
        super(FilterStack, self).__init__()
        self.stack = []

    def push(self, filter):
        self.add_filter(filter)
        self.stack.append(filter)

    def pop(self):
        self.stack.pop()

    def add_filter(self, filter):
        if len(self.stack) > 0:
            self.stack[-1].add_filter(filter)
        else:
            self.filters.append(filter)

class OrFilter(FilterAggrigator):
    def __call__(self, row):
        return any(
            flattened(
                map(lambda f: f(row), self.filters)))

class NotFilter(FilterAggrigator):
    def __call__(self, row):
        return map(lambda f: not f(row), self.filters)

class GlobFilter(FilterBase):
    def __init__(self, field, pattern):
        self.field = field
        self.filter = re.compile(
            fnmatch.translate(pattern), re.IGNORECASE)

    def __call__(self, row):
        return self.filter.match(str(getattr(row, self.field)))

class PredicateFilter(FilterBase):
    def __init__(self, field, predicate=None):
        self.field = field

        self.predicates = []
        if predicate:
            self.predicates.append(predicate)

    def __call__(self, row):
        value = getattr(row, self.field)
        return any(itertools.imap(lambda f: f(value), self.predicates))

    def __len__(self):
        return len(self.predicates)

    def append(self, predicate):
        self.predicates.append(predicate)

class RegexFilter(FilterBase):
  def __init__(self, field, pattern, flags):
    self.predicate = re.compile(pattern, flags)
    self.fieldgetter = operator.attrgetter(field)

  def __call__(self, row):
    value = self.fieldgetter(row)
    return bool(self.predicate.match(value))

class ComparatorFilter(FilterBase):
  def __init__(self, predicate, field, rhs):
    self.predicate = predicate
    self.fieldgetter = operator.attrgetter(field)
    self.rhs = rhs

  def __call__(self, row):
    value = self.fieldgetter(row)

    t = type(value)
    rhs = self.rhs
    if t is datetime.datetime:
      rhs = dateutil.parser.parse(self.rhs)

    elif t is not str:
      rhs = t(self.rhs)

    return self.predicate(value, rhs)
