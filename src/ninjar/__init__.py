# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) XiangYang, all rights reserved.

"""
Ninja build script generator.

`ninjar` is a low-level ninja generator for C/C++ project,
it provides global variables, command invoker, and the build rule abstraction.
"""

from . import shell
from .main import BuildScript, action, options, variables
from .ninja import NinjaGenerator, UnitStage, Query
from .writeln import log_out, LogLevel, colorful_print, Color


# alias: Query.from_glob
select = Query.from_glob


__all__ = [
    'BuildScript',
    'NinjaGenerator',
    'action',
    'options',
    'variables',
    'log_out',
    'LogLevel',
    'colorful_print',
    'Color',
    'shell',
    'select',
    'UnitStage',
]
