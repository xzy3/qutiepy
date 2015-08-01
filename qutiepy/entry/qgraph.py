#!/usr/bin/env python
from __future__ import print_function

import collections
import itertools
import csv
import bisect

import argparse
import fileinput

import qutiepy.sge_accounting

class histogram(object):
    def __init__(self, *bins):
        self.bins = sorted(tuple(bins))
        self.histo = collections.defaultdict(int)

    def count(self, key, delta):
        self.histo[bisect.bisect_right(self.bins, key)] += delta

    def __iter__(self):
        return itertools.imap(lambda k: self.histo[k],
            self.bins)

    def get_headers(self):
        sec = itertools.tee(self.bins)
        next(sec)
        return tuple(
            itertools.imap("to".join,
                itertools.izip_longest(self.bins, sec, fillvalue='+')))

class runtime_rec(object):
    def __init__(self):
        self.job_count = 0

        self.successful_jobs = 0

        self.total_wallclock = 0
        self.max_wallclock = float('-inf')
        self.min_wallclock = float('inf')

        self.total_time = 0

        self.slots_histo = histogram(1, 2, 4, 8, 16, 32, 64, 128)
        self.runtime_histo = histogram(
            60 * 60 * 24, # one day
            60 * 60 * 24 * 7, # one week
            60 * 60 * 24 * 30.4166667 # average month
        )

        self.queue_histo = collections.defaultdict(int)

    @property
    def avg_runtime(self):
        return self.total_wallclock / float(self.successful_jobs)

    def __call__(self, row):
        self.job_count += 1
        compute_time = row.ru_utime + row.ru_stime
        self.total_time += compute_time

        self.slots_histo.count(row.slots, 1)
        self.queue_histo[row.qname] += 1

        if row.exit_status == 0:
            self.successful_jobs += 1

            self.total_wallclock += row.ru_wallclock
            self.max_wallclock = max(row.ru_wallclock, self.max_wallclock)
            self.min_wallclock = min(row.ru_wallclock, self.min_wallclock)
            self.runtime_histo.count(row.ru_wallclock, 1)

    @classmethod
    def header_row(cls):
        return (
            'job_count',
            'successful_jobs',
            'min_wallclock',
            'max_wallclock',
            'avg_runtime',
            'total_time'
        )

    def dump(self):
        return map(lambda name: getattr(self, name), type(self).header_row())

def main():
  try:
    parser = argparse.ArgumentParser()
    parser.add_argument('accounting_files', nargs='*', default=None,
      help='Additional accounting files to parse')
    args = parser.parse_args()

    account = qutiepy.sge_accounting.SGEAccountingFile()
    if args.accounting_files:
      account = itertools.chain(
        qutiepy.sge_accounting.SGEAccountingFile(
          fileinput.input(args.accounting_files, openhook=fileinput.hook_compressed)),
        account)

    rollup_dict_by_user = collections.defaultdict(float)
    rollup_dict_jobs_by_user = collections.defaultdict(int)

    rollup_dict_system_stats = collections.defaultdict(runtime_rec)
    for i,r in enumerate(account):
        if i % 1000000 == 0:
            print('\rprocessed {0}M records'.format( i // 1000000))

        rollup_dict_system_stats[ (r.start_time.month, r.start_time.year) ](r)

        # compute time by user
        rollup_dict_by_user[ (r.start_time.month, r.start_time.year, r.owner) ] += r.ru_utime + r.ru_stime

        # job count by user
        rollup_dict_jobs_by_user[ (r.start_time.month, r.start_time.year, r.owner) ] += 1

    # (12, 1969) is the key for dates that didn't parse. So remove that.
    rollup_dict_system_stats.pop((12, 1969), 1)
    rollup_dict_by_user.pop((12, 1969), 1)
    rollup_dict_jobs_by_user.pop((12, 1969), 1)

    # total successful jobs
    with open('cluster-system-stats.csv', 'wb+') as out_file:
        csv_writer = csv.writer(out_file, delimiter=',')

        csv_writer.writerow(tuple(itertools.chain(('month', 'year'), runtime_rec.header_row())))
        csv_writer.writerows(
          itertools.imap(lambda r: list(itertools.chain(r[0], r[1].dump())),
            rollup_dict_system_stats.iteritems()))

    # count of jobs per slots
    with open('cluster-slots-per-job.csv', 'wb+') as out_file:
        csv_writer = csv.writer(out_file, delimiter=',')

        csv_writer.writerow(tuple(itertools.chain(('month', 'year'), next(rollup_dict_system_stats.itervalues()).slots_histo.get_headers())))
        csv_writer.writerows(
          itertools.imap(lambda r: tuple(itertools.chain((r[0][0], r[0][1]), iter(r[1].slots_histo))),
              rollup_dict_system_stats.iteritems()))

    ## job count by queue
    with open('cluster-jobs-by-queue.csv', 'wb+') as out_file:
        csv_writer = csv.writer(out_file, delimiter=',')

        csv_writer.writerow(tuple(itertools.chain(('month', 'year'), next(rollup_dict_system_stats.itervalues()).queue_histo.get_headers())))
        csv_writer.writerows(
          itertools.imap(lambda r: tuple(itertools.chain((r[0][0], r[0][1]), iter(r[1].queue_histo))),
              rollup_dict_system_stats.iteritems()))

    # compute time by user
    with open('cluster-cpu-hours-by-user.csv', 'wb+') as out_file:
        csv_writer = csv.writer(out_file, delimiter=',')

        csv_writer.writerow(('month', 'year', 'user', 'cpu_time'))
        csv_writer.writerows(
            itertools.imap(lambda r: (r[0][0], r[0][1], r[0][2], r[1]),
                rollup_dict_by_user.iteritems()))


    # job count by user
    with open('cluster-cpu-hours-by-user.csv', 'wb+') as out_file:
        csv_writer = csv.writer(out_file, delimiter=',')

        csv_writer.writerow(('month', 'year', 'user', 'job count'))
        csv_writer.writerows(
            itertools.imap(lambda r: (r[0][0], r[0][1], r[0][2], r[1]),
                rollup_dict_jobs_by_user.iteritems()))

  except KeyboardInterrupt:
    pass

# vim: set shiftwidth=4 tabstop=4
