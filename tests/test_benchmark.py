"""Benchmark regma."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from regma import Model
from regma import integer
from regma import reference
from regma import string
from regma.template import model_template

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def _create_model() -> type[Model]:

    class _BenchmarkModel1(Model):
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: int = integer(0, 9999, 4)

        template = model_template("{foo}_{bar}")

    return _BenchmarkModel1


def _create_reference_model() -> type[Model]:

    model1 = _create_model()

    class _BenchmarkModel2(Model):
        foo_bar: Model = reference(model1)
        foo: str = string(r"[a-zA-Z0-9]+")
        bar: int = integer(0, 9999, 4)

        template = model_template(
            "{foo_bar.template}_{foo_bar.bar}_{foo_bar.foo}_{foo}_{bar}"
        )

    return _BenchmarkModel2


class BenchmarkModel1(Model):
    """Test model for benchmark."""

    foo: str = string(r"[a-zA-Z0-9]+")
    bar: int = integer(0, 9999, 4)

    template = model_template("{foo}_{bar}")


class BenchmarkModel2(Model):
    """Test model for benchmark."""

    foo_bar: BenchmarkModel1
    foo: str = string(r"[a-zA-Z0-9]+")
    bar: int = integer(0, 9999, 4)

    template = model_template(
        "{foo_bar.template}_{foo_bar.bar}_{foo_bar.foo}_{foo}_{bar}"
    )


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
    benchmark(BenchmarkModel2.template.parse, "test_0042_0042_test_other_0001")


def test_benchmark_format(benchmark: BenchmarkFixture) -> None:
    """Benchmark the format of a model."""
    model = BenchmarkModel1("test", 42)
    model_reference = BenchmarkModel2(model, "other", 1)
    benchmark(lambda: model_reference.template)
