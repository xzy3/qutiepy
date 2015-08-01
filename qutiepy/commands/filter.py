from __future__ import print_function

import argparse
import itertools
import textwrap

import qutiepy.filter.Parser
import qutiepy.sge_accounting
from qutiepy.commands.Command import Command

COMMAND_DESCRIPTION = '''\
Filter allows records to be dropped from the stream based on expressive
rules with a lisp/ldap like syntax.

Available Variables:
{field_list}

 Variables that are complex python types can have any of their
 attributes accessed.

 See Also: The python documentation for the appropriate type(s)
  datetime.Datetime, decimal.Decimal, float, int, str

  e.x. (and(submission_time.hour >= 9)(submission_time.hour < 5))

Operators:
 Supported by All Types
 - (var = value) equality
 - (var != value) inequality
 Strings
 - (var ~= /<regex>/<flags>) Regex match using the Python re syntax
  See notes on regex below
 - (var *=<glob>)
 Numeric and Datetime Formats
 - (var < value) less than
 - (var > value) greater than
 - (var <= value) less than or equal
 - (var >= value) greater than or equal

 Regex Notes:
 - The pattern delimeter '/' can be any character. The first
   non-whitespace caracter is used as a delimiter, the pattern
   is consitered to continue until that character occurs again.
 - See the python re module for discussion of the syntax.
   [https://docs.python.org/2/library/re.html]
 - The flags section can be any of the one character flags listed in re.
   * 'I' Ignore Case [https://docs.python.org/2/library/re.html#re.I]
   * 'L' Locale [https://docs.python.org/2/library/re.html#re.L]
   * 'M' Multiline [https://docs.python.org/2/library/re.html#re.M]
   * 'S' Dot all [https://docs.python.org/2/library/re.html#re.S]
   * 'U' Unicode [https://docs.python.org/2/library/re.html#re.U]
   * 'X' Verbose [https://docs.python.org/2/library/re.html#re.X]

Conjunctions:
 - (and predicate [[predicate]...])
 - (or predicate [[predicate]...])
 - (not predicate [[predicate]...])
'''.format(
  field_list=textwrap.fill(
    ", ".join(qutiepy.sge_accounting.SGEAccountingRow.fields()),
    initial_indent=' '*2, subsequent_indent=' '*2
    )
)

def filter(namespace, filter_chain):
  filter = getattr(namespace, 'filter_str')
  return itertools.ifilter(filter, filter_chain)

class Filter(Command):
  @classmethod
  def register_self(self, argparsers):
    parser = argparsers.add_parser('filter',
      help='Drop records that do not match the given filter',
      description=COMMAND_DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)
    parser.set_defaults(func=filter)

    parser.add_argument('filter_str', nargs=1, action=qutiepy.filter.Parser.Parser)
