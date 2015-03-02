# -*- coding: utf-8 -*-
from setuptools import setup
try:
    from jupyterpip import cmdclass
except:
    import pip, importlib
    pip.main(['install', 'jupyter-pip']); cmdclass = importlib.import_module('jupyterpip').cmdclass

setup(
    name='jsobject',
    version='0.1',
    description='Exposes Javascript in Python (in the IPython notebook).',
    author='Jonathan Frederic',
    author_email='jon.freder@gmail.com',
    license='MIT License',
    url='https://github.com/jdfreder/ipython-jsobject',
    keywords='python ipython javascript jsobject pyjsobject front-end frontend window',
    classifiers=['Development Status :: 4 - Beta',
                 'Programming Language :: Python',
                 'License :: OSI Approved :: MIT License'],
    packages=['jsobject'],
    include_package_data=True,
    install_requires=["jupyter-pip"],
    cmdclass=cmdclass('jsobject', 'jsobject/backend_context'),
)
