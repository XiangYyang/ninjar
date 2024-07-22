# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) XiangYang, all rights reserved.

"""
Colorful write_ln
"""

from enum import Enum

import colorama
from colorama import Fore

global_level: int = 0


class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    MESSAGE = 2
    WARN = 3
    ERROR = 4
    FATAL = 5


class Color(Enum):
    RESET = 'reset'
    Red = 'red'
    Green = 'green'
    Yellow = 'yellow'
    Cyan = 'cyan'
    Gray = 'gray'
    White = 'white'
    LightBlue = 'lightblue'
    LightGreen = 'lightgreen'
    LightWhite = 'lightwhite'


def init() -> None:
    """
    Initialize colorful write_ln
    """
    colorama.init(autoreset=True)


def set_log_level(lev: LogLevel) -> None:
    """
    Set the minium log level
    """
    global global_level
    global_level = lev.value


def log_out(lev: LogLevel, content: str) -> None:
    """
    Write a log to the stdout
    """
    global global_level
    if lev.value < global_level:
        return

    color = {
        LogLevel.DEBUG: Color.Gray,
        LogLevel.INFO: Color.RESET,
        LogLevel.MESSAGE: Color.LightWhite,
        LogLevel.WARN: Color.Yellow,
        LogLevel.ERROR: Color.Red,
        LogLevel.FATAL: Color.Red,

    }

    colorful_print(color[lev], content)


def colorful_print(color_val: Color, content: str) -> None:
    """
    Print content with color
    """
    color = {
        Color.RESET: Fore.RESET,
        Color.Red: Fore.RED,
        Color.Green: Fore.GREEN,
        Color.White: Fore.WHITE,
        Color.Yellow: Fore.YELLOW,
        Color.Cyan: Fore.CYAN,
        Color.Gray: Fore.LIGHTBLACK_EX,
        Color.LightBlue: Fore.LIGHTBLUE_EX,
        Color.LightGreen: Fore.LIGHTGREEN_EX,
        Color.LightWhite: Fore.LIGHTWHITE_EX,
    }
    # print the content
    if color_val in color:
        print(color[color_val] + content + Fore.RESET)
    else:
        print(content)
