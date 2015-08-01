#!/usr/bin/env python
from __future__ import print_function
from __future__ import division

"""\
Top level qutiepy command and entry point. Loads sub-modules through package
inspection."""

import pkg_resources
import sys
import argparse
import collections
import fileinput
import itertools

from ..commands import *
from ..sge_accounting import SGEAccountingFile

# borrowed this class from the argparse backport and hacked it up
class _qutiepy_SubParsersAction(argparse.Action):
  """Handle the strange way the qutiepy parses the command line"""

  class _ChoicesPseudoAction(argparse.Action):
    def __init__(self, name, aliases, help):
      metavar = dest = name

      if aliases:
        metavar += ' (%s)' % ', '.join(aliases)

      sup = super(_qutiepy_SubParsersAction._ChoicesPseudoAction, self)
      sup.__init__(option_strings=[], dest=dest, help=help,
        metavar=metavar)

  def __init__(self, option_strings, prog, parser_class, dest=argparse.SUPPRESS, help=None, metavar=None):
    self._prog_prefix = prog
    self._parser_class = parser_class
    self._name_parser_map = {}
    self._choices_actions = []

    super(_qutiepy_SubParsersAction, self).__init__(
      option_strings=option_strings,
      dest=dest,
      nargs=argparse.PARSER,
      choices=self._name_parser_map,
      help=help,
      metavar=metavar)

  def add_parser(self, name, **kwargs):
    # set prog from the existing prefix
    if kwargs.get('prog') is None:
      kwargs['prog'] = '%s %s' % (self._prog_prefix, name)

    aliases = kwargs.pop('aliases', ())

    # create a pseudo-action to hold the choice help
    if 'help' in kwargs:
      help = kwargs.pop('help')
      choice_action = self._ChoicesPseudoAction(name, aliases, help)
      self._choices_actions.append(choice_action)

    # create the parser and add it to the map
    parser = self._parser_class(**kwargs)
    self._name_parser_map[name] = parser

    # make parser available under aliases also
    for alias in aliases:
      self._name_parser_map[alias] = parser

    return parser

  def _get_subactions(self):
    return self._choices_actions

  def __call__(self, parser, namespace, values, option_string=None):
    subcommands = []
    setattr(namespace, self.dest, subcommands)

    i = 0
    while i < len(values):
      parser_name = values[i]

      j = i + 1
      while j < len(values) and values[j] not in self._name_parser_map.keys():
        j += 1

      arg_strings = values[i+1:j]
      i += j

      sub_namespace = argparse.Namespace()
      subcommands.append(sub_namespace)

      # select the parser
      try:
        parser = self._name_parser_map[parser_name]
      except KeyError:
        tup = parser_name, ', '.join(self._name_parser_map)
        msg = _('unknown parser %r (choices: %s)' % tup)
        raise ArgumentError(self, msg)

      # parse all the remaining options into the namespace
      # store any unrecognized options on the object, so that the top
      # level parser can decide what to do with them

      sub_namespace, arg_strings = parser.parse_known_args(arg_strings, sub_namespace)
      if arg_strings:
        vars(namespace).setdefault(argparse._UNRECOGNIZED_ARGS_ATTR, [])
        getattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR).extend(arg_strings)

def main():
  parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
  parser.add_argument('-v', '--version', action='version',
    version='%(prog)s {0}'.format(pkg_resources.require("qutiepy")[0].version))
  # using nargs=1 in appends cause argparse to create a list of lists
  parser.add_argument('-i', '--include', action='append', default=None, dest='extra_accounting_files', type=str,
    metavar='ACCOUNTING FILE', help='Include additonal source files in the record stream before the standard stream.')
  parser.add_argument('-s', '--skip-accounting', action='store_true', default=False, dest='skip_system_account_file',
    help='Skip reading of the live accounting file [Default: %(default)s]')

  subparsers = parser.add_subparsers(action=_qutiepy_SubParsersAction, dest='subcommands',
    title="Pipeline components",
    description='Accounting record are read and processed by each sub-component in order.')

  for command in Command.Command.__subclasses__():
    c = command()
    c.register_self(subparsers)

  args = parser.parse_args()

  record_streams = []
  if args.extra_accounting_files:
     record_streams.append(SGEAccountingFile(
        fileinput.input(args.extra_accounting_files, openhook=fileinput.hook_compressed)))

  if not args.skip_system_account_file:
    record_streams.append(SGEAccountingFile())

  if not record_streams:
    parser.error('No source files. System accounting file skipped and no others included.')

  pipeline = itertools.chain(*record_streams)
  for stage in args.subcommands:
    pipeline = stage.func(stage, pipeline)

  try:
    collections.deque(pipeline, 0)

  except IOError as ioex:
    if ioex.filename:
      parser.error("Error reading '{0.filename}'. {0.strerror} [Errno {0.errno}]".format(ioex))
    else:
      parser.error(ioex)

  except KeyboardInterrupt:
    sys.exit(1)
