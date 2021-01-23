#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""This module runs all command line arguments."""

__authors__ = ["Justin Furuness"]
__credits__ = ["Justin Furuness"]
__Lisence__ = "BSD"
__maintainer__ = "Justin Furuness"
__email__ = "jfuruness@gmail.com"
__status__ = "Development"

from argparse import ArgumentParser
import logging

from lib_utils import utils

from .speech_recognition_wrapper import Speech_Recognition_Wrapper


def main():
    """Does all the command line options available
    See top of file for in depth description"""

    parser = ArgumentParser(description="lib_speech_recognition_wrapper")

    for arg in ["run", "debug", "test"]:
        parser.add_argument(f"--{arg}", default=False, action='store_true')

    args = parser.parse_args()

    # Configure logging
    utils.config_logging(logging.DEBUG if args.debug else logging.INFO)

    if args.run:
        Speech_Recognition_Wrapper().run()
