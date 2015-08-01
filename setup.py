#!/usr/bin/env python

from setuptools import setup, find_packages
import sys

install_requires = ['python-dateutil']
if sys.version_info < (2, 7):
  install_requires.append('argparse')
  install_requires.append('ordereddict')

setup(
  name='qutiepy',
  version='0.0.1dev',
  description='Utilties for gathering job statistics on Open/Univa Grid Engine clusters',
  author='Seth Sims',
  author_email='xzy3@users.noreply.github.com',
  install_requires=install_requires ,
  packages=find_packages(),
  entry_points={
    'console_scripts' : [
      'qmet = qutiepy.entry.qmet:main',
      'qgraph = qutiepy.entry.qgraph:main',
      'qutiepy = qutiepy.entry.qutiepy:main'
    ]
  },
  classifiers=[
    'Development Status :: 2 - Pre-Alpha',
    'Environment :: Console',
    'Intended Audience :: Information Technology',
    'Intended Audience :: Science/Research',
    'Intended Audience :: System Administrators',
    'Natural Language :: English',
    'Operating System :: Unix',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2 :: Only',
    'Topic :: System :: Systems Administration',
    'Topic :: Utilities'
  ]
)
