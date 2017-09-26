import os
import sys
from setuptools import setup, find_packages

# tell python to not write bytecode files
sys.dont_write_bytecode = True

# get the version out of the package itself
path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, "{}/lib".format(path))
from dart.agent import __version__  # noqa

setup(
    name='dart-agent',
    version=__version__,
    scripts=['bin/dart-agent'],
    package_dir={'': 'lib'},
    packages=find_packages(where='lib', exclude=('tests', 'tests.*')),
    include_package_data=True,
    setup_requires=('pytest-runner'),
    tests_require=('pytest-flake8', 'pytest-pep8', 'pytest-cov', 'pytest'),
)
