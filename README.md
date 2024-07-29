Ninjar
======

A small ninjar build script generator framework.

```python
import ninjar
from typing import List, Dict


class SimpleStage(ninjar.ninja.Stage):
    def __init__(self, ninja: ninjar.NinjaGenerator, name: str) -> None:
        super().__init__(ninja, name)

        self._add_option('example')
        self._add_option('command')

    def inherit(self) -> "SimpleStage":
        """
        inherit this object
        """
        new_obj = SimpleStage(self.ninja, self.name)
        new_obj.cmd = self.cmd .copy()
        return new_obj

    def input_type(self) -> List[str]:
        """
        input: `any`
        """
        return [':any']

    def generate_rule(self) -> None:
        """
        Generate the ninja rule statement
        """
        cmd_str = self._get_command()
        self.ninja.add_rule(self.name, cmd_str, 'CC: $in', '$in.d')

    def generate_build(self, input: List[str]) -> str:
        """
        Generate the ninja build statement and return the output file
        """
        # dot't forget need check the len(input) in your project
        inp_file = input[0]
        out_file = f'build/{inp_file}.out'

        self.ninja.add_build(self.name, out_file, input)

        return out_file


@ninjar.action(default=True)
def ninja(opts: Dict[str, str], args: Dict[str, str]):
    """
    Generate the build.ninja file
    """
    # At least one action, called ninja is required.
    # The `action` is a function,
    # `py build.py -t action_name` will execute the action `action_name`

    # This action is the default one
    # `py build.py` will execute this action

    with ninjar.NinjaGenerator() as ninja:
        # let's create a stage
        stage_1 = SimpleStage(ninja, 'simple')

        # the unit stage will return the input
        stage_unit = ninjar.UnitStage(ninja, 'unit')

        # input files, now it's `*.py`
        inp_file = ninjar.select('./*.py')

        # and then, apply the `stage_1` to `inp_file`
        # assume the `*.py` -> [['build.py']]
        # see the `generate_build` method in the `SimpleStage`
        # so the result, the `mid_file`, = [['build.py.out']]
        #
        # inp_file([['build.py']]) -- stage_1 --> build.py.out
        #
        mid_file = inp_file.apply(stage_1)

        # `apply` method can apply more than one stage for the same inputs
        twice_files = mid_file.apply(stage_1, stage_unit)

        # the result is [['build.py.out.out'], ['build.py.out']]
        #
        # mid_file([['build.py.out']]) +- stage_1    --> build.py.out.out
        #                              +- stage_unit --> build.py.out
        #
        # the unit stage return the first input file and do nothing.
        # let's fold the output
        fold_file = twice_files.fold()

        # now the result is [['build.py.out', 'build.py.out']]
        result = fold_file.collect_files()

        # we can use `colorful_print` to print a colorful output
        ninjar.colorful_print(ninjar.Color.Cyan, f'result = `{result}`')

        # let's generate `build.ninja`
        # build.py -- stage_1 --> build.py.out +- stage_1 --> build.py.out.out
        #                                      +- unit    --> build.py.out
        #
        ninja.add_defaults(result)


@ninjar.action()
def not_default(opts: Dict[str, str], args: Dict[str, str]):
    """
    This is not a default action, run it `py build.py -t not_default`
    """
    print('hello, action `not_default`')


@ninjar.action(['ninja'])
def deps_other(opts: Dict[str, str], args: Dict[str, str]):
    """
    An action dependent on `ninja`, run it `py build.py -t deps_other`
    """
    print('hello, action `deps_other`')


if __name__ == '__main__':
    # try the following commands

    # run the default actions
    # py build.py

    # run specific actions
    # py build.py -t not_default
    # py build.py -t deps_other

    # run the build script
    ninjar.BuildScript(__import__(__name__)).run()

```
