from __future__ import print_function
from __future__ import division

"""Parses the sge accounting log"""

import operator
import itertools
import csv
import collections
import datetime
import decimal
import warnings

import sge_common

def sge_datetime(time):
    return datetime.datetime.fromtimestamp(int(time))

def sge_maxvmem(mem):
    # In the accounting file the memory has a decimal in it for some reason...
    int_part, dec_part = mem.split('.', 1)
    if dec_part.strip('.0') != "":
      warnings.warn('maxvem found with non-zero mantissa please report to qutiepy devs')

    return int(int_part)

def uge_datetime(time):
    ms_val = int(time)
    return datetime.datetime.fromtimestamp(ms_val // 1000).replace(microsecond=(ms_val%1000) * 1000)

class AccountingRow(collections.Mapping):
  _fields = []

  @classmethod
  def _addfield(cls, field_desc):
    cls._fields.append(field_desc)

  @classmethod
  def fields(cls):
    """Return a sorted set of AccountingField names"""
    return sorted(
      map(operator.itemgetter(0),
        itertools.ifilter(lambda member_item: type(member_item[1]) is AccountingField,
          cls.__dict__.iteritems())))

  def __init__(self, row):
    self._rawrow = row
    self._memorizedrow = dict()

  def __len__(self):
    return len(type(self)._fields)

  def __getitem__(self, key):
      try:
          if type(key) is int:
              return self._rawrow[key]

          elif type(key) is str:
              val = self._memorizedrow.get(key)
              if val:
                return val

              return self.__getattribute__(key)

          else:
              raise TypeError("key must be an int or a string")

      except AttributeError as ex:
          raise IndexError("key %s is not an available field." % key, ex)

  def __iter__(self):
    return itertools.ifilter(lambda member: type(member) is AccountingField, self.__dict__)

class AccountingField(object):
  def __init__(self, pos=None, converter=int, doc=None):
    self.pos = pos
    self.converter = converter
    self.doc = doc

  def __call__(self, fget):
    self.converter = fget
    return self

  def __set__(self, obj, value):
    raise AttributeError("Accounting Fields are read only")

  def __get__(self, obj, objtype=None):
    # Set up the field in the row object
    if obj is None:
      objtype._addfield(self)
      return self

    if self.pos is None:
      if self.converter:
        return self.converter(obj)

      raise AttributeError('unreadable attribute')

    val = obj._rawrow[self.pos]

    if self.converter is not None:
      try:
        val = self.converter(val)
      except ValueError as ex:
        raise ValueError("Error with pos {0} caused by {1}".format(self.pos, ex))

    return obj._memorizedrow.setdefault(self.pos, val)

class GEFailedField(AccountingField):
  SGE_FAILED_MESSAGES = collections.defaultdict(
      lambda: "Unknown error code",
      {
          0 : "Successful",
          1 : "assumedly before job: Failed early in execd",
          3 : "Before writing config: failed before execd set up local spool",
          4 : "Before writing PID: sheperd failed to record it's pid",
          5 : "On reading config file",
          6 : "Setting processor set",
          7 : "Before prolog",
          8 : "In prolog",
          9 : "Before pestart: Failed before starting parallel environment",
          10 : "In pestart: Failed while starting parallel environment",
          11 : "Before Job: failed in shepard before starting job",
          12 : "Before pestop: ran, but failed before calling PE stop",
          13 : "In pestop",
          14 : "Before epilog: ran, but failed before calling epilog script ",
          15 : "In epilog: ran, but failed in epilog script",
          16 : "Releasing processor set: ran, but processor set could not be released",
          17 : "Through signal: Job killed by signal (possibly qdel)",
          18 : "Shepard returned error",
          19 : "Shepard failed while writing reports",
          20 : "Shepard encountered a problem",
          21 : "qmaster asked about an unknown job",
          24 : "Migrating: job ran, will be migrated",
          25 : "Rescheduling: job ran, will be rescheduled",
          26 : "Opening output file: Failed to open stderr or stdout file",
          27 : "Failed to find requested shell",
          28 : "Failed changing to working directory",
          29 : "Failed setting up AFS Security",
          36 : "Failed because of configured remote startup daemon",
          37 : "Ran but stopped due to exceeding run time limit (h_rt, h_cpu, or h_vmem)",
          38 : "Failed adding supplementary gid to job",
          100: "Assumedly after job"
      }
  )

  def __init__(self, err):
    self.errno = int(err)

  def __str__(self):
    return str(self.errno)

  def coerce(self, other):
    if type(other) is GEFailedField:
      return other.errno

    if type(other) is int:
      return other

    raise NotImplemented()

  def __lt__(self, other):
    return self.errno < self.coerce(other)

  def __le__(self, other):
    return self.errno <= self.coerce(other)

  def __gt__(self, other):
    return self.errno > self.coerce(other)

  def __ge__(self, other):
    return self.errno >= self.coerce(other)

  def __eq__(self, other):
    return self.errno == self.coerce(other)

  def __ne__(self, other):
    return self.errno != self.coerce(other)

  @property
  def message(self):
    return GEFailedField.SGE_FAILED_MESSAGES[self.errno]

  @property
  def full(self):
    return "%s%s" % (self.errno, (" : " + self.message) if self.errno != 0 else "")

class SGEAccountingRow(AccountingRow):
    qname = AccountingField(0, converter=str)
    hostname = AccountingField(1, str)
    group = AccountingField(2, str)
    owner = AccountingField(3, str)
    job_name = AccountingField(4, str)
    job_number = AccountingField(5)
    account = AccountingField(6, str)
    priority = AccountingField(7)
    submission_time = AccountingField(8, sge_datetime)
    start_time = AccountingField(9, sge_datetime)
    end_time = AccountingField(10, sge_datetime)
    failed = AccountingField(11, GEFailedField)
    exit_status = AccountingField(12)
    ru_wallclock = AccountingField(13, float)
    ru_utime = AccountingField(14, float)
    ru_stime = AccountingField(15, float)
    ru_maxrss = AccountingField(16, decimal.Decimal)
    ru_ixrss = AccountingField(17)
    ru_ismrss = AccountingField(18)
    ru_idrss = AccountingField(19)
    ru_isrss = AccountingField(20)
    ru_minflt = AccountingField(21)
    ru_majflt = AccountingField(22)
    ru_nswap = AccountingField(23)
    ru_inblock = AccountingField(24,float)
    ru_oublock = AccountingField(25)
    ru_msgsnd = AccountingField(26)
    ru_msgrcv = AccountingField(27)
    ru_nsignals = AccountingField(28)
    ru_nvcsw = AccountingField(29)
    ru_nivcsw = AccountingField(30)
    project = AccountingField(31, str)
    department = AccountingField(32, str)
    granted_pe = AccountingField(33, str)
    slots = AccountingField(34, int)
    task_number = AccountingField(35, int)
    cpu = AccountingField(36, float)
    mem = AccountingField(37, decimal.Decimal)
    io = AccountingField(38, decimal.Decimal)
    category = AccountingField(39, str)
    iow = AccountingField(40, float)
    pe_taskid = AccountingField(41, str)
    maxvmem = AccountingField(42, float)
    arid = AccountingField(43)
    ar_submission_time = AccountingField(44, sge_datetime)

    @AccountingField()
    def waiting_time(self):
      if self.submission_time < self.start_time:
        return self.start_time - self.submission_time

      return datetime.timedelta(0)

    @AccountingField()
    def waiting_time_sec(self):
      td = self.waiting_time
      return ((td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6)

    @AccountingField()
    def aggregate_time(self):
        if self.submission_time < self.end_time:
            return self.end_time - self.submission_time

        return datetime.timedelta(0)

    @AccountingField()
    def aggregate_time_sec(self):
      td = self.aggregate_time
      return ((td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6)

class UGEAccountingRow(SGEAccountingRow):
    submission_time = AccountingField(8, uge_datetime)
    start_time = AccountingField(9, uge_datetime)
    end_time = AccountingField(10, uge_datetime)
    maxvmem = AccountingField(42, float)
    ar_submission_time = AccountingField(44, uge_datetime)

    @AccountingField(45)
    def cwd(self, val):
      return val.replace('\xFF', ':')

    @AccountingField(46)
    def submit_cmd(self, val):
      return val.replace('\xFF', ':')

class SGEAccountingFile(object):
    """Handles parsing the sge accounting log"""

    class Dialect(csv.Dialect):
        delimiter = ':'
        doublequote = False
        escapechar = None
        quoting = csv.QUOTE_NONE
        strict = False
        lineterminator='\n'

    def __init__(self, fd=None):
        if fd is None:
            paths = sge_common.Paths()
            self.accounting_file = file(paths.accouting_file, 'rb')

        elif issubclass(fd, collections.Iterable):
          self.accounting_file = fd

        else:
          raise TypeError('fd must be either None or a file like '
              'object that yields accounting file lines')

    def __iter__(self):
        for record in self.build_reader(self.accounting_file):
            if len(record) > 45:
                yield UGEAccountingRow(record)
            else:
                yield SGEAccountingRow(record)

    @staticmethod
    def build_reader(fd):
        return csv.reader(
            itertools.ifilterfalse(
                lambda line: line.startswith('#'),
                fd),
            dialect=SGEAccountingFile.Dialect())

# vim: set shiftwidth=2 tabstop=2
