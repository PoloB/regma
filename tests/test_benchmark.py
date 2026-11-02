"""Benchmark regma."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from regma import Template
from regma import integer
from regma import string

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def _create_simple_template() -> Template:
    return Template("{foo}_{bar}", foo=string(r"\w+"), bar=integer(0, 9999, 4))


def _create_nested_template() -> Template:
    foo_bar = Template("{foo}_{bar}", foo=string(r"\w+"), bar=integer(0, 9999, 4))
    return Template(
        "{foo_bar}_{foo_bar.bar}_{foo_bar.foo}_{foo}_{bar}",
        foo_bar=foo_bar,
        foo=string(r"\w+"),
        bar=integer(0, 9999, 4),
    )


def test_benchmark_simple_template_definition(benchmark: BenchmarkFixture) -> None:
    """Benchmark the definition of a simple model."""
    benchmark(_create_simple_template)


def test_benchmark_nested_template_definition(benchmark: BenchmarkFixture) -> None:
    """Benchmark the definition of a simple model."""
    benchmark(_create_nested_template)


def test_benchmark_template_parse(benchmark: BenchmarkFixture) -> None:
    """Benchmark the parsing of a string through a model."""
    template = _create_nested_template()
    benchmark(template.parse, "test_0042_0042_test_other_0001")


def test_benchmark_format(benchmark: BenchmarkFixture) -> None:
    """Benchmark the format of a model."""
    template = _create_nested_template()
    data = {"foo_bar": {"foo": "test", "bar": 42}, "foo": "other", "bar": 1}
    func = functools.partial(template.format, data)
    benchmark(func)
