"""
Converter module for transforming data between various formats and representations.

This module demonstrates Python's flexible type system with:
- Generic types with covariant/contravariant relationships
- Union types and Optional handling
- Mutable default arguments (Python anti-pattern)
- Duck typing with Protocol classes
- Runtime type flexibility that static typing can't capture
"""

import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar, Union, overload, runtime_checkable

# ============================================================================
# Type Variables with various constraints
# ============================================================================

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)
NumericT = TypeVar("NumericT", int, float, Decimal)
StrOrBytes = TypeVar("StrOrBytes", str, bytes)


# ============================================================================
# Protocol definitions (structural typing)
# ============================================================================


@runtime_checkable
class Convertible(Protocol):
    """Any object that can be converted to an output string."""

    def to_output(self) -> str: ...


@runtime_checkable
class HasSize(Protocol):
    """Any object with a size."""

    def __len__(self) -> int: ...


class OutputConsumer(Protocol[T_contra]):
    """Contravariant consumer that accepts converted outputs."""

    def consume(self, item: T_contra) -> None: ...


# ============================================================================
# Enums and Constants
# ============================================================================


class FormatType(Enum):
    TEXT = "text"
    NUMERIC = "numeric"
    TEMPORAL = "temporal"
    STRUCTURED = "structured"
    BINARY = "binary"
    EMPTY = "empty"


# ============================================================================
# Core Output Classes
# ============================================================================


@dataclass(frozen=True)
class ConvertedOutput:
    """Immutable conversion result."""

    content: str
    format_type: FormatType
    annotations: dict[str, Any] = field(default_factory=dict)

    def with_annotation(self, **kwargs: Any) -> "ConvertedOutput":
        """Return new output with additional annotations."""
        new_annot = {**self.annotations, **kwargs}
        return ConvertedOutput(self.content, self.format_type, new_annot)


@dataclass
class MutableOutputBatch:
    """Mutable batch of outputs - contrast with immutable ConvertedOutput."""

    outputs: list[ConvertedOutput] = field(default_factory=list)
    _finalized: bool = False

    def append(self, output: ConvertedOutput) -> None:
        if self._finalized:
            raise RuntimeError("Batch already finalized")
        self.outputs.append(output)

    def finalize(self) -> None:
        self._finalized = True


# ============================================================================
# Generic Container Classes
# ============================================================================


class OutputContainer(Generic[T_co]):
    """Covariant container - can return subtypes."""

    def __init__(self, items: Sequence[T_co]) -> None:
        self._items: tuple[T_co, ...] = tuple(items)

    def get_all(self) -> tuple[T_co, ...]:
        return self._items

    def map_outputs(self, func: Callable[[T_co], str]) -> list[str]:
        return [func(item) for item in self._items]


class OutputSink(Generic[T_contra]):
    """Contravariant sink - can accept supertypes."""

    def __init__(self) -> None:
        self._collected: list[Any] = []

    def accept(self, item: T_contra) -> None:
        self._collected.append(item)

    def flush(self) -> list[Any]:
        result = self._collected.copy()
        self._collected.clear()
        return result


class InvariantProcessor(Generic[T]):
    """Invariant processor - exact type matching required."""

    def __init__(self, initial: T) -> None:
        self._state: T = initial

    def get(self) -> T:
        return self._state

    def set(self, value: T) -> None:
        self._state = value

    def apply(self, func: Callable[[T], T]) -> T:
        self._state = func(self._state)
        return self._state


# ============================================================================
# Converter Implementations
# ============================================================================


class BaseConverter(ABC, Generic[T]):
    """Abstract base converter with generic input type."""

    @abstractmethod
    def convert(self, value: T) -> ConvertedOutput:
        """Convert value to output."""
        pass

    def convert_batch(self, values: Iterable[T]) -> Iterator[ConvertedOutput]:
        """Lazy conversion of multiple values."""
        for v in values:
            yield self.convert(v)


class TextConverter(BaseConverter[StrOrBytes]):
    """Converter for string and bytes types."""

    def __init__(self, charset: str = "utf-8", transformer: Callable[[str], str] | None = None) -> None:
        self.charset = charset
        self.transformer = transformer or (lambda x: x)

    def convert(self, value: StrOrBytes) -> ConvertedOutput:
        if isinstance(value, bytes):
            str_value = value.decode(self.charset)
        else:
            str_value = value

        transformed = self.transformer(str_value)
        return ConvertedOutput(transformed, FormatType.TEXT)


class NumberConverter(BaseConverter[NumericT]):
    """Converter for numeric types with precision handling."""

    def __init__(
        self,
        decimal_places: int = 4,
        # DANGER: Mutable default argument - Python allows, Scala doesn't
        options: dict[str, Any] = {},  # noqa: B006
    ) -> None:
        self.decimal_places = decimal_places
        self.options = options

    def convert(self, value: NumericT) -> ConvertedOutput:
        if isinstance(value, Decimal):
            str_value = f"{value:.{self.decimal_places}f}"
        elif isinstance(value, float):
            str_value = f"{value:.{self.decimal_places}f}"
        else:
            str_value = str(value)

        return ConvertedOutput(str_value, FormatType.NUMERIC, {"source_type": type(value).__name__})


class DateConverter(BaseConverter[Union[datetime, date]]):  # noqa: UP007
    """Converter for date/time types."""

    ISO_DATETIME = "%Y-%m-%dT%H:%M:%S"
    ISO_DATE = "%Y-%m-%d"

    def __init__(self, pattern: str | None = None) -> None:
        self.pattern = pattern

    def convert(self, value: datetime | date) -> ConvertedOutput:
        if self.pattern:
            fmt = self.pattern
        elif isinstance(value, datetime):
            fmt = self.ISO_DATETIME
        else:
            fmt = self.ISO_DATE

        return ConvertedOutput(value.strftime(fmt), FormatType.TEMPORAL)


# ============================================================================
# Advanced: Union Types and Overloads
# ============================================================================


class CompositeConverter:
    """Converter that handles multiple types with overloaded methods."""

    def __init__(self) -> None:
        self._text_converter = TextConverter()
        self._number_converter = NumberConverter()
        self._date_converter = DateConverter()

    # Overloaded signatures for type-specific behavior
    @overload
    def convert(self, value: str) -> ConvertedOutput: ...
    @overload
    def convert(self, value: bytes) -> ConvertedOutput: ...
    @overload
    def convert(self, value: int) -> ConvertedOutput: ...
    @overload
    def convert(self, value: float) -> ConvertedOutput: ...
    @overload
    def convert(self, value: datetime) -> ConvertedOutput: ...
    @overload
    def convert(self, value: None) -> ConvertedOutput: ...
    @overload
    def convert(self, value: Convertible) -> ConvertedOutput: ...

    def convert(self, value: Any) -> ConvertedOutput:
        """
        Dispatch to appropriate converter based on runtime type.

        Note: Python allows this duck-typing dispatch that Scala's
        static type system would reject without explicit type classes.
        """
        if value is None:
            return ConvertedOutput("EMPTY", FormatType.EMPTY)

        if isinstance(value, Convertible):
            return ConvertedOutput(value.to_output(), FormatType.STRUCTURED)

        if isinstance(value, (str, bytes)):
            return self._text_converter.convert(value)

        if isinstance(value, (int, float, Decimal)):
            return self._number_converter.convert(value)

        if isinstance(value, (datetime, date)):
            return self._date_converter.convert(value)

        # Fallback: try str() conversion
        return ConvertedOutput(str(value), FormatType.TEXT, {"fallback": True})


# ============================================================================
# Complex Nested Generics
# ============================================================================


class ConversionRegistry(Generic[T]):
    """
    Registry with complex nested generic types.

    This pattern is particularly challenging to translate to Scala
    due to the mixing of mutable and immutable collections with generics.
    """

    def __init__(self) -> None:
        # Nested generics with mixed mutability
        self._catalog: dict[str, OutputContainer[T]] = {}
        self._processors: list[Callable[[T], ConvertedOutput | None]] = []

    def register(self, key: str, container: OutputContainer[T]) -> None:
        self._catalog[key] = container

    def add_processor(self, processor: Callable[[T], ConvertedOutput | None]) -> None:
        self._processors.append(processor)

    def execute(self, key: str) -> list[ConvertedOutput | None]:
        """Process all items in a container through all processors."""
        container = self._catalog.get(key)
        if container is None:
            return []

        results: list[ConvertedOutput | None] = []
        for item in container.get_all():
            for processor in self._processors:
                result = processor(item)
                if result is not None:
                    results.append(result)
                    break
            else:
                results.append(None)

        return results


# ============================================================================
# Higher-Kinded Type Simulation
# ============================================================================

F = TypeVar("F")  # Type constructor placeholder


class OutputFunctor(Generic[T]):
    """
    Simulated functor for outputs.

    Python can't express true higher-kinded types (HKT), but Scala can.
    This simulation needs to become a proper type class in Scala.
    """

    def __init__(self, value: T) -> None:
        self._value = value

    def map(self, func: Callable[[T], Any]) -> "OutputFunctor[Any]":
        return OutputFunctor(func(self._value))

    def flat_map(self, func: Callable[[T], "OutputFunctor[Any]"]) -> "OutputFunctor[Any]":
        return func(self._value)

    def get_or_else(self, default: T) -> T:
        return self._value if self._value is not None else default


class OutputMonad(OutputFunctor[T]):
    """Extended monad operations."""

    @classmethod
    def pure(cls, value: T) -> "OutputMonad[T]":
        return cls(value)

    def ap(self, func_wrapped: "OutputMonad[Callable[[T], Any]]") -> "OutputMonad[Any]":
        """Applicative apply."""
        return OutputMonad(func_wrapped._value(self._value))


# ============================================================================
# JSON Structure Conversion
# ============================================================================

JsonValue = Union[str, int, float, bool, None, list["JsonValue"], dict[str, "JsonValue"]]  # noqa UP007


class JsonConverter:
    """
    Converter for JSON structures with recursive types.

    The recursive JsonValue type alias is tricky in Scala
    due to the need for explicit recursive type definitions.
    """

    def __init__(self, indent: bool = False) -> None:
        self.indent = indent

    def convert(self, value: JsonValue) -> ConvertedOutput:
        if self.indent:
            json_str = json.dumps(value, indent=2)
        else:
            json_str = json.dumps(value)

        return ConvertedOutput(json_str, FormatType.STRUCTURED, {"json": True})

    def convert_path(self, value: JsonValue, path: str) -> ConvertedOutput | None:
        """Extract and convert a value at a JSON path."""
        parts = path.split(".")
        current: Any = value

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None

        return self.convert(current)


# ============================================================================
# Delimited Converter - Field-Based Data Conversion
# ============================================================================


class DelimitedConverter:
    """
    Converter that splits text by a delimiter into fields.

    This is a fundamental operation used in CSV/TSV parsing and log processing.
    Demonstrates a simple, practical use case for the converter module.
    """

    def __init__(self, lowercase: bool = False, min_length: int = 0, max_length: int | None = None, strip_quotes: bool = False) -> None:
        """
        Initialize delimited converter with options.

        Args:
            lowercase: Convert all fields to lowercase
            min_length: Minimum field length (shorter fields are filtered out)
            max_length: Maximum field length (longer fields are truncated)
            strip_quotes: Remove leading/trailing quotes from fields
        """
        self.lowercase = lowercase
        self.min_length = min_length
        self.max_length = max_length
        self.strip_quotes = strip_quotes
        self._quote_chars = set("\"'`")

    def _process_field(self, field: str) -> str | None:
        """Process a single field into an output string."""
        if self.strip_quotes:
            field = field.strip("".join(self._quote_chars))

        if self.lowercase:
            field = field.lower()

        if len(field) < self.min_length:
            return None

        if self.max_length is not None and len(field) > self.max_length:
            field = field[: self.max_length]

        return field if field else None

    def convert(self, text: str) -> list[ConvertedOutput]:
        """
        Split text by whitespace and return list of converted outputs.

        Args:
            text: Input text to convert

        Returns:
            List of ConvertedOutput objects, one per field
        """
        fields = text.split()
        outputs: list[ConvertedOutput] = []

        for i, fld in enumerate(fields):
            processed = self._process_field(fld)
            if processed is not None:
                output = ConvertedOutput(content=processed, format_type=FormatType.TEXT, annotations={"index": i, "raw": fld})
                outputs.append(output)

        return outputs

    def convert_to_strings(self, text: str) -> list[str]:
        """
        Split text and return list of output strings.

        Convenience method that returns just the string values.

        Args:
            text: Input text to convert

        Returns:
            List of output strings
        """
        return [o.content for o in self.convert(text)]

    def convert_with_offsets(self, text: str) -> list[tuple[str, int, int]]:
        """
        Convert text and return fields with character offsets.

        Args:
            text: Input text to convert

        Returns:
            List of tuples (field_string, start_offset, end_offset)
        """
        result: list[tuple[str, int, int]] = []
        current_pos = 0

        for field in text.split():
            # Find the actual position in the original text
            start = text.find(field, current_pos)
            end = start + len(field)

            processed = self._process_field(field)
            if processed is not None:
                result.append((processed, start, end))

            current_pos = end

        return result

    def count_fields(self, text: str) -> int:
        """Return the number of fields in the text."""
        return len(self.convert(text))


# ============================================================================
# Builder Pattern with Fluent Interface
# ============================================================================


class ConverterPipeline(Generic[T]):
    """
    Fluent pipeline for creating converters.

    The method chaining with generic return types requires
    careful handling of type bounds in Scala.
    """

    def __init__(self) -> None:
        self._transformers: list[Callable[[str], str]] = []
        self._guards: list[Callable[[T], bool]] = []
        self._annotations: dict[str, Any] = {}

    def with_transformer(self, transformer: Callable[[str], str]) -> "ConverterPipeline[T]":
        self._transformers.append(transformer)
        return self

    def with_guard(self, guard: Callable[[T], bool]) -> "ConverterPipeline[T]":
        self._guards.append(guard)
        return self

    def with_annotation(self, **kwargs: Any) -> "ConverterPipeline[T]":
        self._annotations.update(kwargs)
        return self

    def build(self) -> Callable[[T], ConvertedOutput]:
        """Build the final converter function."""
        transformers = self._transformers.copy()
        guards = self._guards.copy()
        annotations = self._annotations.copy()

        def convert(value: T) -> ConvertedOutput:
            # Guard checks
            for guard in guards:
                if not guard(value):
                    raise ValueError(f"Guard check failed for {value}")

            # Convert to string
            str_value = str(value)

            # Apply transformers
            for transformer in transformers:
                str_value = transformer(str_value)

            return ConvertedOutput(str_value, FormatType.TEXT, annotations)

        return convert
