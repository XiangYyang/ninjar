# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) XiangYang, all rights reserved.

"""
Build script helper

This module provides a command invoker based `inspect` module.
"""


import argparse
import hashlib
import inspect
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from types import ModuleType
from typing import Any, Callable, Dict, List, NoReturn, Tuple, TypeAlias, Union

from . import cmds as ninja_tool
from . import expr, shell, writeln
from .ninja import QueryTypeError
from .writeln import LogLevel, log_out

# note:
# for the new version (Python >= 3.12)
# TypeAlias was deprecated
# but the version 3.12 is too new at this time
# the latest version is 3.12.4 today (24/07/15)
# so we still use `TypeAlias` rather than `type statement`
# see also:
# https://docs.python.org/zh-cn/3/library/typing.html#typing.TypeAlias


# Options
OriginOption: TypeAlias = Union[Tuple[str, str, Callable[[str], bool]], Tuple[str, str], str]

# dict lazy-eval functions
UserOptFunction: TypeAlias = Callable[[], Dict[str, OriginOption]]


# dict lazy-eval functions
UserVarFunction: TypeAlias = Callable[[], Dict[str, str]]


# action functions
ActionFunction: TypeAlias = Callable[[Dict[str, str], Dict[str, str]], None]


class BuildScriptException(RuntimeError):
    """
    Build script error
    """

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class ActionArgumentType(Enum):
    VALUE = 'value'
    OPTION = '?'
    APPEND_LIST = '+'


@dataclass
class ActionArgument:
    typ: ActionArgumentType
    name: str
    descript: str


@dataclass
class Action:
    name: str
    descript: str
    deps: List[str]
    default: bool
    additional_args: List[ActionArgument]
    eval_fn: Callable[[Dict[str, str], Dict[str, str]], None]


@dataclass
class UserOption:
    name: str
    value: str
    descript: str
    filter_fn: Callable[[str], bool]


def variables() -> Callable[[UserVarFunction], UserVarFunction]:
    """
    Specify variables
    """

    def var_inner(vars_lazy_fn: UserVarFunction) -> UserVarFunction:
        result = vars_lazy_fn()

        def build_script_variables() -> Dict[str, str]:
            return result

        return build_script_variables

    return var_inner


def options() -> Callable[[UserOptFunction], Callable[[], Dict[str, UserOption]]]:
    """
    Specify options
    """
    def default_filter_fn(x: Any) -> bool:
        return True

    def var_inner(vars_lazy_fn: UserOptFunction) -> Callable[[], Dict[str, UserOption]]:
        result = {}
        var_value = vars_lazy_fn()

        for key, value in var_value.items():
            if isinstance(value, tuple):
                if len(value) == 2:
                    if isinstance(value[1], str):
                        # for `(tuple)`, it's (default_value, description)
                        obj = UserOption(key, str(value[0]), value[1], default_filter_fn)
                    elif inspect.isfunction(value[1]):
                        # for `(tuple)`, it's (default_value, filter_function)
                        obj = UserOption(key, str(value[0]), 'No description', value[1])
                    else:
                        raise RuntimeError(f'Invaild value in tuple value `{value}`[1]')
                elif len(value) == 3:
                    # for `(tuple)`, it's (default_value, description, filter_function)
                    obj = UserOption(key, str(value[0]), value[1], value[2])
                else:
                    raise RuntimeError(f'Variable item `{key}` has incorrent tuple value `{value}`')
            else:
                # for `str`, it's default_value
                obj = UserOption(key, str(value), 'No description', default_filter_fn)

            result.update({key: obj})

        def build_script_user_options() -> Dict[str, UserOption]:
            return result

        return build_script_user_options

    return var_inner


def action(
    deps: Union[List[str], str] = [],
    arg_list: List[Union[str, Tuple[str, str]]] = [],
    default: bool = False
) -> Callable[[ActionFunction], Action]:
    """
    Specify a step/script for the build script
    """
    def deps_inner(func: ActionFunction) -> Action:
        @wraps(func)
        def wrapped(arg1: Dict[str, str], arg2: Dict[str, str]) -> None:
            return func(arg1, arg2)

        if isinstance(deps, list):
            deps_list = deps.copy()
        else:
            deps_list = [deps]

        func_name = func.__name__
        func_docs = inspect.getdoc(func)
        func_descript = 'No description' if func_docs is None else func_docs

        func_args = []
        for item in arg_list:
            if isinstance(item, str):
                arg_name = item
                arg_descript = 'No description'
            else:
                arg_name = item[0]
                arg_descript = item[1]

            # parse the name suffix, to determine the argument type
            if arg_name.startswith('?'):
                arg_typ = ActionArgumentType.OPTION
                arg_actual_name = arg_name[1:]
            elif arg_name.startswith('+'):
                arg_typ = ActionArgumentType.APPEND_LIST
                arg_actual_name = arg_name[1:]
            else:
                arg_typ = ActionArgumentType.VALUE
                arg_actual_name = arg_name

            # add to the argument list
            func_args.append(ActionArgument(arg_typ, arg_actual_name, arg_descript))

        return Action(func_name, func_descript, deps_list, default, func_args, wrapped)

    return deps_inner


class BuildScript:
    """
    Build script helper

    This class adds action functions by reflection
    """
    args: argparse.Namespace
    actions: Dict[str, Action]
    options: Dict[str, UserOption]
    variables: Dict[str, str]

    def __init__(self, self_module: ModuleType) -> None:
        writeln.init()
        expr.setup_global_variable()

        self.actions = {}
        self.options = {}
        self.variables = {}

        # load objects
        objs = {}
        for obj_key, obj_val in inspect.getmembers(self_module):
            objs.update({obj_key: obj_val})

        try:
            # get the __doc__ from main module
            descript = inspect.getdoc(self_module)
            descript_str = 'Build script' if descript is None else descript

            # argument parser
            parser = argparse.ArgumentParser(
                description=descript_str,
                formatter_class=argparse.RawTextHelpFormatter,
            )

            # add default options
            BuildScript._add_default_arguments(parser)

            # add action arguments
            self._add_action_arguments(objs, parser)

            # parse the arguments
            self.args = parser.parse_args()

            # release?
            self.options.update({
                'release':  UserOption('release',
                                       str(0),
                                       'Use the release build?',
                                       lambda s: s in ['1', '0'])})
            # add default action
            self.actions.update({
                'build': Action('build',
                                'Run `ninja` command',
                                ['ninja'],
                                False,
                                [],
                                ninja_tool.build())})

            self.actions.update({
                'clean': Action('clean',
                                'Run `ninja -t clean` command',
                                ['ninja'],
                                False,
                                [],
                                ninja_tool.clean())})

            self.actions.update({
                'compdb': Action('compdb',
                                'Run `ninja -t compdb > compiler_commands.json` command',
                                 ['ninja'],
                                 False,
                                 [],
                                 ninja_tool.compdb())})

            # add actions
            self._add_actions(objs)

            # add options
            self._add_options(objs)

            # add variables from reflect data
            self._add_variables(objs)

            # check existing `ninja` action
            if 'ninja' not in self.actions:
                raise BuildScriptException('missing `ninja` action')
        except BuildScriptException as e:
            log_out(LogLevel.FATAL, f'x Runtime error {e}')
            quit(1)

    def run(self) -> NoReturn:
        """
        Run the build script
        """
        # set the log-level
        if self.args.verbose:
            writeln.set_log_level(LogLevel.DEBUG)
        else:
            writeln.set_log_level(LogLevel.INFO)

        # version info?
        if self.args.version:
            log_out(LogLevel.MESSAGE, 'Build script version 2.0.0')
            quit(0)

        # print list?
        if self.args.list:
            self._print_list()
            quit(0)

        # run the build script
        try:
            self._run_build_script()
        except BuildScriptException as e:
            log_out(LogLevel.FATAL, f'x build script error: {e}')
            quit(1)
        except expr.ExprEvalException as e:
            log_out(LogLevel.FATAL, f'x Express error: {e}')
            quit(1)
        except QueryTypeError as e:
            log_out(LogLevel.FATAL, f'x Query failed: {e}')
            quit(1)
        except shell.ShellError as e:
            log_out(LogLevel.FATAL, f'x Run command failed: {e}')
            quit(1)
        except RuntimeError as e:
            log_out(LogLevel.FATAL, f'x runtime error: {e}')
            quit(1)

        quit(0)

    def _run_build_script(self) -> None:
        """
        Run the build script
        """
        need_run = self.args.tool.copy()

        # add the default action if NONE item was specified
        if len(need_run) == 0:
            for k, item in self.actions.items():
                if item.default:
                    need_run.append(k)

        # check the length
        if len(need_run) == 0:
            log_out(LogLevel.WARN, '! No action was run')
            return

        # parse the variable arguments
        options_val = BuildScript._parse_options(self.options, self.args.option)

        # generate the options values
        options_table = {}
        for opt_name, opt_val in self.options.items():
            options_table.update({opt_name: opt_val.value})

        # update the options table
        options_table.update(options_val)

        # update global variables
        for var_name, var_value in self.variables.items():
            if var_name in expr.get_global_variables():
                raise BuildScriptException(f'Variable `{var_name}` was redefined')

        expr.update_global_variables(self.variables)

        # calculate the hash of options
        options_hash = BuildScript._dict_hash(options_table)
        expr.update_global_variables({'option_hash': options_hash})

        # run the actions!!
        self._run_actions(need_run, options_table)

    def _run_actions(self, actions: List[str], options: Dict[str, str]) -> None:
        """
        Run actions
        """
        track_list: List[str] = []

        for action in actions:
            if action not in self.actions:
                raise BuildScriptException(f'Cannot find action `{action}`')

            self._run_single_action(action, options, track_list, [])

    def _run_single_action(
        self,
        action: str,
        user_options: Dict[str, str],
        track_list: List[str], depth_list: List[str]
    ) -> None:
        """
        Run actions
        """
        if action in track_list:
            return

        # check the action existing
        if action not in self.actions:
            depth_list.reverse()
            hint_msg = ' -> '.join(depth_list)
            raise BuildScriptException(f'action {action} was not found, deps: {hint_msg}')

        act = self.actions[action]

        # check the recursion depth
        if act.name in depth_list:
            depth_list.reverse()
            hint_msg = ' -> '.join(depth_list)
            raise BuildScriptException(f'cycle reference: {act.name} -> {hint_msg}')

        # record this call
        depth_list.append(act.name)

        # run the dependences
        for act_name in act.deps:
            self._run_single_action(act_name, user_options, track_list, depth_list.copy())

        # generate the argument table
        arg_table = {}

        for add_args in act.additional_args:
            arg_name = f'{act.name}-{add_args.name}'.replace('-', '_')
            str_value = str(inspect.getattr_static(self.args, arg_name, ''))

            arg_table.update({add_args.name: str_value})

        # run this
        log_out(LogLevel.MESSAGE, f'> run {action}')
        act.eval_fn(user_options, arg_table)
        track_list.append(action)

    def _print_list(self) -> None:
        """
        Print the tool list
        """
        log_out(LogLevel.MESSAGE, 'Action list: ')

        for k, action in self.actions.items():
            log_out(LogLevel.INFO, f'- {k:<12s} {action.descript}')

        if len(self.actions) == 0:
            log_out(LogLevel.INFO, '- (no action was found)')

        log_out(LogLevel.MESSAGE, 'Option list: ')
        for k, option in self.options.items():
            log_out(LogLevel.INFO, f'- {k:<12s} {option.descript}')

        if len(self.options) == 0:
            log_out(LogLevel.INFO, '- (no option was found)')

    def _add_actions(self, objs: Dict[str, Any]) -> None:
        """
        Add actions into the list
        """
        for k, obj in objs.items():
            if not isinstance(obj, Action):
                continue

            if obj.name in self.actions:
                raise BuildScriptException(f'Action `{obj.name}` was existed')

            self.actions.update({obj.name: obj})

    def _add_options(self, objs: Dict[str, Any]) -> None:
        """
        Add custom-defined options
        """
        for k, obj in objs.items():
            if not inspect.isfunction(obj):
                continue

            if obj.__name__ != 'build_script_user_options':
                continue

            self.options.update(obj())

    def _add_variables(self, objs: Dict[str, Any]) -> None:
        """
        Add custom variables to global
        """
        for k, obj in objs.items():
            if not inspect.isfunction(obj):
                continue

            if obj.__name__ != 'build_script_variables':
                continue

            self.variables.update(obj())

    def _add_action_arguments(self, objs: Dict[str, Any], parser: argparse.ArgumentParser) -> None:
        """
        Add argument for actions
        """
        for k, obj in objs.items():
            if not isinstance(obj, Action):
                continue

            p = parser.add_argument_group(title=f'{obj.name} options')

            for arg in obj.additional_args:
                opt_name = f'--{obj.name}-{arg.name}'.replace('_', '-')

                if arg.typ == ActionArgumentType.APPEND_LIST:
                    # append to the list, like --arg va1 val2 ...
                    p.add_argument(opt_name, type=str, default=[],
                                   action="extend", nargs="+", help=arg.descript)
                elif arg.typ == ActionArgumentType.OPTION:
                    # store true
                    p.add_argument(opt_name, default=False,
                                   action='store_true', help=arg.descript)
                elif arg.typ == ActionArgumentType.VALUE:
                    # just a value
                    p.add_argument(opt_name, type=str, default='',
                                   help=arg.descript)
                else:
                    raise RuntimeWarning(f'Unknown type `{arg.typ}` for argument `{arg.name}`')

    @staticmethod
    def _dict_hash(dict: Dict[str, str], length: int = 1) -> str:
        """
        (protected) Get the string hash
        """
        string = ''
        for k, v in dict.items():
            string += f'{k}={v},'

        return hashlib.shake_128(string.encode('utf-8')).hexdigest(length)

    @staticmethod
    def _parse_options(var_table: Dict[str, UserOption], args: List[str]) -> Dict[str, str]:
        """
        Parse the user-defned options
        """
        result = {}

        for var_expr in args:
            var_cont = var_expr.split('=')

            # parse the input
            if len(var_cont) == 1:
                var_name = var_cont[0]
                var_value = '1'
            elif len(var_cont) == 2:
                var_name = var_cont[0]
                var_value = var_cont[1]
            else:
                raise BuildScriptException(f'Cannot parse option `{var_expr}`')

            # check the name, makesure the variable was defined
            if var_name not in var_table:
                raise BuildScriptException(f'Undefined option `{var_name}`')

            # check the value
            var_defs = var_table[var_name]
            filter_res = var_defs.filter_fn(var_value)
            if not filter_res:
                raise BuildScriptException(f'{var_name} = `{var_value}` is invaild')

            result.update({var_name: var_value})

        return result

    @staticmethod
    def _add_default_arguments(parser: argparse.ArgumentParser) -> None:
        """
        Add the basic arguments
        """
        parser.add_argument('-V', '--version', default=False,
                            action='store_true', help='print version info and exit')

        parser.add_argument('-r', '--release', default=False, action='store_true',
                            help='use the `release` profile, default to false')

        parser.add_argument('-l', '--list', default=False,
                            action='store_true', help='display all available tools, scripts, option')

        parser.add_argument('-t', '--tool', type=str, default=[],
                            action="extend", nargs="+", help='run the action')

        parser.add_argument('-D', '--option', type=str, default=[],
                            action="extend", nargs="+", help='set the option')

        parser.add_argument('-v', '--verbose', default=False, action='store_true',
                            help='use verbose output')
