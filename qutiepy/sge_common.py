"""Some common things for sge"""

import os.path
import os

class Paths(object):
    def __init__(self, env=None):
        if not env:
            self.env = os.environ.copy()
        else:
            self.env = env

    @property
    def root(self):
        try:
            return self.env['SGE_ROOT']
        except KeyError:
            raise RuntimeError('SGE_ROOT variable is not set. Did you run on a submission host?')

    @root.setter
    def root(self, value):
        self.env['SGE_ROOT'] = value

    @property
    def cell(self):
        try:
            return self.env['SGE_CELL']
        except KeyError:
            raise RuntimeError('SGE_CELL environment variabe is not set. Did you run on a submission host?')

    @cell.setter
    def cell(self, value):
        self.env['SGE_CELL'] = value

    @property
    def cell_dir(self):
        return os.path.join(self.root, self.cell)

    @property
    def accouting_file(self):
        return os.path.join(self.cell_dir, 'common', 'accounting')
