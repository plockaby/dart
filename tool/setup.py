import sys
from setuptools import setup, find_packages

# tell python to not write bytecode files
sys.dont_write_bytecode = True

setup(
    name='dart-tool',
    scripts=['bin/dart'],
    package_dir={'': 'lib'},
    packages=find_packages(where='lib', exclude=('tests', 'tests.*')),
    include_package_data=True,
    setup_requires=('pytest-runner'),
    tests_require=('pytest-flake8', 'pytest-pep8', 'pytest-cov', 'pytest'),
)
