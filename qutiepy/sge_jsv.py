#!/usr/bin/env python
from __future__ import print_function

import sys
import operator
import optparse

class PasrseException(Exception):
  def __init__(self, message):
    self.message = message

class jsv_parser(object):
  PSUDO_PARAMS = ['CLIENT', 'CMDARGS', 'CMDNAME', 'CONTEXT', 'GROUP', 'JOB_ID', 'USER', 'VERSION']
  SPLIT_PARAMS = ['l_hard','l_soft', 'ac']

  def __init__(self, in_fd, out_fd, get_env=False):
    self.in_fd = in_fd
    self.out_fd = out_fd

    self.parameters = {}
    self.updated_parameters = set()

  def dump(self, out):
    import pprint
    pprint.pprint(self.parameters, stream=out)
    out.flush()

  def __getitem__(self, key):
    return self.parameters.get(key, None)

  def __setitem__(self, key, value):
    if key in jsv_parser.PSUDO_PARAMS:
      raise KeyError('The parameter |{0}| is read only'.format(key))

    self.parameters[key] = value
    self.updated_parameters.add(key)

  def update_param(self, key, **kwargs):
    self.parameters.setdefault(key, dict()).update(kwargs)
    self.updated_parameters.add(key)

  def _read_next(self):
    l = self.in_fd.readline()
    if l[-1] != '\n':
      raise ParseException('Incomplete line!')

    return l.strip()

  def __getitem__(self, key):
    return self.parameters.get(key, None)

  def accept(self):
    self._send('RESULT STATE ACCEPT')

  def reject(self):
    self._send('RESULT STATE REJECT')

  def correct_settings(self):
    for key in self.updated_parameters:
      value = self.parameters[key]

      if type(value) is dict:
        value = ','.join(map(lambda kv: '='.join(kv), value.iteritems()))

      self._send('PARAM {0} {1}'.format(key, value))

    self._send('RESULT STATE CORRECT')

  def _send(self, message):
    print(message, file=self.out_fd)
    self.out_fd.flush()

  def __call__(self):
    while True:
      l = self._read_next()
      if l.startswith('PARAM'):
        self._parse_param(l)

      elif l == 'START':
        #self._send('SEND ENV', file=self.out_fd)
        self._send('STARTED')

      elif l == 'BEGIN':
        return True

      elif l == 'QUIT':
        return False

      else:
        raise ParseExeption('Unknown command found!\n\t{0}'.format(l))

  def _parse_param(self, l):
    cmd, param, setting = l.split(None, 2)
    if cmd != 'PARAM':
      raise ParseException('Expected PARAM here found |{0}|\n\t{1}'.format(cmd, l))

    if param in jsv_parser.SPLIT_PARAMS:
      setting = self._split_resources(setting)

    elif param == 'CMDARGS':
      self.parameters['CMDARGS'] = [None] * int(setting)
      return

    elif param.startswith('CMDARG'):
      self.parameters['CMDARGS'][int(param[6:])] = setting
      return

    elif param == 'VERSION' and setting != '1.0':
      raise ParseException('Unknown JSV protocol version |{0}|! Cowardly refusing to continue!')

    self.parameters[param] = setting

  def _split_resources(self, l):
    return dict(map(operator.methodcaller('split', '=', 1), l.split(',')))

TEST_CASE = '''\
START
PARAM VERSION 1.0
PARAM CONTEXT client
PARAM CLIENT drmaa
PARAM USER clcuser
PARAM GROUP staff
PARAM CMDNAME /sge_root/examples/jobs/sleeper.sh
PARAM CMDARGS 1
PARAM CMDARG0 12
PARAM l_hard a=1,b=5
PARAM l_soft q=all.q
PARAM M user@hostname
PARAM N Sleeper
PARAM o /dev/null
PARAM pe_name pe1
PARAM pe_min 3
PARAM pe_max 3
PARAM S /bin/sh
BEGIN
'''

if __name__ == '__main__':
  parser = optparse.OptionParser()
  parser.add_option('-t', '--test', dest='test_run', default=False, action='store_true',
    help='Run as a test submission rather than a real run')
  parser.add_option('-l', '--log', dest='log_file', default=None, action='store',
    help='Store jsv actions to the given log file')
  options, args = parser.parse_args()

  if not options.test_run:
    settings = jsv_parser(sys.stdin, sys.stdout)

  else:
    import cStringIO
    settings = jsv_parser(cStringIO.StringIO(TEST_CASE), sys.stdout)

  try:
    settings()
    algo_name = settings['N']
    if algo_name != 'sleeper.sh':
      settings.accept()
      sys.exit(0)

    settings['pe_name'] = 'smp'
    settings['pe_min'] = '12'
    settings['pe_max'] = '16'
    settings['q_hard'] = 'all.q'

    if options.log_file:
      with open(options.log_file, 'a') as log:
        settings.dump(log)

    settings.correct_settings()
    sys.exit(0)

  except Exception as ex:
    if options.log_file:
      with open(options.log_file, 'a') as log:
        print('Exception |{0}|'.format(ex), file=log)

    settings.accept()
    sys.exit(1)
