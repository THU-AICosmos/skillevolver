#!/bin/bash
# Use this file to solve the task.
COMPOSE_BAKE=true
set -e

cat <<'EOF' > Converter.scala
package converter
/**
 * Converter module for transforming data between various formats and representations.
 *
 * This module demonstrates Scala's type system with:
 * - Generic types with covariant/contravariant relationships
 * - Union types via Either and sealed traits
 * - Proper immutability patterns
 * - Structural typing via type classes
 * - Compile-time type safety
 */
import java.time.{LocalDate, LocalDateTime}
import java.time.format.DateTimeFormatter
import scala.collection.mutable
import scala.util.{Try, Success, Failure}
import io.circe._
import io.circe.syntax._
import io.circe.parser._
// ============================================================================
// Protocol definitions (type classes - Scala's structural typing)
// ============================================================================
/**
 * Type class for any object that can produce an output string.
 * This is the Scala equivalent of Python's Protocol/duck typing.
 */
trait Convertible[A] {
  def toOutput(a: A): String
}
object Convertible {
  def apply[A](implicit ev: Convertible[A]): Convertible[A] = ev
  // Syntax extension for cleaner usage
  implicit class ConvertibleOps[A](val a: A) extends AnyVal {
    def toOutput(implicit ev: Convertible[A]): String = ev.toOutput(a)
  }
  // Default instances
  implicit val stringConvertible: Convertible[String] = (a: String) => a
  implicit val intConvertible: Convertible[Int] = (a: Int) => a.toString
  implicit val doubleConvertible: Convertible[Double] = (a: Double) => a.toString
  implicit val boolConvertible: Convertible[Boolean] = (a: Boolean) => a.toString
}
/**
 * Type class for objects with a size.
 */
trait HasSize[A] {
  def size(a: A): Int
}
object HasSize {
  implicit val stringHasSize: HasSize[String] = (a: String) => a.length
  implicit def seqHasSize[T]: HasSize[Seq[T]] = (a: Seq[T]) => a.length
}
/**
 * Contravariant consumer that accepts converted outputs.
 */
trait OutputConsumer[-A] {
  def consume(item: A): Unit
}
// ============================================================================
// Enums and Constants
// ============================================================================
/**
 * Format type enumeration.
 */
sealed trait FormatType {
  def value: String
}
object FormatType {
  case object TEXT extends FormatType { val value = "text" }
  case object NUMERIC extends FormatType { val value = "numeric" }
  case object TEMPORAL extends FormatType { val value = "temporal" }
  case object STRUCTURED extends FormatType { val value = "structured" }
  case object BINARY extends FormatType { val value = "binary" }
  case object EMPTY extends FormatType { val value = "empty" }
  val values: Seq[FormatType] = Seq(TEXT, NUMERIC, TEMPORAL, STRUCTURED, BINARY, EMPTY)
  def fromString(s: String): Option[FormatType] = values.find(_.value == s)
}
// ============================================================================
// Core Output Classes
// ============================================================================
/**
 * Immutable conversion result.
 * Scala case classes are naturally immutable, unlike Python dataclasses.
 */
final case class ConvertedOutput(
  content: String,
  formatType: FormatType,
  annotations: Map[String, Any] = Map.empty
) {
  /**
   * Return new output with additional annotations.
   */
  def withAnnotation(newAnnot: (String, Any)*): ConvertedOutput =
    copy(annotations = annotations ++ newAnnot.toMap)
}
/**
 * Mutable batch of outputs - contrast with immutable ConvertedOutput.
 * Uses Scala's mutable collections explicitly.
 */
final class MutableOutputBatch {
  private val _outputs: mutable.ListBuffer[ConvertedOutput] = mutable.ListBuffer.empty
  private var _finalized: Boolean = false
  def outputs: List[ConvertedOutput] = _outputs.toList
  def append(output: ConvertedOutput): Unit = {
    if (_finalized) {
      throw new RuntimeException("Batch already finalized")
    }
    _outputs += output
  }
  def markFinalized(): Unit = {
    _finalized = true
  }
  def isFinalized: Boolean = _finalized
}
// ============================================================================
// Generic Container Classes
// ============================================================================
/**
 * Covariant container - can return subtypes.
 * The +A indicates covariance in Scala.
 */
class OutputContainer[+A](items: Seq[A]) {
  private val _items: Vector[A] = items.toVector
  def getAll: Vector[A] = _items
  def mapOutputs[B](func: A => B): Vector[B] = _items.map(func)
  def size: Int = _items.size
}
/**
 * Contravariant sink - can accept supertypes.
 * The -A indicates contravariance in Scala.
 */
class OutputSink[-A] {
  private val _collected: mutable.ListBuffer[Any] = mutable.ListBuffer.empty
  def accept(item: A): Unit = {
    _collected += item
  }
  def flush(): List[Any] = {
    val result = _collected.toList
    _collected.clear()
    result
  }
}
/**
 * Invariant processor - exact type matching required.
 * No variance annotation means invariant.
 */
class InvariantProcessor[A](private var _state: A) {
  def get: A = _state
  def set(value: A): Unit = {
    _state = value
  }
  def apply(func: A => A): A = {
    _state = func(_state)
    _state
  }
}
// ============================================================================
// Converter Implementations
// ============================================================================
/**
 * Abstract base converter with generic input type.
 */
abstract class BaseConverter[A] {
  def convert(value: A): ConvertedOutput
  /**
   * Lazy conversion of multiple values using Scala's Iterator.
   */
  def convertBatch(values: Iterable[A]): Iterator[ConvertedOutput] =
    values.iterator.map(convert)
}
/**
 * Union type for String or Array[Byte].
 * Scala doesn't have Python's Union, so we use a sealed trait.
 */
sealed trait StrOrBytes {
  def asString(charset: String): String
}
object StrOrBytes {
  final case class Str(value: String) extends StrOrBytes {
    def asString(charset: String): String = value
  }
  final case class Bytes(value: Array[Byte]) extends StrOrBytes {
    def asString(charset: String): String = new String(value, charset)
  }
  // Implicit conversions for convenience
  implicit def fromString(s: String): StrOrBytes = Str(s)
  implicit def fromBytes(b: Array[Byte]): StrOrBytes = Bytes(b)
}
/**
 * Converter for string and bytes types.
 */
class TextConverter(
  charset: String = "UTF-8",
  transformer: String => String = identity
) extends BaseConverter[StrOrBytes] {
  override def convert(value: StrOrBytes): ConvertedOutput = {
    val strValue = value.asString(charset)
    val transformed = transformer(strValue)
    ConvertedOutput(transformed, FormatType.TEXT)
  }
  // Convenience method for direct string conversion
  def convertString(value: String): ConvertedOutput =
    convert(StrOrBytes.Str(value))
}
/**
 * Numeric value wrapper for conversion.
 * Scala uses BigDecimal instead of Python's Decimal.
 */
sealed trait NumericValue {
  def typeName: String
}
object NumericValue {
  final case class IntValue(value: Int) extends NumericValue {
    val typeName = "Int"
  }
  final case class LongValue(value: Long) extends NumericValue {
    val typeName = "Long"
  }
  final case class FloatValue(value: Float) extends NumericValue {
    val typeName = "Float"
  }
  final case class DoubleValue(value: Double) extends NumericValue {
    val typeName = "Double"
  }
  final case class BigDecimalValue(value: BigDecimal) extends NumericValue {
    val typeName = "BigDecimal"
  }
  // Implicit conversions
  implicit def fromInt(i: Int): NumericValue = IntValue(i)
  implicit def fromLong(l: Long): NumericValue = LongValue(l)
  implicit def fromFloat(f: Float): NumericValue = FloatValue(f)
  implicit def fromDouble(d: Double): NumericValue = DoubleValue(d)
  implicit def fromBigDecimal(bd: BigDecimal): NumericValue = BigDecimalValue(bd)
}
/**
 * Converter for numeric types with precision handling.
 *
 * Note: Unlike Python, Scala doesn't allow mutable default arguments,
 * so we use immutable Map by default.
 */
class NumberConverter(
  decimalPlaces: Int = 4,
  options: Map[String, Any] = Map.empty
) extends BaseConverter[NumericValue] {
  private val formatString = s"%.${decimalPlaces}f"
  override def convert(value: NumericValue): ConvertedOutput = {
    val strValue = value match {
      case NumericValue.BigDecimalValue(bd) =>
        bd.setScale(decimalPlaces, BigDecimal.RoundingMode.HALF_UP).toString()
      case NumericValue.DoubleValue(d) =>
        formatString.format(d)
      case NumericValue.FloatValue(f) =>
        formatString.format(f)
      case NumericValue.IntValue(i) =>
        i.toString
      case NumericValue.LongValue(l) =>
        l.toString
    }
    ConvertedOutput(strValue, FormatType.NUMERIC, Map("source_type" -> value.typeName))
  }
  // Convenience methods for direct numeric conversion
  def convertInt(value: Int): ConvertedOutput = convert(NumericValue.IntValue(value))
  def convertDouble(value: Double): ConvertedOutput = convert(NumericValue.DoubleValue(value))
  def convertBigDecimal(value: BigDecimal): ConvertedOutput = convert(NumericValue.BigDecimalValue(value))
}
/**
 * Temporal value wrapper.
 */
sealed trait TemporalValue
object TemporalValue {
  final case class DateTime(value: LocalDateTime) extends TemporalValue
  final case class Date(value: LocalDate) extends TemporalValue
  implicit def fromLocalDateTime(dt: LocalDateTime): TemporalValue = DateTime(dt)
  implicit def fromLocalDate(d: LocalDate): TemporalValue = Date(d)
}
/**
 * Converter for date/time types.
 */
class DateConverter(
  pattern: Option[String] = None
) extends BaseConverter[TemporalValue] {
  private val IsoDateTimeFormat = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")
  private val IsoDateFormat = DateTimeFormatter.ofPattern("yyyy-MM-dd")
  override def convert(value: TemporalValue): ConvertedOutput = {
    val formatter = pattern match {
      case Some(fmt) => DateTimeFormatter.ofPattern(fmt)
      case None => value match {
        case _: TemporalValue.DateTime => IsoDateTimeFormat
        case _: TemporalValue.Date => IsoDateFormat
      }
    }
    val strValue = value match {
      case TemporalValue.DateTime(dt) => dt.format(formatter)
      case TemporalValue.Date(d) => d.format(formatter)
    }
    ConvertedOutput(strValue, FormatType.TEMPORAL)
  }
  // Convenience methods
  def convertDateTime(value: LocalDateTime): ConvertedOutput =
    convert(TemporalValue.DateTime(value))
  def convertDate(value: LocalDate): ConvertedOutput =
    convert(TemporalValue.Date(value))
}
// ============================================================================
// Advanced: Union Types via Sealed Traits
// ============================================================================
/**
 * Universal convertible value - Scala's approach to Python's Union type.
 */
sealed trait ConvertibleValue
object ConvertibleValue {
  final case class StringVal(value: String) extends ConvertibleValue
  final case class BytesVal(value: Array[Byte]) extends ConvertibleValue
  final case class IntVal(value: Int) extends ConvertibleValue
  final case class LongVal(value: Long) extends ConvertibleValue
  final case class DoubleVal(value: Double) extends ConvertibleValue
  final case class BigDecimalVal(value: BigDecimal) extends ConvertibleValue
  final case class DateTimeVal(value: LocalDateTime) extends ConvertibleValue
  final case class DateVal(value: LocalDate) extends ConvertibleValue
  final case class CustomVal[A](value: A)(implicit ev: Convertible[A]) extends ConvertibleValue {
    def toOutput: String = ev.toOutput(value)
  }
  case object EmptyVal extends ConvertibleValue
  // Implicit conversions
  implicit def fromString(s: String): ConvertibleValue = StringVal(s)
  implicit def fromInt(i: Int): ConvertibleValue = IntVal(i)
  implicit def fromDouble(d: Double): ConvertibleValue = DoubleVal(d)
  implicit def fromDateTime(dt: LocalDateTime): ConvertibleValue = DateTimeVal(dt)
}
/**
 * Converter that handles multiple types with pattern matching.
 * This is Scala's idiomatic approach to Python's overloaded methods.
 */
class CompositeConverter {
  private val textConverter = new TextConverter()
  private val numberConverter = new NumberConverter()
  private val dateConverter = new DateConverter()
  /**
   * Dispatch to appropriate converter based on the value type.
   * Scala's pattern matching provides compile-time exhaustiveness checking,
   * unlike Python's runtime isinstance checks.
   */
  def convert(value: ConvertibleValue): ConvertedOutput = value match {
    case ConvertibleValue.EmptyVal =>
      ConvertedOutput("EMPTY", FormatType.EMPTY)
    case ConvertibleValue.StringVal(s) =>
      textConverter.convertString(s)
    case ConvertibleValue.BytesVal(b) =>
      textConverter.convert(StrOrBytes.Bytes(b))
    case ConvertibleValue.IntVal(i) =>
      numberConverter.convertInt(i)
    case ConvertibleValue.LongVal(l) =>
      numberConverter.convert(NumericValue.LongValue(l))
    case ConvertibleValue.DoubleVal(d) =>
      numberConverter.convertDouble(d)
    case ConvertibleValue.BigDecimalVal(bd) =>
      numberConverter.convertBigDecimal(bd)
    case ConvertibleValue.DateTimeVal(dt) =>
      dateConverter.convertDateTime(dt)
    case ConvertibleValue.DateVal(d) =>
      dateConverter.convertDate(d)
    case c: ConvertibleValue.CustomVal[_] =>
      ConvertedOutput(c.toOutput, FormatType.STRUCTURED)
  }
  // Convenience overloads for common types
  def convert(value: String): ConvertedOutput = convert(ConvertibleValue.StringVal(value))
  def convert(value: Int): ConvertedOutput = convert(ConvertibleValue.IntVal(value))
  def convert(value: Double): ConvertedOutput = convert(ConvertibleValue.DoubleVal(value))
  def convert(value: LocalDateTime): ConvertedOutput = convert(ConvertibleValue.DateTimeVal(value))
  def convert(value: LocalDate): ConvertedOutput = convert(ConvertibleValue.DateVal(value))
  def convertEmpty: ConvertedOutput = convert(ConvertibleValue.EmptyVal)
}
// ============================================================================
// Complex Nested Generics
// ============================================================================
/**
 * Registry with complex nested generic types.
 *
 * In Scala, we maintain explicit type safety throughout,
 * unlike Python's runtime type flexibility.
 */
class ConversionRegistry[A] {
  private val _catalog: mutable.Map[String, OutputContainer[A]] = mutable.Map.empty
  private val _processors: mutable.ListBuffer[A => Option[ConvertedOutput]] = mutable.ListBuffer.empty
  def register(key: String, container: OutputContainer[A]): Unit = {
    _catalog(key) = container
  }
  def addProcessor(processor: A => Option[ConvertedOutput]): Unit = {
    _processors += processor
  }
  /**
   * Process all items in a container through all processors.
   */
  def execute(key: String): List[Option[ConvertedOutput]] = {
    _catalog.get(key) match {
      case None => Nil
      case Some(container) =>
        container.getAll.map { item =>
          _processors.iterator.map(_(item)).find(_.isDefined).flatten
        }.toList
    }
  }
}
// ============================================================================
// Higher-Kinded Type Simulation / Functor & Monad
// ============================================================================
/**
 * Functor for outputs.
 *
 * Scala can express true higher-kinded types, making this a proper functor.
 */
class OutputFunctor[A](protected val _value: A) {
  def map[B](func: A => B): OutputFunctor[B] =
    new OutputFunctor(func(_value))
  def flatMap[B](func: A => OutputFunctor[B]): OutputFunctor[B] =
    func(_value)
  def getOrElse(default: => A): A =
    if (_value != null) _value else default
  def get: A = _value
}
/**
 * Monad for outputs with extended operations.
 */
class OutputMonad[A](value: A) extends OutputFunctor[A](value) {
  override def map[B](func: A => B): OutputMonad[B] =
    new OutputMonad(func(_value))
  override def flatMap[B](func: A => OutputFunctor[B]): OutputMonad[B] =
    func(_value) match {
      case om: OutputMonad[B @unchecked] => om
      case of => new OutputMonad(of.get)
    }
  /**
   * Applicative apply.
   */
  def ap[B](funcWrapped: OutputMonad[A => B]): OutputMonad[B] =
    new OutputMonad(funcWrapped._value(_value))
}
object OutputMonad {
  def pure[A](value: A): OutputMonad[A] = new OutputMonad(value)
}
// ============================================================================
// JSON Structure Conversion
// ============================================================================
/**
 * Converter for JSON structures using Circe.
 *
 * Circe provides type-safe JSON handling in Scala,
 * unlike Python's dynamic json module.
 */
class JsonConverter(indent: Boolean = false) {
  def convert(value: Json): ConvertedOutput = {
    val jsonStr = if (indent) {
      value.spaces2
    } else {
      value.noSpaces
    }
    ConvertedOutput(jsonStr, FormatType.STRUCTURED, Map("json" -> true))
  }
  /**
   * Parse and convert a JSON string.
   */
  def convertString(jsonString: String): Either[ParsingFailure, ConvertedOutput] = {
    parse(jsonString).map(convert)
  }
  /**
   * Extract and convert a value at a JSON path.
   */
  def convertPath(value: Json, path: String): Option[ConvertedOutput] = {
    val parts = path.split('.')
    def navigate(current: Json, remainingParts: List[String]): Option[Json] = {
      remainingParts match {
        case Nil => Some(current)
        case part :: rest =>
          if (part.forall(_.isDigit)) {
            // Array index
            val idx = part.toInt
            current.asArray.flatMap(_.lift(idx)).flatMap(navigate(_, rest))
          } else {
            // Object key
            current.asObject.flatMap(_.apply(part)).flatMap(navigate(_, rest))
          }
      }
    }
    navigate(value, parts.toList).map(convert)
  }
}
// ============================================================================
// Delimited Converter - Field-Based Data Conversion
// ============================================================================
/**
 * Converter that splits text by whitespace into fields.
 *
 * This is a fundamental operation used in CSV/TSV parsing and log processing.
 */
class DelimitedConverter(
  lowercase: Boolean = false,
  minLength: Int = 0,
  maxLength: Option[Int] = None,
  stripQuotes: Boolean = false
) {
  private val quoteChars: Set[Char] = Set('"', '\'', '`')
  private def processField(field: String): Option[String] = {
    var processed = field
    if (stripQuotes) {
      processed = processed.dropWhile(quoteChars.contains).reverse.dropWhile(quoteChars.contains).reverse
    }
    if (lowercase) {
      processed = processed.toLowerCase
    }
    if (processed.length < minLength) {
      return None
    }
    maxLength.foreach { max =>
      if (processed.length > max) {
        processed = processed.take(max)
      }
    }
    if (processed.isEmpty) None else Some(processed)
  }
  /**
   * Split text by whitespace and return list of converted outputs.
   */
  def convert(text: String): List[ConvertedOutput] = {
    val fields = text.split("\\s+").toList.filter(_.nonEmpty)
    fields.zipWithIndex.flatMap { case (fld, i) =>
      processField(fld).map { processed =>
        ConvertedOutput(
          content = processed,
          formatType = FormatType.TEXT,
          annotations = Map("index" -> i, "raw" -> fld)
        )
      }
    }
  }
  /**
   * Convenience method that returns just the string values.
   */
  def convertToStrings(text: String): List[String] =
    convert(text).map(_.content)
  /**
   * Convert text and return fields with character offsets.
   */
  def convertWithOffsets(text: String): List[(String, Int, Int)] = {
    val fields = text.split("\\s+").toList.filter(_.nonEmpty)
    var currentPos = 0
    fields.flatMap { fld =>
      val start = text.indexOf(fld, currentPos)
      val end = start + fld.length
      currentPos = end
      processField(fld).map(processed => (processed, start, end))
    }
  }
  /**
   * Return the number of fields in the text.
   */
  def countFields(text: String): Int = convert(text).size
}
// ============================================================================
// Builder Pattern with Fluent Interface
// ============================================================================
/**
 * Fluent pipeline for creating converters.
 *
 * Scala's type system allows for type-safe method chaining.
 */
class ConverterPipeline[A] {
  private val _transformers: mutable.ListBuffer[String => String] = mutable.ListBuffer.empty
  private val _guards: mutable.ListBuffer[A => Boolean] = mutable.ListBuffer.empty
  private var _annotations: Map[String, Any] = Map.empty
  def withTransformer(transformer: String => String): ConverterPipeline[A] = {
    _transformers += transformer
    this
  }
  def withGuard(guard: A => Boolean): ConverterPipeline[A] = {
    _guards += guard
    this
  }
  def withAnnotation(annot: (String, Any)*): ConverterPipeline[A] = {
    _annotations = _annotations ++ annot.toMap
    this
  }
  /**
   * Build the final converter function.
   */
  def build(): A => ConvertedOutput = {
    val transformers = _transformers.toList
    val guards = _guards.toList
    val annotations = _annotations
    (value: A) => {
      // Guard checks
      guards.foreach { guard =>
        if (!guard(value)) {
          throw new IllegalArgumentException(s"Guard check failed for $value")
        }
      }
      // Convert to string
      var strValue = value.toString
      // Apply transformers
      transformers.foreach { transformer =>
        strValue = transformer(strValue)
      }
      ConvertedOutput(strValue, FormatType.TEXT, annotations)
    }
  }
}
object ConverterPipeline {
  def apply[A](): ConverterPipeline[A] = new ConverterPipeline[A]()
}
EOF
