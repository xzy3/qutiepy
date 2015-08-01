from __future__ import print_function

# filter {Conjunction}|{Compairson}
# Conjunctions:
# - and (and {filter} )
# - or (or {filter} )
# - not (not {filter} )
# Comparison:
# - Format ({field name} {op} {value})
# - Numeric/Date ops: <, >, =, !=, <=, >=
# - String ops: = (exact equals), ~= /{python regex}/, *= {glob}

import qutiepy.filter.BaseTypes as BaseTypes

import sys
if sys.version_info < (2, 7):
  import ordereddict
else:
  import collections as ordereddict

import argparse
import functools
import operator
import string
import re

class Context(object):
  def __init__(self, text):
    self.text = text.strip()
    self.pos = 0

  @property
  def current(self):
    return self.text[self.pos:]

  @property
  def done(self):
    return self.pos == len(self.text)

  def lstrip(self):
    while not self.done and self.text[self.pos] in string.whitespace:
      self.pos += 1

class ParseError(Exception):
  pass

def _handle_simple_value(context):
  curr = context.current
  i = 0
  while curr[i] != ')':
    i += 1

  context.pos += i
  return curr[:i]

def _handle_predicate_value(op, context, field):
  const = _handle_simple_value(context)
  return BaseTypes.ComparatorFilter(op, field, const)

def _handle_glob_value(context, field):
  value = _handle_simple_value(context)
  return BaseTypes.GlobFilter(field, value)

def _handle_regex_value(context, field):
  context.lstrip()
  curr = context.current

  # This is the trick used in vim the first non space caracter
  # encountered is counted as the pattern delimiter. We go until
  # we match a the caracter again. So the user can select a delimiter
  # that is not in the regex anywhere rather than dealing with metacharacter
  # madness.
  delim = curr[0]
  i = 1
  while curr[i] != delim:
    i += 1

  pattern = curr[1:i]

  j = i + 1
  flags = 0
  while curr[j] not in string.whitespace + ')':
    f = getattr(re, curr[j], None)
    if f is None:
      raise ParseError('Unknown flag regex flag {0} to parse filter at position {1}'.format(curr[j], context.pos))

    flags |= f
    j += 1

  context.pos += j
  context.lstrip()
  return BaseTypes.RegexFilter(field, pattern, flags)

class Parser(argparse.Action):
  AND_TOKEN = '(and'
  OR_TOKEN = '(or'
  NOT_TOKEN = '(not'

  OPERATOR_TOKENS = ordereddict.OrderedDict([
    ('=',  functools.partial(_handle_predicate_value, operator.eq)),
    ('<=', functools.partial(_handle_predicate_value, operator.le)),
    ('>=', functools.partial(_handle_predicate_value, operator.ge)),
    ('!=', functools.partial(_handle_predicate_value, operator.ne)),
    ('<',  functools.partial(_handle_predicate_value, operator.lt)),
    ('>',  functools.partial(_handle_predicate_value, operator.gt)),
    ('*=', _handle_glob_value),
    ('~=', _handle_regex_value)
  ])

  def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None, required=False, help=None, metavar=None):
    super(Parser, self).__init__(
      option_strings, dest, nargs,
      const, default, type,
      choices, required, help,
      metavar)

  def __call__(self, parser, namespace, value, option_string):
    assert(len(value) == 1)

    context = Context(value[0])
    setattr(namespace, self.dest, self._parse(context))

  def _parse(self, context):
      context.lstrip()

      if context.current.startswith(Parser.AND_TOKEN):
        filter = self._handle_and(context)

      elif context.current.startswith(Parser.OR_TOKEN):
        filter = self._handle_or(context)

      elif context.current.startswith(Parser.NOT_TOKEN):
        filter = self._handle_not(context)

      elif context.current.startswith('('):
        filter = self._handle_op(context)

      else:
        raise ParseError('Error unable to parse filter at position {0}: Expected a ('.format(context.pos))

      return filter

  def _handle_conjunction(self, context, conjunction):
    while True:
      context.lstrip()

      if context.current.startswith('('):
        conjunction.add_filter(self._parse(context))

      elif context.current.startswith(')'):
        context.pos += 1
        return conjunction

      else:
        raise ParseError('Error while parsing and at postiion {0}. Looking for a )'.format(context.pos))

  def _handle_and(self, context):
    context.pos += len(Parser.AND_TOKEN)
    return self._handle_conjunction(context, BaseTypes.AndFilter())

  def _handle_or(self, context):
    context.pos += len(Parser.OR_TOKEN)
    return self._handle_conjunction(context, BaseTypes.OrFilter())

  def _handle_not(self, context):
    context.pos += len(Parser.NOT_TOKEN)
    return self._handle_conjunction(context, BaseTypes.NotFilter())

  def _handle_op(self, context):
    context.pos += 1
    context.lstrip()

    curr = context.current
    i = 0
    while curr[i] in string.ascii_lowercase or curr[i] == '_' or curr[i] == '.':
      i += 1

    field = curr[:i]
    context.pos += i
    context.lstrip()

    # We can't just look this up. The tokens have to be checked in order so that
    # the correct one is selected.
    value_parser = None
    for token,op in Parser.OPERATOR_TOKENS.iteritems():
      if context.current.startswith(token):
        context.pos += len(token)
        value_parser = op

    if not value_parser:
      raise ParseError('Error while parsing operator at position {0}. Looking for a relational operator.'.format(context.pos))

    predicate = value_parser(context, field)

    if not context.current.startswith(')'):
        raise ParseError('Error while parsing operator at postiion {0}. Looking for a )'.format(context.pos))

    context.pos += 1
    return predicate
