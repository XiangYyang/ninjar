# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) XiangYang, all rights reserved.

"""
Variable

This module provides the global variable
"""


import os
import sys
import subprocess
from typing import Dict
from string import Template
from datetime import datetime
from .writeln import LogLevel, log_out


class ExprEvalException(RuntimeError):
    """
    Express eval exception
    """

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


# basic variables
global_variables: Dict[str, str]


def get_global_variables() -> Dict[str, str]:
    """
    get the basic variable
    """
    global global_variables
    return global_variables.copy()


def update_global_variables(values: Dict[str, str]) -> None:
    """
    get the basic variable
    """
    global global_variables
    global_variables.update(values)


def setup_global_variable() -> None:
    """
    Load the default variables
    """
    global global_variables
    global_variables = {}

    # current timr
    now = datetime.now()

    # load git hash
    try:
        cmd_out = subprocess.run('git rev-parse HEAD', check=True, capture_output=True)
        git_commid_hash = cmd_out.stdout.decode('utf-8').strip()
    except subprocess.CalledProcessError:
        git_commid_hash = 'None'
        log_out(LogLevel.WARN, f'! git{global_variables} `git rev-parse HEAD` failed, exitcode is not zero')
    except FileNotFoundError:
        git_commid_hash = 'Undefined'
        log_out(LogLevel.WARN, f'! git{global_variables} `git rev-parse HEAD` failed, `git` was not found')

    # pre-define variables
    global_variables = {
        'root': base_dir(),
        'build': 'target/build',
        'package': 'target/pkgs',
        'tbgen_out': 'target/tbgen',
        'target': 'target',
        'option_hash': 'unknown',
        'date': str(datetime.date(now)),
        'time': str(datetime.time(now)),
        'timestamp': str(datetime.timestamp(now)),
        'git_commit': git_commid_hash,
        'self': get_self_command(),
    }

    # add the enviroment variables
    env_var_table = dict(os.environ)
    for (env_name, env_val) in env_var_table.items():
        buildin_name = f'env_{env_name}'.lower()
        if buildin_name in global_variables:
            raise RuntimeError(f'Logic error: enviroment variable `{buildin_name}` was re-defined')
        else:
            global_variables.update({buildin_name: env_val})


def base_dir() -> str:
    return os.path.abspath('.')


def get_self_command() -> str:
    """
    Get the command of this script
    """
    script_host = os.path.basename(sys.executable)
    script_name = sys.argv[0]
    return f'{script_host} {script_name}'


def global_eval_path(path: str, addition_dict: Dict[str, str] = {}) -> str:
    global global_variables
    var_dict = global_variables.copy()
    var_dict.update(addition_dict)
    return eval_path(path, var_dict)


def global_eval_expr(path: str, addition_dict: Dict[str, str] = {}) -> str:
    global global_variables
    var_dict = global_variables.copy()
    var_dict.update(addition_dict)
    return eval_expr(path, var_dict)


def eval_path(path: str, vars: Dict[str, str]) -> str:
    expr = eval_expr(path, vars)
    return os.path.normpath(expr)


def eval_expr(expr: str, vars: Dict[str, str]) -> str:
    max_step = 16
    old_expr = expr

    # to keep the escape character
    # 好笨蛋 QAQ
    expr = expr.replace('$$', '@=@')

    try:
        while expr.find('$') != -1 and max_step > 0:
            patt = Template(expr)
            expr = patt.substitute(vars)
            max_step -= 1
    except KeyError as e:
        raise ExprEvalException(f'variable `{e.args[0]}` was not found, it was used in `{old_expr}`')

    if max_step == 0:
        raise ExprEvalException(f'cannot eval express: `{old_expr}`, max eval step')

    expr = expr.replace('@=@', '$')

    return expr
