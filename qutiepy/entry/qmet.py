#!/usr/bin/env python
from __future__ import print_function

"""Parses the sge accounting log"""

import pkg_resources

import sys
import re
import operator
import optparse
import itertools
import functools
import string
import dateutil, dateutil.parser

import qutiepy.sge_accounting
import qutiepy.filter.BaseTypes
import qutiepy.filter.Parser

class SGEOption(optparse.Option):
    pass

class SGEFilterOption(SGEOption):
    def take_action(self, action, dest, opt, value, values, parser):
        filter_stack = values.ensure_value('filter', qutiepy.filter.FilterStack())

        self.filter_action(filter_stack, action, dest, opt, value, values, parser)

class SGEAndOption(SGEFilterOption):
    def __init__(self):
        SGEFilterOption.__init__(self, '--and', action='store_true',
            help='Group actions together using and')

    def filter_action(self, filter_stack, actio, dest, opt, value, values, parser):
        filter_stack.push(qutiepy.filter.AndFilter())

class SGEOrOption(SGEFilterOption):
    def __init__(self):
        SGEFilterOption.__init__(self, '--or', metavar=None, action='store_true',
            help='Group actions together using or')

    def filter_action(self, filter_stack, actio, dest, opt, value, values, parser):
        filter_stack.push(qutiepy.filter.OrFilter())

class SGENotOption(SGEFilterOption):
    def __init__(self):
        SGEFilterOption.__init__(self, '--not', metavar=None, action='store_true',
            help='Group actions together using not')

    def filter_action(self, filter_stack, actio, dest, opt, value, values, parser):
        filter_stack.push(qutiepy.filter.NotFilter())

class SGEGroupEndOption(SGEFilterOption):
    def __init__(self):
        SGEFilterOption.__init__(self, '--ge', metavar=None, action='store_true',
            help='End a grouping of actions')

    def filter_action(self, filter_stack, actio, dest, opt, value, values, parser):
        filter_stack.pop()

class SGEGlobOption(SGEFilterOption):
    def __init__(self, long, field_name):
        SGEFilterOption.__init__(self, long,
            help= 'glob to filter by %s' % field_name)
        self.field_name = field_name

    def filter_action(self, filter_stack, action, dest, opt, value, values, parser):
        filter_stack.add_filter(qutiepy.filter.GlobFilter(self.field_name, value))

class SGEAfterOption(SGEFilterOption):
    def __init__(self, long, field_name):
        SGEFilterOption.__init__(self, long, nargs=1,
            help='filter to match records after a specific time')
        self.field_name = field_name

    def filter_action(self, filter_stack, action, dest, opt, value, values, parser):
        ti = dateutil.parser.parse(value)
        filter_stack.add_filter(
            qutiepy.filter.PredicateFilter(self.field_name,
                functools.partial(operator.le, ti)))

class SGEBeforeOption(SGEFilterOption):
    def __init__(self, long, field_name):
        SGEFilterOption.__init__(self, long, nargs=1,
            help='filter to match records before a specific time')
        self.field_name = field_name

    def filter_action(self, filter_stack, action, dest, opt, value, values, parser):
        ti = dateutil.parser.parse(value)
        filter_stack.add_filter(
           qutiepy.filter.PredicateFilter(self.field_name,
                functools.partial(operator.ge, ti)))

class SGERangeOption(SGEFilterOption):
    PATTERN = re.compile(r"""
        \s*
        (?:
            (?:(?P<begin>[0-9]+)\s*[.]{2}\s*(?P<end>[0-9]+))
            |
            (?:(?P<min>[0-9]+)\s*[.]{2})
            |
            (?:[.]{2}\s*(?P<max>[0-9]+))
            |
            (?P<val>[0-9]+)
        )
        \s*,?
        """,
        re.VERBOSE)

    def __init__(self, long, field_name):
        SGEFilterOption.__init__(self, long, nargs=0,
            help='specify a list of value ranges for %s' % field_name)
        self.field_name = field_name

    def floatable(str):
        try:
            float(str)
            return True
        except ValueError:
            return False

    def filter_action(self, filter_stack, action, dest, opt, value, values, parser):
        # grab all of the values up to the next option
        args = []
        count = 0
        for arg in parser.rargs:
            if arg[:2] == "--" and len(arg) > 2:
                break

            if arg[:1] == '-' and len(arg) > 1 and not floatable(arg):
                break

            count += 1
            args.append(arg)

        del parser.rargs[:count]

        filters = qutiepy.filter.PredicateFilter(self.field_name)
        for match in SGERangeOption.PATTERN.finditer(''.join(args)):
            d = match.groupdict()

            val = d['val']
            if val:
                filters.append(functools.partial(operator.eq, float(val)))
                continue

            val = d['min']
            if val:
                filters.append(functools.partial(operator.le, float(val)))
                continue

            val = d['max']
            if val:
                filters.append(functools.partial(operator.ge, float(val)))
                continue

            else:
                begin = d['begin']
                end = d['end']

                filters.append(
                        functools.partial(lambda begin,end,val: begin <= val and val <= end, float(begin), float(end)))

        if len(filters) > 0:
            filter_stack.add_filter(filters)

DEFAULT_TEMPLATE = """\
==============================================================
qname           $qname
hostname        $hostname
group           $group
owner           $owner
project         $project
department      $department
jobname         $job_name
jobnumber       $job_number
taskid          $task_number
pe_taskid       $pe_taskid
account         $account
priority        $priority
qsub_time       $submission_time
start_time      $start_time
end_time        $end_time
waiting_time    $waiting_time
aggregate_time  $aggregate_time
granted_pe      $granted_pe
slots           $slots
failed          $failed_with_message
exit_status     $exit_status
ru_wallclock    $ru_wallclock
ru_utime        $ru_utime
ru_stime        $ru_stime
ru_maxrss       $ru_maxrss
ru_ixrss        $ru_ixrss
ru_ismrss       $ru_ismrss
ru_idrss        $ru_idrss
ru_isrss        $ru_isrss
ru_minflt       $ru_minflt
ru_majflt       $ru_majflt
ru_nswap        $ru_nswap
ru_inblock      $ru_inblock
ru_oublock      $ru_oublock
ru_msgsnd       $ru_msgsnd
ru_msgrcv       $ru_msgrcv
ru_nsignals     $ru_nsignals
ru_nvcsw        $ru_nvcsw
ru_nivcsw       $ru_nivcsw
cpu             $cpu
mem             $mem
io              $io
iow             $iow
maxvmem         $maxvmem
arid            $arid
"""

def action_firstMatch(templ, records):
    r = next(records, False)

    if r:
        print(templ.substitute(r))
        return True

    return False

def action_formatAll(templ, records):
    matched = 0

    for r in records:
        print(templ.substitute(r))
        matched += 1

    if matched > 0:
        print("Matched %s records" % matched, file=sys.stderr)
        return True

    return False

def action_lastMatch(templ, records):
    matched = None
    for r in records:
        matched = r

    if matched:
        print(templ.substitute(r))
        return True

    return False

def main():
    parser = optparse.OptionParser(option_class=SGEOption,
        usage="usage: %prog [options]", version='%%prog %s' % pkg_resources.require("qutiepy")[0].version)

    parser.add_option('--first-match', action='store_const', dest='action', const=action_firstMatch,
        help='Only display the first record which matches')
    parser.add_option('--last-match', action='store_const', dest='action', const=action_lastMatch,
        help='Only display the last record which matches')
    parser.add_option('--dry-run', action='store_true', default=False, dest='dry_run',
        help='Only helpful for debugging, just prepairs to walk the file but never actually does anything')

    group = optparse.OptionGroup(parser, "Grouping Predicates",
        "Filter rows by field values. Filters are grouped using prefix notation, "
        "by default a row must match all filters to be printed.")

    group.add_option(SGEAndOption())
    group.add_option(SGEOrOption())
    group.add_option(SGENotOption())
    group.add_option(SGEGroupEndOption())
    parser.add_option_group(group)

    group = optparse.OptionGroup(parser, 'Time Filters',
        "Filter on time based fields by giving a date")

    group.add_option(SGEBeforeOption('--submitted-before', 'submission_time'))
    group.add_option(SGEAfterOption('--submitted-after', 'submission_time'))
    group.add_option(SGEBeforeOption('--started-before', 'start_time'))
    group.add_option(SGEAfterOption('--started-after', 'start_time'))
    group.add_option(SGEBeforeOption('--ended-before', 'end_time'))
    group.add_option(SGEAfterOption('--ended-after', 'end_time'))
    parser.add_option_group(group)

    group = optparse.OptionGroup(parser, 'Glob Filters',
        "Match fields using unix style globing")

    group.add_option(SGEGlobOption('--queue', 'qname'))
    group.add_option(SGEGlobOption('--host', 'hostname'))
    group.add_option(SGEGlobOption('--group', 'group'))
    group.add_option(SGEGlobOption('--owner', 'owner'))
    group.add_option(SGEGlobOption('--job', 'job_name'))
    group.add_option(SGEGlobOption('--granted-pe', 'granted_pe'))
    parser.add_option_group(group)

    group = optparse.OptionGroup(parser, 'Range Filters',
        "Filter field by specifiying ranges of numeric values. "
        "...NUM is less than or equal to NUM, NUM is equal to a number, "
        "NUM..NUM is every value between the two numbers including the endpoints, "
        "NUM... is every value greater than or equal to NUM")

    group.add_option(SGERangeOption('--job-number', 'job_number'))
    group.add_option(SGERangeOption('--exit-status', 'exit_status'))
    group.add_option(SGERangeOption('--slots', 'slots'))
    parser.add_option_group(group)

    group = optparse.OptionGroup(parser, "format", ""
            "available field names: " +
            ', '.join(qutiepy.sge_accounting.SGEAccountingRow.fields()))

    group.add_option('--header', action='store_true', dest='print_header', default=False,
        help="Print the format string out before the first record as a header")
    group.add_option('--format', action='store', default=DEFAULT_TEMPLATE, dest='output_template',
        help="Format the output by using template strings. $$ will be replaced by a $. "
            "$var_name or ${var_name} will be replaced by the value from matched records.")
    group.add_option('--filter', action='store', default=None, dest='str_filter')

    parser.add_option_group(group)
    (options, args) = parser.parse_args()

    if options.dry_run:
        print('This is a test it was only a test.')
        sys.exit(0)

    account = qutiepy.sge_accounting.SGEAccountingFile()


    str_filter = getattr(options, 'str_filter', None)
    if str_filter:
      p = qutiepy.filter.Parser.Parser()
      filter = p.parse(str_filter)
    else:
      filter = getattr(options, 'filter', None)

    if filter:
        records = itertools.ifilter(filter, account)
    else:
        records = iter(account)

    try:
        templ = string.Template(options.output_template)

        if options.print_header:
          print(options.output_template)

        action = action_formatAll
        if options.action:
            action = options.action

        if action(templ, records):
            sys.exit(0)

        else:
            print('No matching records', file=sys.stderr)
            sys.exit(1)

    except IndexError as ex:
        print('Malformed format option', ex[0], file=sys.stderr)
        sys.exit(2)

    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
  main()
