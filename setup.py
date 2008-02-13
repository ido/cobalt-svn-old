#!/usr/bin/env python

from distutils.core import setup
from glob import glob

setup(name="Cobalt",
      version="0.98.0pre3",
      description="Cobalt Resource Manager",
      author="Cobalt Team",
      author_email="cobalt@mcs.anl.gov",
      packages=["Cobalt", "Cobalt.Components"],
      package_dir = {'Cobalt': 'src/lib'},
      scripts = glob('src/clients/*.py') + glob('src/clients/POSIX/*.py'),
      data_files=[('share/man/man1', glob('man/*.1')),
                  ('share/man/man1', glob('POSIX/man/*.1')),
                  ('share/man/man8', glob('man/*.8'))]
      )

