from setuptools import setup, find_packages
import sys

setup(
    name='lib_speech_recognition_wrapper',
    packages=find_packages(),
    version='0.0.0',
    author='Justin Furuness',
    author_email='jfuruness@gmail.com',
    url='https://github.com/jfuruness/lib_speech_recognition_wrapper.git',
    download_url='https://github.com/jfuruness/lib_speech_recognition_wrapper.git',
    keywords=['Furuness', 'Assistant', 'voice', 'sphinx', 'voice assistant'],
    install_requires=[
        'pocketsphinx',
        'pyaudio',
    ],
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3'],
    entry_points={
        'console_scripts': 'lib_speech_recognition_wrapper = lib_speech_recognition_wrapper.__main__:main'},
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
)
