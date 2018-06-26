from setuptools import setup

setup(name='datalabframework',
      version='0.2.1',
      install_requires=[
        'requests',
        'pyyaml',
        'jupyter'
      ],
      description='Productivity Utilities for Data Science with Python Notebooks',
      url='http://github.com/natbusa/datalabframework',
      author='Natalino Busa',
      author_email='natalino.busa@gmail.com',
      license='MIT',
      packages=['datalabframework'],
      zip_safe=False)
