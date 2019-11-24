import sys
from setuptools import setup, find_namespace_packages


# tell python to not write bytecode files
sys.dont_write_bytecode = True

setup(
    name="dart-portal",
    version="3.4",
    author="Paul Lockaby",
    author_email="paul@paullockaby.com",
    license="Artistic-2.0",
    url="https://github.com/plockaby/dart",
    scripts=[],
    package_dir={"": "lib"},
    packages=find_namespace_packages(where="lib", include=["dart.*"], exclude=["test", "tests.*"]),
    include_package_data=True,
    python_requires=">=3.7",
    setup_requires=["pytest-runner"],
    tests_require=["pytest-flake8", "pytest"],
    install_requires=["flask", "gunicorn<20", "gevent", "flask-moment", "flask-caching", "requests", "pyyaml", "redis"],
    namespace_packages=["dart"],
)
