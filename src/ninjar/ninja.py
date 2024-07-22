# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) XiangYang, all rights reserved.

"""
Ninja generator helper

This module provides the abstraction for ninja build scripts
"""

import glob
import io
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import TracebackType
from typing import Dict, Generator, List, Optional, Self, Union, final

from .expr import global_eval_expr, global_eval_path
from .shell import join_command


class QueryTypeError(RuntimeError):
    """
    This exception indicates type checking errors for Query
    """

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class NinjaGenerator:
    """
    Generate build.ninja
    """
    # file handler
    file_handler: io.TextIOWrapper

    # build item
    build_item: List[str]

    # default item
    default_item: List[str]

    def __init__(self, file: str = './build.ninja') -> None:
        self.build_item = []
        self.default_item = []
        self.file_handler = open(file, 'w', encoding='utf-8')
        # write the date
        cur_time = time.strftime('%Y-%m-%d %H:%M:%S (%Z)', time.localtime())
        self.file_handler.writelines([
            '# <autogen>\n',
            '# This file was auto generated, DO NOT edit it by manual\n',
            f'# Generated at {cur_time}\n',
            '# </autogen>\n',
        ])

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional["BaseException"],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        # write the build items
        for line in self.build_item:
            self.file_handler.write(line)
            self.file_handler.write('\n')

        # default targets
        defaults = ' '.join(self.default_item)
        default_stat = f'default {defaults}'

        # write the default target
        self.file_handler.writelines([
            f'# {len(self.build_item)} build statements were generated\n',
            '# default target:\n',
            default_stat,
            '\n',
        ])

        # close the file
        self.file_handler.close()

    def add_rule(self, name: str, command: str, description: str = '', dep_file: str = '') -> None:
        """
        Write a rule

        Args:
            name (str): Rule name
            command (_type_): command
            description (str, optional): rule description
            dep_file (str, optional): dependence files
        """
        self.file_handler.write(f'rule {name}\n')
        self.file_handler.write(f'    command = {command}\n')
        if len(description) > 0:
            self.file_handler.write(f'    description = {description}\n')
        if len(dep_file) > 0:
            self.file_handler.write(f'    depfile = {dep_file}\n')

    def add_build(self, rule: str, out: str, inp: List[str], dyn_deps: List[str] = []) -> None:
        """
        Write a build target

        Args:
            rule (str): build rule
            out (str): output files
            inp (List[str]): input files
        """
        inputs = ' '.join(inp)

        if len(dyn_deps) > 0:
            dyn_deps_str = '|| ' + ' '.join(dyn_deps)
            self.build_item.append(f'build {out}: {rule} {inputs} {dyn_deps_str}')
        else:
            self.build_item.append(f'build {out}: {rule} {inputs}')

    def add_defaults(self, file: Union[str, List[str]]) -> None:
        """
        Add the default target
        """
        if isinstance(file, str):
            self.default_item.append(file)
        else:
            self.default_item += file


class Stage(ABC):
    """
    `Stage` abstract class is a rule statement.

    A stage (`Stage` instance) describes a build command
    which has one or more inputs, and one output.
    It is the abstraction of the Ninja rule statemet.
    """
    name: str
    ninja: NinjaGenerator
    generated_rule: bool
    cmd: List[str]

    def __init__(self, ninja: NinjaGenerator, name: str) -> None:
        super().__init__()
        self.cmd = []
        self.name = name
        self.ninja = ninja
        self.generated_rule = False

    def set_name(self, name: str) -> Self:
        """
        Override the ninja rule name
        """
        self.name = name
        return self

    def get_name(self) -> str:
        """
        Get the rule name
        """
        return self.name

    def apply(self, input: List[str]) -> str:
        if not self.generated_rule:
            self.generate_rule()
            self.generated_rule = True

        return self.generate_build(input)

    def _add_option(self, opt: Union[List[str], str]) -> None:
        """
        (protected) Add options with global_eval_expr
        """
        def inner_fn(opt_item: str) -> None:
            self.cmd.append(global_eval_expr(opt_item))

        if isinstance(opt, str):
            inner_fn(opt)
        else:
            for opt_item in opt:
                inner_fn(opt_item)

    def _get_command(self) -> str:
        """
        (protected) Get the command string
        """
        return join_command(self.cmd)

    @abstractmethod
    def inherit(self) -> "Stage":
        """
        inherit this object
        """

    @abstractmethod
    def input_type(self) -> List[str]:
        """
        Get the input type

        The returned value specifies the all acceptable types.
        """

    @abstractmethod
    def generate_rule(self) -> None:
        """
        Generate the ninja rule statement
        """

    @abstractmethod
    def generate_build(self, input: List[str]) -> str:
        """
        Generate the ninja build statement and return the output file
        """


@final
class UnitStage(Stage):
    """
    Unit stage will returns the same output as the input
    """

    def __init__(self, ninja: NinjaGenerator, name: str) -> None:
        super().__init__(ninja, name)

    def inherit(self) -> "UnitStage":
        return UnitStage(self.ninja, self.name)

    def input_type(self) -> List[str]:
        return [':any']

    def generate_rule(self) -> None:
        pass

    def generate_build(self, input: List[str]) -> str:
        if len(input) != 1:
            raise QueryTypeError(f'input `{input}` is too loog for UnitStage')

        return input[0]


@dataclass
class Element:
    """
    Element is the input and output for building rules

    The `element` is a list, and they all have the type `type_name`.

    For the `type_name`,

    * `:any` means ANY types (match all file extensions)
    * `:undefined` is inner used undefined types
    * other cases, use `type_ext` to describe the type of file `filename.ext`
    """
    element: List[str]
    type_name: str


class Query:
    """
    Query is used to enumrate files.

    It will generate a build statement for the results.
    """
    it: Generator[Element, None, None]

    def __init__(self, it: Generator[Element, None, None]):
        self.it = it

    def apply(self, *rule: Stage) -> "Query":
        """
        Apply the rule

        It will generate build statements for each `Element`.

        If multiple rules are applied,
        for each rule, it will generate build statements for each `Element`

        `UnitStage` class provides an identity element.
        `self.apply(unit_stage)` will returns the same output as the input
        """
        def inner_fn() -> Generator[Element, None, None]:
            for item in self.it:
                for rule_item in rule:
                    inp_type = rule_item.input_type()
                    # check the type
                    if ':any' not in inp_type and item.type_name not in inp_type:
                        raise QueryTypeError(f'`apply` type error: input `{item.type_name}` -> rule `{inp_type}`')

                    # apply the rule
                    out_file = rule_item.apply(item.element)

                    # return the result
                    ext_name = Query._extension_name(out_file)
                    if len(ext_name) == 0:
                        raise QueryTypeError(f'`apply` type error: unknown type name for file `{out_file}`')

                    yield Element([out_file], f'type_{ext_name}')

        return Query(inner_fn())

    def fold(self) -> "Query":
        """
        Fold this to one element
        """
        def inner_fn() -> Generator[Element, None, None]:
            lst = []
            inp_type = ':undefined'

            for item in self.it:
                if inp_type == ':undefined':
                    inp_type = item.type_name
                elif inp_type != item.type_name:
                    raise QueryTypeError(f'`fold` type error: `{item.type_name}` fold to `{inp_type}`')

                # append the items
                for item_inner in item.element:
                    lst.append(item_inner)

            # return the result
            yield Element(lst, f'{inp_type}')

        return Query(inner_fn())

    def flat(self) -> "Query":
        """
        Flatten the input
        """
        def inner_fn() -> Generator[Element, None, None]:
            result: Dict[str, List[str]] = {}

            for item in self.it:
                inp_type = item.type_name

                if inp_type not in result:
                    result[inp_type] = []

                # append the items
                for item_inner in item.element:
                    result[inp_type].append(item_inner)

            # return the result
            for typ, result_item in result.items():
                yield Element(result_item, f'{typ}')

        return Query(inner_fn())

    def collect_files(self) -> List[str]:
        """
        Collect the result to a list and evaluates the Query
        """

        lst = []
        for val in self.it:
            for item in val.element:
                lst.append(item)

        return lst

    def concat(self, other: Self) -> "Query":
        """
        Concat two items
        """
        def inner_fn() -> Generator[Element, None, None]:
            for it in self.it:
                yield it

            for it in other.it:
                yield it

        return Query(inner_fn())

    @staticmethod
    def from_glob(glob_filter: Union[List[str], str], exclude: List[str] = []) -> "Query":
        """
        Get the data view by glob expression
        """
        def inner_fn() -> Generator[Element, None, None]:
            if isinstance(glob_filter, str):
                filters = [glob_filter]
            else:
                filters = glob_filter
            # walker the files
            for filter_item in filters:
                filter_eval = global_eval_path(filter_item)
                for file in glob.iglob(filter_eval):
                    # filter the files
                    res = [i for i in exclude if i in file]
                    if len(res) == 0:
                        ext_name = Query._extension_name(file)
                        # Add files that are not on the exclusion list
                        yield Element([file], f'type_{ext_name}')

        return Query(inner_fn())

    @staticmethod
    def _extension_name(file: str) -> str:
        """
        Get the extension name without the `dot`, e.g. `123.c` -> `c`
        """
        return os.path.splitext(file)[1][1:].lower()
