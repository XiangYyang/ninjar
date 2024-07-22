# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) XiangYang, all rights reserved.

"""
Shell execute helper
"""


import subprocess
from typing import List, Union

from .expr import global_eval_path
from .writeln import LogLevel, log_out


class ShellError(RuntimeError):
    """
    Shell command error
    """

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def execute(cmd: Union[str, List[str]]) -> None:
    """
    Execute the command
    """
    if isinstance(cmd, str):
        cmd_str = join_command([cmd])
    else:
        cmd_str = join_command(cmd)

    # replace variables
    cmd_eval = global_eval_path(cmd_str)
    log_out(LogLevel.DEBUG, f'> run `{cmd_eval}`')

    try:
        subprocess.run(cmd_eval, check=True)
    except subprocess.CalledProcessError:
        raise ShellError(f'command `{cmd_eval}` exit code is not 0')


def execute_with_stdout(cmd: Union[str, List[str]], encoding: str = 'utf-8') -> str:
    """
    Execute the command and return the stdout
    """
    if isinstance(cmd, str):
        cmd_str = join_command([cmd])
    else:
        cmd_str = join_command(cmd)

    # replace variables
    cmd_eval = global_eval_path(cmd_str)
    log_out(LogLevel.DEBUG, f'> run `{cmd_eval}`')

    try:
        cmd_out = subprocess.run(cmd_eval, check=True, capture_output=True)
        return cmd_out.stdout.decode(encoding).rstrip()
    except subprocess.CalledProcessError:
        raise ShellError(f'command `{cmd_eval}` exit code is not 0')


def save_content(path: str, content: str, encoding: str = 'utf-8') -> str:
    """
    Save the string content
    """
    path_val = global_eval_path(path)
    str_byte = content.encode(encoding)
    with open(path_val, 'wb') as f:
        f.write(str_byte)

    return path_val


def join_command(args: List[str]) -> str:
    """
    Join the space into `args`
    """
    return ' '.join(map(lambda s: f'"{s}"' if s.find(' ') != -1 else s, args))
