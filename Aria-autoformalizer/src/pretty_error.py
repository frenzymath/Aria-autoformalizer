from typing import Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class Pos(BaseModel):
    line: int
    column: int

Severity = Literal['error', 'warning', 'information', 'sorry']

class Message(BaseModel):
    severity: Severity
    pos: Pos | None
    end_pos: Pos | None
    # kind: str
    keep_full_range: bool
    data: str
    caption: str

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class SortedMessages(BaseModel):
    sorries: list[Message] = []
    errors: list[Message] = []
    warnings: list[Message] = []
    informations: list[Message] = []

class VerifyResult(BaseModel):
    sorted_messages: SortedMessages
    system_errors: str | None
    verified_code: str
    verified_timeout: int
    pass_: bool # Indicates if the verification passed the compiler
    complete: bool # Indicates if the verification contains no sorries or failed declarations
    is_timeout: bool
    verify_time: float
    complete_timestamp: str
    extra_info: dict
    lean_toolchain: str | None = None

    @staticmethod
    @staticmethod
    def from_system_error(code: str, timeout: int, system_errors: str, lean_toolchain: str='remote') -> 'VerifyResult':
        return VerifyResult(
            sorted_messages=SortedMessages(),
            system_errors=system_errors,
            verified_code=code,
            verified_timeout=timeout,
            pass_=False,
            complete=False,
            is_timeout=False,
            verify_time=0.0,
            complete_timestamp=datetime.now().isoformat(),
            extra_info={},
            lean_toolchain=lean_toolchain
        )

def no_pos_pretty_print_message(message: Message) -> str:
    """
    Pretty print the message without position information.
    """
    if not message.caption.strip():
        return f"{message.severity.upper()}: {message.data.strip()}"
    return f"{message.severity.upper()}: {message.caption} - {message.data}"

def pretty_print_message(
    message: Message,
    code: str, 
    ctx: int=2,
    max_data_length: int=2000,
    max_context_lines: int=10
) -> str:
    """ 
    Pretty print the message with position and context 
    from the code, so that users can understand the message better.
    """
    if message.pos is None or message.end_pos is None:
        return no_pos_pretty_print_message(message)
    lines = code.splitlines()
    sl, sc = message.pos.line, message.pos.column
    el, ec = message.end_pos.line, message.end_pos.column

    out: list[str] = []
    ln_width = len(str(el + ctx))  # width for number column

    # Helper that prints a normal line with its number
    def add_line(n: int, text: str):
        out.append(f"{str(n).rjust(ln_width)}│ {text}")
    
    def count_spaces(text: str) -> tuple[int, int]:
        """ Count leading and ending spaces in a line of text. """
        return (len(text) - len(text.lstrip()), 
                len(text) - len(text.rstrip()))
    
    def add_mark_line(n: int, text: str):
        """ Add a line with just the mark. """
        add_line(n, text)
        nlsp, nrsp = count_spaces(text)
        out.append(f'{" " * ln_width}│ ' + " " * nlsp + "^" * (len(text) - nlsp - nrsp) + " " * nrsp)

    # Context *before* the span
    for i in range(max(1, sl - ctx), sl):
        add_line(i, lines[i - 1])

    # Handle single- vs multi-line span
    if sl == el:
        line = lines[sl - 1]
        add_line(sl, line)
        caret_len = max(1, ec - sc)
        out.append(
            f'{" " * ln_width}│ ' + " " * (sc) + "^" * caret_len
        )
    elif el - sl <= max_context_lines:
        # first line
        first = lines[sl - 1]
        add_line(sl, first)
        out.append(
            f'{" " * ln_width}│ ' + " " * (sc) + "^" * (len(first) - sc + 1)
        )
        # middle lines
        for n in range(sl + 1, el):
            add_mark_line(n, lines[n - 1])
        # last line
        last = lines[el - 1]
        add_mark_line(el, last)
    else:
        # If the span is too long, just underline first two lines and
        # last two lines, middle lines is represented by one line of
        # "...".
        
        # First 2 lines
        first = lines[sl - 1]
        add_line(sl, first)
        out.append(
            f'{" " * ln_width}│ ' + " " * (sc) + "^" * (len(first) - sc + 1)
        )
        second = lines[sl]
        add_mark_line(sl + 1, second)
        # Middle line
        nlsp, _ = count_spaces(second)
        out.append(f'{" " * ln_width}│ ' + " " * nlsp + "...")
        # Last 2 lines
        second_last = lines[el - 2]
        add_mark_line(el - 1, second_last)
        last = lines[el - 1]
        add_mark_line(el, last)

    # Context *after* the span
    for i in range(el + 1, min(len(lines) + 1, el + ctx + 1)):
        add_line(i, lines[i - 1])

    snippet = "\n".join(out)
    data = message.data.strip()
    if len(message.data) > max_data_length:
        data = message.data[:max_data_length] + "..."

    if message.caption.strip():
        return f"{message.severity.upper()}: {message.caption} - {data}\nContext:\n{snippet}"
    return f"{message.severity.upper()}: {data}\nContext:\n{snippet}"

def pp_verify_result(
    verify_result: VerifyResult,
    include_warnings: bool = False,
    include_system_errors: bool = True,
    include_context: bool = True
) -> str:
    """
    Pretty print the verification result with optional system errors and context.
    """
    result = ""
    if include_system_errors and verify_result.system_errors:
        result = f"System Errors: {verify_result.system_errors}\n"
    
    if not verify_result.sorted_messages:
        result += "No messages."
        return result
    
    result += "\nMessages:\n"
    messages: list[Message] = verify_result.sorted_messages.sorries + \
        verify_result.sorted_messages.errors
    
    if include_warnings:
        messages += verify_result.sorted_messages.warnings

    for message in messages:
        if include_context:
            result += pretty_print_message(message, verify_result.verified_code) + "\n"
        else:
            result += no_pos_pretty_print_message(message) + "\n"
    
    return result.strip()