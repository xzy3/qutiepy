from __future__ import print_function

import argparse
import itertools
import string
import textwrap
import sys

import qutiepy.sge_accounting
from qutiepy.commands.Command import Command

class SI_Format(object):
  big_prefixes = ['', 'K', 'M', 'G', 'T', 'E', 'Z', 'Y']
  small_prefixes = ['m', 'u', 'n', 'p', 'f', 'a', 'z', 'y']

  def __init__(self, value):
    self.prefix = ''

    temp = abs(value)
    if temp != 0:
      if temp >= 1000:
        i = 0
        while temp >= 1000 and i < len(SI_Format.big_prefixes):
          i += 1
          temp /= 1000

        self.prefix = SI_Format.big_prefixes[i]

      elif temp < 0.01:
        i = 0
        while temp < 1 and i < len(SI_Format.small_prefixes):
          i += 1
          temp *= 1000

        self.prefix = SI_Format.small_prefixes[i]

    self.value = temp

  def __format__(self, spec):
    # limit to 4 sigfigs for general printing
    tmp_spec = spec
    if not spec:
      tmp_spec = '.4g'

    return '{0}{1}'.format(
      format(self.value, tmp_spec),
      self.prefix)

class _Formatter(string.Formatter):
  def __init__(self, format_str, stream):
    self.format_str = format_str

    self.stream = stream
    if type(stream) is list:
      self.stream = stream[-1]

  def __call__(self, row):
    print(self.vformat(self.format_str, row, row), file=self.stream)
    return row

  def convert_field(self, value, conversion):
    if conversion == 'h':
      return SI_Format(value)

    return super(_Formatter, self).convert_field(value, conversion)

def format_row(namespace, filter_chain):
  return itertools.imap(
    _Formatter(
      namespace.format_str,
      namespace.output),
    filter_chain)

COMMAND_DESCRIPTION = '''\
Format turns records from a stream into strings.

Available Variables:
{field_list}

 Variables that are complex python types can have any of their
 attributes accessed.

 See Also: The python documentation for the appropriate type(s)
  datetime.Datetime, decimal.Decimal, float, int, str

Formatting Language:
 This command uses the python PEP 3101 formatter machenery in the
 backend. See
  https://docs.python.org/2/library/string.html#format-string-syntax

 ex. qutiepy format '{{owner}},{{job_name}},{{slots}},{{waiting_time}}'

Custom Format Conversions:
 A special format conversion h(uman readable) has been added. This
 conversion type adds a metric prefix.

 i.e.  qutiepy format 'maxvmem {{maxvmem!h}}b'

 could print 'maxvmem 12.40Kb'.
'''.format(
  field_list=textwrap.fill(
    ", ".join(qutiepy.sge_accounting.SGEAccountingRow.fields()),
    initial_indent=' '*2, subsequent_indent=' '*2
    )
)


DEFAULT_FORMAT = '''\
==============================================================
qname           {qname}
hostname        {hostname}
group           {group}
owner           {owner}
project         {project}
department      {department}
jobname         {job_name}
jobnumber       {job_number}
taskid          {task_number}
pe_taskid       {pe_taskid}
account         {account}
priority        {priority}
qsub_time       {submission_time:%x %X}
start_time      {start_time:%x %X}
end_time        {end_time:%x %X}
waiting_time    {waiting_time}
aggregate_time  {aggregate_time}
granted_pe      {granted_pe}
slots           {slots}
failed          {failed.full}
exit_status     {exit_status}
ru_wallclock    {ru_wallclock}
ru_utime        {ru_utime}
ru_stime        {ru_stime}
ru_maxrss       {ru_maxrss!h}
ru_ixrss        {ru_ixrss!h}
ru_ismrss       {ru_ismrss!h}
ru_idrss        {ru_idrss!h}
ru_isrss        {ru_isrss!h}
ru_minflt       {ru_minflt}
ru_majflt       {ru_majflt}
ru_nswap        {ru_nswap}
ru_inblock      {ru_inblock}
ru_oublock      {ru_oublock}
ru_msgsnd       {ru_msgsnd}
ru_msgrcv       {ru_msgrcv}
ru_nsignals     {ru_nsignals}
ru_nvcsw        {ru_nvcsw}
ru_nivcsw       {ru_nivcsw}
cpu             {cpu}
mem             {mem}
io              {io}
iow             {iow}
maxvmem         {maxvmem!h}b
arid            {arid}
'''

class Format(Command):
  @classmethod
  def register_self(cls, argparsers):
    parser = argparsers.add_parser('format',
      help='Format records as strings',
      description=COMMAND_DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)
    parser.set_defaults(func=format_row)

    parser.add_argument('-o', '--output', nargs=1,
      default='-', type=argparse.FileType('w'), dest='output',
      help='Where the output will be written to [Default: stdout]')
    parser.add_argument('format_str', nargs='?', default=DEFAULT_FORMAT)
