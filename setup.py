import codecs
import os
import sys

from setuptools import setup


here = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(here, 'homeslice', '__version__.py')) as f:
    exec(f.read(), about)

with codecs.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    readme = f.read()

with codecs.open(os.path.join(here, 'HISTORY.txt'), encoding='utf-8') as f:
    history = f.read()

long_description = readme + '\n\n' + history


required = [
    'click',
    'click_completion',
    'click-log',
    'crayons',
]

if sys.version_info < (2, 7):
    required.append('pathlib')


setup(
    name='homeslice',
    version=about['__version__'],
    description='dotfiles and :pizza: management',
    long_description=long_description,
    url='https://github.com/jefftriplett/homeslice',
    author='Jeff Triplett',
    author_email='jeff.triplett@gmail.com',
    packages=[
        'homeslice',
        'homeslice.commands',
    ],
    entry_points={
        'console_scripts': [
            'homeslice=homeslice:cli'
        ]
    },
    install_requires=required,
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Systems Administration',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],
)
