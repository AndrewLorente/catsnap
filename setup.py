#!/usr/bin/python

from setuptools import setup

setup(name="catsnap",
      version="1.0.0",
      description="catalog and store funny pictures",
      author="Andrew Lorente",
      author_email="andrew.lorente@gmail.com",
      url="github.com/andrewlorente/catsnap",
      packages=['catsnap',
                'catsnap.document',
                'catsnap.batch'],
      scripts=['scripts/catsnap'],
      install_requires=[
          "boto==2.5.2",
          "requests==0.13.2",

          "mock==1.0.0a2",
          "nose==1.1.2",
          ],
      )
