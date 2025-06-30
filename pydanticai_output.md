# `pydantic_ai.output`

### OutputDataT

```python
OutputDataT = TypeVar(
    "OutputDataT", default=str, covariant=True
)

```

Covariant type variable for the output data type of a run.

### ToolOutput

Bases: `Generic[OutputDataT]`

Marker class to use a tool for output and optionally customize the tool.

Example: tool_output.py

```python
from pydantic import BaseModel

from pydantic_ai import Agent, ToolOutput


class Fruit(BaseModel):
    name: str
    color: str


class Vehicle(BaseModel):
    name: str
    wheels: int


agent = Agent(
    'openai:gpt-4o',
    output_type=[
        ToolOutput(Fruit, name='return_fruit'),
        ToolOutput(Vehicle, name='return_vehicle'),
    ],
)
result = agent.run_sync('What is a banana?')
print(repr(result.output))
#> Fruit(name='banana', color='yellow')

```

Source code in `pydantic_ai_slim/pydantic_ai/output.py`

````python
@dataclass(init=False)
class ToolOutput(Generic[OutputDataT]):
    """Marker class to use a tool for output and optionally customize the tool.

    Example:
    ```python {title="tool_output.py"}
    from pydantic import BaseModel

    from pydantic_ai import Agent, ToolOutput


    class Fruit(BaseModel):
        name: str
        color: str


    class Vehicle(BaseModel):
        name: str
        wheels: int


    agent = Agent(
        'openai:gpt-4o',
        output_type=[
            ToolOutput(Fruit, name='return_fruit'),
            ToolOutput(Vehicle, name='return_vehicle'),
        ],
    )
    result = agent.run_sync('What is a banana?')
    print(repr(result.output))
    #> Fruit(name='banana', color='yellow')
    ```
    """

    output: OutputTypeOrFunction[OutputDataT]
    """An output type or function."""
    name: str | None
    """The name of the tool that will be passed to the model. If not specified and only one output is provided, `final_result` will be used. If multiple outputs are provided, the name of the output type or function will be added to the tool name."""
    description: str | None
    """The description of the tool that will be passed to the model. If not specified, the docstring of the output type or function will be used."""
    max_retries: int | None
    """The maximum number of retries for the tool."""
    strict: bool | None
    """Whether to use strict mode for the tool."""

    def __init__(
        self,
        type_: OutputTypeOrFunction[OutputDataT],
        *,
        name: str | None = None,
        description: str | None = None,
        max_retries: int | None = None,
        strict: bool | None = None,
    ):
        self.output = type_
        self.name = name
        self.description = description
        self.max_retries = max_retries
        self.strict = strict

````

#### output

```python
output: OutputTypeOrFunction[OutputDataT] = type_

```

An output type or function.

#### name

```python
name: str | None = name

```

The name of the tool that will be passed to the model. If not specified and only one output is provided, `final_result` will be used. If multiple outputs are provided, the name of the output type or function will be added to the tool name.

#### description

```python
description: str | None = description

```

The description of the tool that will be passed to the model. If not specified, the docstring of the output type or function will be used.

#### max_retries

```python
max_retries: int | None = max_retries

```

The maximum number of retries for the tool.

#### strict

```python
strict: bool | None = strict

```

Whether to use strict mode for the tool.

### NativeOutput

Bases: `Generic[OutputDataT]`

Marker class to use the model's native structured outputs functionality for outputs and optionally customize the name and description.

Example: native_output.py

```python
from tool_output import Fruit, Vehicle

from pydantic_ai import Agent, NativeOutput


agent = Agent(
    'openai:gpt-4o',
    output_type=NativeOutput(
        [Fruit, Vehicle],
        name='Fruit or vehicle',
        description='Return a fruit or vehicle.'
    ),
)
result = agent.run_sync('What is a Ford Explorer?')
print(repr(result.output))
#> Vehicle(name='Ford Explorer', wheels=4)

```

Source code in `pydantic_ai_slim/pydantic_ai/output.py`

````python
@dataclass(init=False)
class NativeOutput(Generic[OutputDataT]):
    """Marker class to use the model's native structured outputs functionality for outputs and optionally customize the name and description.

    Example:
    ```python {title="native_output.py" requires="tool_output.py"}
    from tool_output import Fruit, Vehicle

    from pydantic_ai import Agent, NativeOutput


    agent = Agent(
        'openai:gpt-4o',
        output_type=NativeOutput(
            [Fruit, Vehicle],
            name='Fruit or vehicle',
            description='Return a fruit or vehicle.'
        ),
    )
    result = agent.run_sync('What is a Ford Explorer?')
    print(repr(result.output))
    #> Vehicle(name='Ford Explorer', wheels=4)
    ```
    """

    outputs: OutputTypeOrFunction[OutputDataT] | Sequence[OutputTypeOrFunction[OutputDataT]]
    """The output types or functions."""
    name: str | None
    """The name of the structured output that will be passed to the model. If not specified and only one output is provided, the name of the output type or function will be used."""
    description: str | None
    """The description of the structured output that will be passed to the model. If not specified and only one output is provided, the docstring of the output type or function will be used."""

    def __init__(
        self,
        outputs: OutputTypeOrFunction[OutputDataT] | Sequence[OutputTypeOrFunction[OutputDataT]],
        *,
        name: str | None = None,
        description: str | None = None,
    ):
        self.outputs = outputs
        self.name = name
        self.description = description

````

#### outputs

```python
outputs: (
    OutputTypeOrFunction[OutputDataT]
    | Sequence[OutputTypeOrFunction[OutputDataT]]
) = outputs

```

The output types or functions.

#### name

```python
name: str | None = name

```

The name of the structured output that will be passed to the model. If not specified and only one output is provided, the name of the output type or function will be used.

#### description

```python
description: str | None = description

```

The description of the structured output that will be passed to the model. If not specified and only one output is provided, the docstring of the output type or function will be used.

### PromptedOutput

Bases: `Generic[OutputDataT]`

Marker class to use a prompt to tell the model what to output and optionally customize the prompt.

Example: prompted_output.py

```python
from pydantic import BaseModel
from tool_output import Vehicle

from pydantic_ai import Agent, PromptedOutput


class Device(BaseModel):
    name: str
    kind: str


agent = Agent(
    'openai:gpt-4o',
    output_type=PromptedOutput(
        [Vehicle, Device],
        name='Vehicle or device',
        description='Return a vehicle or device.'
    ),
)
result = agent.run_sync('What is a MacBook?')
print(repr(result.output))
#> Device(name='MacBook', kind='laptop')

agent = Agent(
    'openai:gpt-4o',
    output_type=PromptedOutput(
        [Vehicle, Device],
        template='Gimme some JSON: {schema}'
    ),
)
result = agent.run_sync('What is a Ford Explorer?')
print(repr(result.output))
#> Vehicle(name='Ford Explorer', wheels=4)

```

Source code in `pydantic_ai_slim/pydantic_ai/output.py`

````python
@dataclass(init=False)
class PromptedOutput(Generic[OutputDataT]):
    """Marker class to use a prompt to tell the model what to output and optionally customize the prompt.

    Example:
    ```python {title="prompted_output.py" requires="tool_output.py"}
    from pydantic import BaseModel
    from tool_output import Vehicle

    from pydantic_ai import Agent, PromptedOutput


    class Device(BaseModel):
        name: str
        kind: str


    agent = Agent(
        'openai:gpt-4o',
        output_type=PromptedOutput(
            [Vehicle, Device],
            name='Vehicle or device',
            description='Return a vehicle or device.'
        ),
    )
    result = agent.run_sync('What is a MacBook?')
    print(repr(result.output))
    #> Device(name='MacBook', kind='laptop')

    agent = Agent(
        'openai:gpt-4o',
        output_type=PromptedOutput(
            [Vehicle, Device],
            template='Gimme some JSON: {schema}'
        ),
    )
    result = agent.run_sync('What is a Ford Explorer?')
    print(repr(result.output))
    #> Vehicle(name='Ford Explorer', wheels=4)
    ```
    """

    outputs: OutputTypeOrFunction[OutputDataT] | Sequence[OutputTypeOrFunction[OutputDataT]]
    """The output types or functions."""
    name: str | None
    """The name of the structured output that will be passed to the model. If not specified and only one output is provided, the name of the output type or function will be used."""
    description: str | None
    """The description that will be passed to the model. If not specified and only one output is provided, the docstring of the output type or function will be used."""
    template: str | None
    """Template for the prompt passed to the model.
    The '{schema}' placeholder will be replaced with the output JSON schema.
    If not specified, the default template specified on the model's profile will be used.
    """

    def __init__(
        self,
        outputs: OutputTypeOrFunction[OutputDataT] | Sequence[OutputTypeOrFunction[OutputDataT]],
        *,
        name: str | None = None,
        description: str | None = None,
        template: str | None = None,
    ):
        self.outputs = outputs
        self.name = name
        self.description = description
        self.template = template

````

#### outputs

```python
outputs: (
    OutputTypeOrFunction[OutputDataT]
    | Sequence[OutputTypeOrFunction[OutputDataT]]
) = outputs

```

The output types or functions.

#### name

```python
name: str | None = name

```

The name of the structured output that will be passed to the model. If not specified and only one output is provided, the name of the output type or function will be used.

#### description

```python
description: str | None = description

```

The description that will be passed to the model. If not specified and only one output is provided, the docstring of the output type or function will be used.

#### template

```python
template: str | None = template

```

Template for the prompt passed to the model. The '{schema}' placeholder will be replaced with the output JSON schema. If not specified, the default template specified on the model's profile will be used.

### TextOutput

Bases: `Generic[OutputDataT]`

Marker class to use text output for an output function taking a string argument.

Example:

```python
from pydantic_ai import Agent, TextOutput


def split_into_words(text: str) -> list[str]:
    return text.split()


agent = Agent(
    'openai:gpt-4o',
    output_type=TextOutput(split_into_words),
)
result = agent.run_sync('Who was Albert Einstein?')
print(result.output)
#> ['Albert', 'Einstein', 'was', 'a', 'German-born', 'theoretical', 'physicist.']

```

Source code in `pydantic_ai_slim/pydantic_ai/output.py`

````python
@dataclass
class TextOutput(Generic[OutputDataT]):
    """Marker class to use text output for an output function taking a string argument.

    Example:
    ```python
    from pydantic_ai import Agent, TextOutput


    def split_into_words(text: str) -> list[str]:
        return text.split()


    agent = Agent(
        'openai:gpt-4o',
        output_type=TextOutput(split_into_words),
    )
    result = agent.run_sync('Who was Albert Einstein?')
    print(result.output)
    #> ['Albert', 'Einstein', 'was', 'a', 'German-born', 'theoretical', 'physicist.']
    ```
    """

    output_function: TextOutputFunc[OutputDataT]
    """The function that will be called to process the model's plain text output. The function must take a single string argument."""

````

#### output_function

```python
output_function: TextOutputFunc[OutputDataT]

```

The function that will be called to process the model's plain text output. The function must take a single string argument.