package converter

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import org.scalatest.BeforeAndAfterEach

import java.time.{LocalDate, LocalDateTime}
import io.circe.parser._
import io.circe.syntax._
import io.circe.Json

class ConverterSpec extends AnyFlatSpec with Matchers with BeforeAndAfterEach {

  // ============================================================================
  // FormatType Tests
  // ============================================================================

  "FormatType" should "have correct string values" in {
    FormatType.TEXT.value shouldBe "text"
    FormatType.NUMERIC.value shouldBe "numeric"
    FormatType.TEMPORAL.value shouldBe "temporal"
    FormatType.STRUCTURED.value shouldBe "structured"
    FormatType.BINARY.value shouldBe "binary"
    FormatType.EMPTY.value shouldBe "empty"
  }


  // ============================================================================
  // ConvertedOutput Tests
  // ============================================================================

  "ConvertedOutput" should "be immutable and create new instances with annotations" in {
    val output = ConvertedOutput("sample", FormatType.TEXT)
    val annotated = output.withAnnotation("source" -> "test")

    output.annotations shouldBe empty
    annotated.annotations should contain ("source" -> "test")
    output should not be theSameInstanceAs(annotated)
  }


  // ============================================================================
  // OutputContainer Tests (Covariant)
  // ============================================================================

  "OutputContainer" should "store and retrieve items" in {
    val container = new OutputContainer(Seq("x", "y", "z"))

    container.getAll shouldBe Vector("x", "y", "z")
    container.size shouldBe 3
  }


  // ============================================================================
  // CompositeConverter Tests
  // ============================================================================

  "CompositeConverter" should "convert empty values" in {
    val conv = new CompositeConverter()
    val output = conv.convertEmpty

    output.content shouldBe "EMPTY"
    output.formatType shouldBe FormatType.EMPTY
  }

  it should "convert datetime" in {
    val conv = new CompositeConverter()
    val dt = LocalDateTime.of(2025, 3, 20, 14, 45, 0)
    val output = conv.convert(dt)

    output.formatType shouldBe FormatType.TEMPORAL
    output.content should include ("2025-03-20")
  }


  // ============================================================================
  // ConversionRegistry Tests
  // ============================================================================

  "ConversionRegistry" should "register and execute on containers" in {
    val registry = new ConversionRegistry[String]
    val container = new OutputContainer(Seq("alpha", "beta"))

    registry.register("items", container)
    registry.addProcessor { s =>
      Some(ConvertedOutput(s.reverse, FormatType.TEXT))
    }

    val results = registry.execute("items")
    results should have size 2
    results.flatten.map(_.content) shouldBe List("ahpla", "ateb")
  }


  // ============================================================================
  // OutputFunctor Tests
  // ============================================================================

  "OutputFunctor" should "map values" in {
    val functor = new OutputFunctor(7)
    val mapped = functor.map(_ + 3)

    mapped.get shouldBe 10
  }


  // ============================================================================
  // JsonConverter Tests
  // ============================================================================

  "JsonConverter" should "convert JSON values" in {
    val conv = new JsonConverter()
    val json = parse("""{"name": "alice"}""").getOrElse(Json.Null)
    val output = conv.convert(json)

    output.formatType shouldBe FormatType.STRUCTURED
    output.annotations should contain ("json" -> true)
    output.content should include ("name")
  }


  // ============================================================================
  // DelimitedConverter Tests
  // ============================================================================

  "DelimitedConverter" should "combine multiple options" in {
    val conv = new DelimitedConverter(
      lowercase = true,
      minLength = 3,
      maxLength = Some(5),
      stripQuotes = true
    )
    val outputs = conv.convert("\"Hi\" 'Welcome!' GREAT...")

    outputs.map(_.content) shouldBe List("welco", "great")
  }

  // ============================================================================
  // ConverterPipeline Tests
  // ============================================================================

  "ConverterPipeline" should "chain multiple operations fluently" in {
    val converter = ConverterPipeline[String]()
      .withTransformer(_.toUpperCase)
      .withTransformer(_.replace(" ", "-"))
      .withGuard(_.nonEmpty)
      .withAnnotation("origin" -> "pipeline")
      .build()

    val output = converter("foo bar")
    output.content shouldBe "FOO-BAR"
    output.annotations should contain ("origin" -> "pipeline")
  }

}
