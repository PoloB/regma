"""Benchmark regma."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from regma import TemplateModel
from regma import integer
from regma import reference
from regma import string

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def _create_model() -> type[TemplateModel]:

    class BenchmarkModel1(TemplateModel):
        __template__ = "{foo}_{bar}"
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: int = integer(0, 9999, 4)

    return BenchmarkModel1


def _create_reference_model() -> type[TemplateModel]:

    model1 = _create_model()

    class BenchmarkModel2(TemplateModel):
        __template__ = "{foo_bar}_{foo_bar.bar}_{foo_bar.foo}_{foo}_{bar}"
        foo_bar: TemplateModel = reference(model1)
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: int = integer(0, 9999, 4)

    return BenchmarkModel2


def test_benchmark_simple_model_definition(benchmark: BenchmarkFixture) -> None:
    """Benchmark the definition of a simple model."""
    benchmark(_create_model)


def test_benchmark_reference_model(benchmark: BenchmarkFixture) -> None:
    """Benchmark the definition of a simple model."""
    benchmark(_create_reference_model)


def test_benchmark_simple_model_instantiation(benchmark: BenchmarkFixture) -> None:
    """Benchmark the instantiation of a simple model."""
    benchmark(functools.partial(_create_model(), "test", 1))


def test_benchmark_parse(benchmark: BenchmarkFixture) -> None:
    """Benchmark the parsing of a string through a model."""
    benchmark(_create_reference_model().parse, "test_0042_0042_test_other_0001")


def test_benchmark_format(benchmark: BenchmarkFixture) -> None:
    """Benchmark the format of a model."""
    model = _create_model()("test", 42)
    model_reference = _create_reference_model()(model, "other", 1)
    benchmark(model_reference.format)
