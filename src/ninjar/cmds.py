# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) XiangYang, all rights reserved.

"""
`ninja -t` commands
"""


import json
import os
import shlex
from typing import Callable, Dict, List

from .shell import execute, execute_with_stdout, save_content
from .writeln import LogLevel, log_out


def build() -> Callable[[Dict[str, str], Dict[str, str]], None]:
    """
    Run command `ninja`
    """
    def inner_fn(opts: Dict[str, str], args: Dict[str, str]) -> None:
        execute('ninja')

    return inner_fn


def clean() -> Callable[[Dict[str, str], Dict[str, str]], None]:
    """
    Run command `ninja -t clean`
    """
    def inner_fn(opts: Dict[str, str], args: Dict[str, str]) -> None:
        execute(['ninja', '-t', 'clean'])

    return inner_fn


def compdb(compdb_path: str = 'compile_commands.json') -> Callable[[Dict[str, str], Dict[str, str]], None]:
    """
    Run command `ninja -t compdb`, and save it to `compdb`
    """
    def inner_fn(opts: Dict[str, str], args: Dict[str, str]) -> None:
        compdb = execute_with_stdout(['ninja', '-t', 'compdb'])

        # write json
        json_str = _simplify_compdb(compdb)
        save_content(compdb_path, json_str)

        log_out(LogLevel.INFO, f'Save to `{compdb_path}` completed.')

    return inner_fn


def _simplify_compdb(
    json_str: str,
    outs: List[str] = ['.o', '.obj'],
    exts: List[str] = ['.c', '.h', '.s', '.asm', '.cc', '.hpp', '.cpp', '.ixx', '.cxx'],
) -> str:
    """
    Simpilify the clangd compiled database
    """
    json_obj = json.loads(json_str)
    json_trim = []
    for json_item in json_obj:
        out_name = json_item['output']
        out_ext = os.path.splitext(os.path.basename(out_name))[1]
        file_name = json_item['file']
        file_ext = os.path.splitext(os.path.basename(file_name))[1]
        if file_ext in exts and out_ext in outs:
            json_content = {
                'file': os.path.normpath(file_name),
                'output': os.path.normpath(json_item['output']),
                'directory': json_item['directory'],
                'command': _compdb_filer_command(json_item['command'])
            }
            json_trim.append(json_content)

    # return the json
    return json.dumps(json_trim, indent=2, separators=(',', ': '))


def _compdb_filer_command(cmd: str) -> str:
    """
    Return the command that can be supported clangd
    """
    args = shlex.split(cmd, posix=False)
    used_args = filter(lambda s: not _compdb_filted_argument(s), args)
    new_cmd = ' '.join(_compdb_map_argument(arg) for arg in used_args)
    return new_cmd


def _compdb_map_argument(arg: str) -> str:
    """
    Map the command argument with `""`
    """
    if arg.find(' ') != -1:
        return f'"{arg}"'
    else:
        return arg


def _compdb_filted_argument(arg: str) -> bool:
    """
    Return true if this argument need be ignored
    """
    allow_features = [
        '-fno-exceptions',
        '-fno-rtti',
    ]
    if arg.startswith('-fno-') and arg not in allow_features:
        # trip the gcc `-fno-xxxx` argument
        return True
    else:
        return False
