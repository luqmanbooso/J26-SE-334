"""libcst helpers for reading and rewriting generated step functions."""

from __future__ import annotations

import ast
from dataclasses import dataclass

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider


class StepNotFoundError(ValueError):
    """Raised when a generated step or literal locator cannot be found."""


@dataclass(frozen=True)
class StepInfo:
    """Locator and action extracted from one generated step."""

    action: str | None
    by: str
    value: str


def extract_step(source: str, step_index: int) -> StepInfo:
    """Read the explicit locator and action from a generated step."""
    module = _parse(source)
    target = f"step_{step_index}"
    visitor = FindStep(target)
    module.visit(visitor)
    for node, action in visitor.calls:
        return _step_info(node, action)
    raise StepNotFoundError(f"Step function {target} was not found")


def rewrite_step_locator(
    source: str,
    step_index: int,
    by: str,
    value: str,
    note: str,
) -> str:
    """Rewrite only the locator call and prepend an audit comment."""
    info = extract_step(source, step_index)
    module = _parse(source)
    target = f"step_{step_index}"
    wrapper = MetadataWrapper(module)
    transformer = ReplaceCall(
        target,
        info.by,
        info.value,
        by,
        value,
    )
    rewritten = wrapper.visit(transformer).code
    if not transformer._replaced:
        raise StepNotFoundError("Locator call was not found")
    old = f"{info.by}={info.value}"
    return f"# healed: {old} -> {by}={value} ({note})\n{rewritten}"


class FindStep(cst.CSTVisitor):
    """Collect locator calls under one function."""

    def __init__(self, function_name: str) -> None:
        self.function_name = function_name
        self.calls: list[tuple[cst.Call, str | None]] = []
        self._inside = False

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        if node.name.value == self.function_name:
            self._inside = True
        return True

    def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
        if node.name.value == self.function_name:
            self._inside = False

    def visit_Call(self, node: cst.Call) -> None:
        if (
            self._inside
            and _is_find_element(node)
            and not any(call is node for call, _ in self.calls)
        ):
            self.calls.append((node, None))

    def visit_Attribute(self, node: cst.Attribute) -> None:
        if (
            self._inside
            and node.attr.value in {"click", "send_keys"}
            and isinstance(node.value, cst.Call)
            and _is_find_element(node.value)
        ):
            action = {"click": "tap", "send_keys": "input"}.get(node.attr.value)
            if not any(call is node.value for call, _ in self.calls):
                self.calls.append((node.value, action))


class ReplaceCall(cst.CSTTransformer):
    """Replace a matching locator call inside one generated function."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, function_name: str, old_by: str, old_value: str, by: str, value: str) -> None:
        self.function_name = function_name
        self.old_by = old_by
        self.old_value = old_value
        self.by = by
        self.value = value
        self._inside = False
        self._replaced = False

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        if node.name.value == self.function_name:
            self._inside = True
        return True

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        if original_node.name.value == self.function_name:
            self._inside = False
        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        if self._replaced or not self._inside or not _is_find_element(original_node):
            return updated_node
        if len(original_node.args) < 2:
            raise StepNotFoundError("find_element call has no locator pair")
        old_by = _by_literal(original_node.args[0].value)
        old_value = _literal(original_node.args[1].value)
        if old_by != self.old_by or old_value != self.old_value:
            return updated_node
        args = list(updated_node.args)
        args[0] = args[0].with_changes(value=cst.Attribute(value=cst.Name("AppiumBy"), attr=cst.Name(self.by)))
        args[1] = args[1].with_changes(
            value=cst.SimpleString(_preserve_string_literal(args[1].value, self.value))
        )
        self._replaced = True
        return updated_node.with_changes(args=args)

def _parse(source: str) -> cst.Module:
    try:
        return cst.parse_module(source)
    except cst.ParserSyntaxError as error:
        raise StepNotFoundError("Generated script is not valid Python") from error


def _is_find_element(node: cst.Call) -> bool:
    func = node.func
    return (
        isinstance(func, cst.Attribute)
        and func.attr.value == "find_element"
        and isinstance(func.value, cst.Name)
        and func.value.value == "driver"
    )


def _literal(node: cst.BaseExpression) -> str:
    if not isinstance(node, cst.SimpleString):
        raise StepNotFoundError("Locator must use string literals")
    try:
        value = ast.literal_eval(node.value)
    except (ValueError, SyntaxError) as error:
        raise StepNotFoundError("Locator must use a valid string literal") from error
    if not isinstance(value, str):
        raise StepNotFoundError("Locator must use string literals")
    return value


def _by_literal(node: cst.BaseExpression) -> str:
    if isinstance(node, cst.Attribute) and isinstance(node.value, cst.Name):
        if node.value.value == "AppiumBy":
            return node.attr.value
    return _literal(node)


def _preserve_string_literal(node: cst.BaseExpression, value: str) -> str:
    """Use the original quote when it can represent the replacement safely."""
    if isinstance(node, cst.SimpleString) and node.value[:1] in {"'", '"'}:
        quote = node.value[0]
        if quote not in value and "\\" not in value:
            return f"{quote}{value}{quote}"
    return repr(value)


def _step_info(call: cst.Call, action: str | None) -> StepInfo:
    if len(call.args) < 2:
        raise StepNotFoundError("find_element call has no locator pair")
    by = _by_literal(call.args[0].value)
    value = _literal(call.args[1].value)
    return StepInfo(action=action, by=by, value=value)
