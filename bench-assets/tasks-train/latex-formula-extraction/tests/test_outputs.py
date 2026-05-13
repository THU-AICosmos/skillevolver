"""
Tests for latex-formula-extraction training variant (statistical learning paper).

Verifies that the agent writes all standalone LaTeX formulas extracted from
stat_learning_paper.pdf to /root/extracted_stat_formulas.md, one per line
wrapped in $$ delimiters.
"""

import io
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ANSWER_FILE = Path("/root/extracted_stat_formulas.md")
PDF_FILE = Path("/root/stat_learning_paper.pdf")
MARKER_TIMEOUT = 120
EXPECTED_FORMULAS = [
    r"$$D_{\mathrm{KL}}(P \| Q) = \int_{-\infty}^{\infty} p(x) \ln \frac{p(x)}{q(x)} \, dx$$",
    r"$$\sigma(\mathbf{z})_k = \frac{e^{z_k}}{\sum_{j=1}^{K} e^{z_j}}$$",
    r"$$\mathcal{L}(\theta) = -\frac{1}{N} \sum_{i=1}^{N} \left\{ y_i \log \hat{y}_i + (1 - y_i) \log(1 - \hat{y}_i) \right]$$",
    r"$$\theta_{t+1} = \theta_t - \eta \nabla_\theta \mathbb{E}_{(x,y) \sim \mathcal{D}} \left[ \ell(f_\theta(x), y) \right]$$",
    r"$$I(X; Y) = \sum_{x \in \mathcal{X}} \sum_{y \in \mathcal{Y}} p(x, y) \log \frac{p(x, y)}{p(x)\, p(y)}$$",
    r"$$f(x \mid \mu, \sigma^2) = \frac{1}{\sqrt{2\pi\sigma^2}} \exp\!\left( -\frac{(x - \mu)^2}{2\sigma^2} \right)$$",
    r"$$\mathcal{L}(\theta) = -\frac{1}{N} \sum_{i=1}^{N} \left\{ y_i \log \hat{y}_i + (1 - y_i) \log(1 - \hat{y}_i) \right\}$$",
]


def _locate_markdown_outputs(folder: Path) -> list[Path]:
    """Return all markdown files beneath folder, sorted for deterministic selection."""
    return sorted(p for p in folder.rglob("*.md") if p.is_file())


def _invoke_marker(source: Path, out_dir: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    cmd = [
        "marker_single",
        str(source),
        "--output_format",
        "markdown",
        "--disable_image_extraction",
        "--output_dir",
        str(out_dir),
    ]
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"marker_single exited {exc.returncode}\nstdout:\n{exc.stdout}\n\nstderr:\n{exc.stderr}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"marker_single timed out after {timeout}s") from exc


def _pick_markdown(out_dir: Path, stem: str, stdout: str) -> Path:
    """Select the primary markdown output; prefer file matching the PDF stem."""
    preferred = out_dir / stem / f"{stem}.md"
    if preferred.exists():
        return preferred
    candidates = _locate_markdown_outputs(out_dir)
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"No markdown output in {out_dir}; marker stdout:\n{stdout}")


def convert_pdf_to_md(pdf_path: str, *, timeout: int = MARKER_TIMEOUT, cleanup: bool = True) -> str:
    """Run marker_single on the given PDF and return the generated Markdown."""
    source = Path(pdf_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"PDF not found: {source}")
    if shutil.which("marker_single") is None:
        raise RuntimeError("marker_single CLI not found. Install marker-pdf to proceed.")

    def _convert(out_dir: Path) -> str:
        result = _invoke_marker(source, out_dir, timeout)
        md_path = _pick_markdown(out_dir, source.stem, result.stdout)
        return md_path.read_text(encoding="utf-8")

    if cleanup:
        with tempfile.TemporaryDirectory(prefix="marker_out_") as tmpdir:
            return _convert(Path(tmpdir))
    out_dir = source.parent / f"{source.stem}_marker"
    out_dir.mkdir(exist_ok=True)
    return _convert(out_dir)


def gather_formulas_from_md(markdown: str) -> list[str]:
    """
    Extract formulas, merging $$ / body / $$ triples into a single line and
    cleaning marker-added numbering.
    """
    lines = markdown.splitlines()
    collected: list[str] = []
    idx = 0
    while idx < len(lines):
        stripped = lines[idx].strip()

        if stripped == "$$" and idx + 2 < len(lines):
            body = lines[idx + 1].strip()
            closer = lines[idx + 2].strip()
            if closer == "$$":
                cleaned = _sanitize_formula(body)
                if cleaned:
                    collected.append(f"$${cleaned}$$")
                idx += 3
                continue

        if stripped.startswith("$$") and stripped.endswith("$$"):
            inner = stripped[2:-2].strip()
            cleaned = _sanitize_formula(inner)
            if cleaned:
                collected.append(f"$${cleaned}$$")

        idx += 1

    return collected


def read_formulas(path: Path) -> list[str]:
    """Read non-empty lines from a markdown file."""
    if not path.exists():
        raise FileNotFoundError(f"Answer file not found at {path}")
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _sanitize_formula(content: str) -> str:
    """Remove numbering noise and normalize whitespace without altering math."""
    cleaned = re.sub(r"\\tag\{[^}]*\}", "", content)
    cleaned = re.sub(r"\\(?:quad|qquad)\s*\(?\d+\)?", "", cleaned)
    cleaned = cleaned.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"[.,]\s*$", "", cleaned)
    return cleaned


def _remove_dollars(formula: str) -> str:
    """Remove $$ delimiters if present."""
    s = formula.strip()
    if s.startswith("$$") and s.endswith("$$"):
        return s[2:-2].strip()
    return s


def _normalize_for_render(formula: str) -> str:
    """Normalize a formula string before sending to MathJax."""
    return _sanitize_formula(_remove_dollars(formula))


# --- MathJax rendering utilities for pixel-level comparison ---

MATHJAX_CDN_URL = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"


@dataclass(frozen=True)
class RenderConfig:
    """Settings for the MathJax browser session."""
    timeout_ms: int = 20_000
    font_cache: str = "none"


def _build_html(cfg: RenderConfig) -> str:
    """Return a minimal HTML page that bootstraps MathJax."""
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <script>
      window.MathJax = {{
        svg: {{ fontCache: '{cfg.font_cache}' }},
        startup: {{ typeset: false }}
      }};
    </script>
    <script defer src="{MATHJAX_CDN_URL}"></script>
  </head>
  <body></body>
</html>
"""


class FormulaRenderer:
    """
    Render LaTeX to PNGs through a single Playwright session to avoid
    per-formula browser spin-up. Outputs are cached for fast comparisons.
    """

    def __init__(self, cfg: RenderConfig | None = None):
        self.cfg = cfg or RenderConfig()
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._math_page = self._browser.new_page()
        self._math_page.set_content(_build_html(self.cfg), wait_until="load")
        self._math_page.wait_for_function(
            "window.MathJax && MathJax.startup && MathJax.startup.promise",
            timeout=self.cfg.timeout_ms,
        )
        self._math_page.evaluate("() => MathJax.startup.promise")
        self._img_page = self._browser.new_page()
        self._cache: dict[str, bytes] = {}

    def to_svg(self, latex: str) -> str:
        if not isinstance(latex, str) or not latex.strip():
            raise ValueError("latex must be a non-empty string")
        return self._math_page.evaluate(
            """async (latex) => {
                await MathJax.startup.promise;
                const node = await MathJax.tex2svgPromise(latex, {display: true});
                const svg = node.querySelector('svg');
                if (!svg) throw new Error("No <svg> found in MathJax output");
                return svg.outerHTML;
            }""",
            latex,
        )

    def svg_to_png(self, svg_xml: str) -> bytes:
        self._img_page.set_content(
            f"""<!doctype html>
<html>
  <body style="margin:0;display:flex;align-items:flex-start;justify-content:flex-start;">
    {svg_xml}
  </body>
</html>""",
            wait_until="load",
        )
        el = self._img_page.locator("svg").first
        if el.bounding_box() is None:
            raise RuntimeError("Failed to measure SVG for screenshot")
        return el.screenshot(type="png")

    def to_png(self, latex: str) -> bytes:
        if latex not in self._cache:
            self._cache[latex] = self.svg_to_png(self.to_svg(latex))
        return self._cache[latex]

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()


def images_match(png_a: bytes, png_b: bytes) -> bool:
    """Compare two PNG images at the pixel level."""
    try:
        from PIL import Image, ImageChops
    except Exception:
        return png_a == png_b

    img_a = Image.open(io.BytesIO(png_a)).convert("RGBA")
    img_b = Image.open(io.BytesIO(png_b)).convert("RGBA")
    if img_a.size != img_b.size:
        return False
    diff = ImageChops.difference(img_a, img_b)
    return diff.getbbox() is None


def formulas_render_equal(tex_a: str, tex_b: str, *, renderer: FormulaRenderer) -> bool:
    """Return True if two LaTeX snippets render to identical PNGs."""
    return images_match(renderer.to_png(tex_a), renderer.to_png(tex_b))


def compute_render_diff(
    expected: list[str], actual: list[str], renderer: FormulaRenderer
) -> tuple[list[str], list[str]]:
    """
    Compare two lists of formulas using pixel rendering.
    Returns (missing_from_actual, surplus_in_actual).
    """
    remaining = list(actual)
    missing: list[str] = []

    for formula in expected:
        target = _normalize_for_render(formula)
        found_idx = None
        for j, candidate in enumerate(remaining):
            cand_norm = _normalize_for_render(candidate)
            if formulas_render_equal(target, cand_norm, renderer=renderer):
                found_idx = j
                break
        if found_idx is None:
            missing.append(formula)
        else:
            remaining.pop(found_idx)

    return missing, remaining


@pytest.fixture(scope="session")
def formula_renderer():
    """Session-scoped renderer so MathJax only boots once."""
    renderer = FormulaRenderer()
    try:
        yield renderer
    finally:
        renderer.close()


class TestFilePresence:
    """Basic file existence and structure checks."""

    def test_source_pdf_exists(self):
        """Ensure the source PDF is present for extraction."""
        assert PDF_FILE.exists(), f"PDF not found at {PDF_FILE}"

    def test_output_file_exists(self):
        """Ensure the agent wrote the output markdown file."""
        assert ANSWER_FILE.exists(), f"Answer file not found at {ANSWER_FILE}"

    def test_output_has_content(self):
        """Ensure the output file contains at least one formula."""
        formulas = read_formulas(ANSWER_FILE)
        assert formulas, "Answer file is empty or has no formulas"


class TestFormulaFormatting:
    """Validate LaTeX formatting and delimiter usage."""

    def test_dollar_delimiters(self):
        """Every output formula must be wrapped in $$ delimiters."""
        formulas = read_formulas(ANSWER_FILE)
        bad = [f for f in formulas if not (f.startswith("$$") and f.endswith("$$"))]
        assert not bad, f"Lines missing $$ delimiters: {bad}"

    def test_no_duplicates(self):
        """Output should list each formula only once."""
        formulas = read_formulas(ANSWER_FILE)
        assert len(formulas) == len(set(formulas)), "Duplicate formulas detected"


class TestFormulaAccuracy:
    """Compare extracted formulas against the canonical expected list."""

    @pytest.fixture(scope="session")
    def gold_formulas(self):
        assert EXPECTED_FORMULAS, "Expected formulas list is empty"
        return EXPECTED_FORMULAS

    @pytest.fixture(scope="class")
    def agent_formulas(self):
        formulas = read_formulas(ANSWER_FILE)
        assert formulas, "No formulas found in output"
        return formulas

    def test_count_matches(self, gold_formulas, agent_formulas):
        """The number of extracted formulas matches the expected count."""
        assert len(agent_formulas) == len(gold_formulas), (
            f"Expected {len(gold_formulas)} formulas, found {len(agent_formulas)}"
        )

    def test_render_comparison(self, gold_formulas, agent_formulas, formula_renderer):
        """Formulas render identically via MathJax rather than relying on string equality."""
        missing, surplus = compute_render_diff(gold_formulas, agent_formulas, formula_renderer)
        assert not missing, f"Missing formulas: {missing}"
        assert not surplus, f"Unexpected extra formulas: {surplus}"
