import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()
CHANGES = open(os.path.join(here, 'CHANGES.md')).read()
LONG_DESCRIPTION = '\n\n'.join([README, CHANGES])

requires = [
    'pyramid',
    'SQLAlchemy',
    'transaction',
    'pyramid_tm',
    'pyramid_debugtoolbar',
    'six==1.10.0',
    'zope.sqlalchemy',
    'zope.interface',
    'waitress',
    'cryptography'
    ]

setup(name='pyramid_oauth2_provider',
      version='0.2',
      description='Oauth2 endpoint for pyramid applications',
      long_description=LONG_DESCRIPTION,
      classifiers=[
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Framework :: Pyramid',
          'Topic :: Internet :: WWW/HTTP',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
        ],
      author='Elliot Peele',
      author_email='elliot@bentlogic.net',
      url='http://github.com/elliotpeele/pyramid_oauth2_provider',
      keywords='web wsgi bfg pylons pyramid oauth2',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='pyramid_oauth2_provider',
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = pyramid_oauth2_provider:main
      [console_scripts]
      initialize_pyramid_oauth2_provider_db = pyramid_oauth2_provider.scripts.initializedb:main
      """,
      )

