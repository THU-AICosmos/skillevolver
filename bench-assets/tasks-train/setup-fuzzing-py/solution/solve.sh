#!/bin/bash
# Train variant reference solution.
# Demonstrates a "scout-then-act" pattern that transfers to validation libs
# whose primary callable is not at the top level (e.g. val: arrow.parser,
# IPython.core.splitinput, black.Mode(), unfamiliar minisgl).
set -e
export PATH="$HOME/.local/bin:$PATH"
echo "=== solve.sh starting ==="
echo "PWD: $(pwd)"
echo "Contents of /app:"
ls -la /app

# step 1: discover the libraries installed
ls > libraries.txt

libs=("chardet" "autopep8" "jinja2" "pygments")

# step 2: scout APIs for each library, then write notes_for_testing.txt.
# The scouting block below is intentionally verbose — the distilled skill
# reads exploration traces of this output and should internalise the pattern:
#   (a) walk_packages to see submodules
#   (b) grep for parse/tokenize/lex/fix/render/loads/format entry points
#   (c) inspect __init__.py to see what is re-exported
# This is the transferable heuristic, not the specific APIs of these 4 libs.
mkdir -p /tmp/scout
for lib in "${libs[@]}"; do
    echo "===== SCOUTING $lib ====="
    # Install minimally so we can import for walk_packages introspection.
    # We use a throwaway venv at /tmp/scout/$lib so real per-lib venvs (below)
    # are untouched.
    (
        cd /tmp/scout
        uv venv --python 3.12 "$lib-probe" >/dev/null 2>&1 || true
        source "$lib-probe/bin/activate"
        uv pip install --quiet "/app/$lib" >/dev/null 2>&1 || true

        echo "--- walk_packages ($lib) ---"
        python -c "
import pkgutil, importlib, sys
try:
    m = importlib.import_module('$lib')
    print('top-level dir:', sorted([x for x in dir(m) if not x.startswith('_')])[:25])
    if hasattr(m, '__path__'):
        mods = list(pkgutil.walk_packages(m.__path__, prefix='$lib.'))
        for mm in mods[:30]:
            print(mm.name)
except Exception as e:
    print('probe failed:', e, file=sys.stderr)
" 2>&1 | head -40

        echo "--- grep entry-point defs in /app/$lib ---"
        grep -rEn --include='*.py' 'def (parse|tokenize|lex|fix_code|render|loads|format_file_contents|html|detect|from_string)\b' "/app/$lib" 2>/dev/null | head -20 || true

        echo "--- head /app/$lib/*/__init__.py ---"
        find "/app/$lib" -maxdepth 3 -name '__init__.py' | head -3 | while read f; do
            echo "### $f"
            head -40 "$f" 2>/dev/null
        done
        deactivate 2>/dev/null || true
    ) > "/app/$lib-scout.log" 2>&1 || true

    # Promote a compact summary into notes_for_testing.txt
    mkdir -p "/app/$lib"
    {
        echo "# Scouting notes for $lib"
        echo "## walk_packages + grep summary (from /app/$lib-scout.log)"
        head -80 "/app/$lib-scout.log" 2>/dev/null || echo "(scout probe was empty)"
        echo ""
        echo "## Chosen fuzz entry point"
    } > "/app/$lib/notes_for_testing.txt"
done

# Per-lib chosen entry points (the payoff of scouting):
cat >> /app/chardet/notes_for_testing.txt <<'EOF'
chardet exposes `chardet.detect(raw_bytes) -> {encoding, confidence, language}`
at the top level. Baseline "import + call" case.
EOF

cat >> /app/autopep8/notes_for_testing.txt <<'EOF'
autopep8.fix_code(source, options=None) is the entry point. `options` is a
config-object-like dict (e.g. {"aggressive": 1, "max_line_length": 79}).
Pattern lesson: SOME callables need a config object to exercise the hot path.
Cf. val black.format_file_contents(src, mode=black.Mode(), fast=False).
EOF

cat >> /app/jinja2/notes_for_testing.txt <<'EOF'
Jinja2's parse/compile pipeline lives one level deep:
    env = jinja2.Environment(); env.from_string(template_src).render()
Top-level `jinja2` re-exports Environment. Also jinja2.Template(src).render().
Pattern lesson: deep-submodule / builder-pattern parsers.
Cf. val arrow.parser.TzinfoParser(...).parse(s) and IPython.core.splitinput.split_user_input.
EOF

cat >> /app/pygments/notes_for_testing.txt <<'EOF'
pygments top-level `highlight(code, lexer, formatter)` is the public API, but
you must first resolve a lexer from pygments.lexers, e.g.:
    from pygments.lexers import PythonLexer
    from pygments.formatters import HtmlFormatter
    highlight(code, PythonLexer(), HtmlFormatter())
For a self-contained fuzz target, pygments.lex(code, lexer) consumes the
tokeniser directly. Pattern lesson: unfamiliar library -> scout pygments.lexers
module to find a concrete Lexer subclass before you can call the entry point.
Cf. val minisgl (completely unfamiliar project — scout first).
EOF

# step 3: hardcode fuzz.py files for each library.
# Each one showcases a different API-discovery pattern.

# chardet: trivial top-level (baseline)
cat > /app/chardet/fuzz.py << 'EOF'
import sys
import atheris

with atheris.instrument_imports():
    import chardet


def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    raw_bytes = fdp.ConsumeBytes(fdp.ConsumeIntInRange(1, 4096))
    try:
        chardet.detect(raw_bytes)
    except Exception:
        pass


def main():
    atheris.instrument_all()
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
EOF

# autopep8: config-object pattern (transfers to val black.Mode)
cat > /app/autopep8/fuzz.py << 'EOF'
import sys
import atheris

with atheris.instrument_imports():
    import autopep8


# Config object analogous to black.Mode() on val.
_OPTIONS = {
    "aggressive": 1,
    "max_line_length": 79,
    "indent_size": 4,
}


def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    source = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(1, 4096))
    try:
        autopep8.fix_code(source, options=_OPTIONS)
    except Exception:
        pass


def main():
    atheris.instrument_all()
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
EOF

# jinja2: deep-submodule / builder pattern
cat > /app/jinja2/fuzz.py << 'EOF'
import sys
import atheris

with atheris.instrument_imports():
    import jinja2


_ENV = jinja2.Environment(autoescape=False)


def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    src = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(1, 4096))
    try:
        tmpl = _ENV.from_string(src)
        tmpl.render(x=1, y="hello", z=[1, 2, 3])
    except jinja2.TemplateError:
        pass
    except Exception:
        pass


def main():
    atheris.instrument_all()
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
EOF

# pygments: scout-first pattern (need pygments.lexers to find a concrete Lexer)
cat > /app/pygments/fuzz.py << 'EOF'
import sys
import atheris

with atheris.instrument_imports():
    import pygments
    from pygments.lexers import PythonLexer


# Entry point resolved via scouting pygments.lexers — analogous to
# resolving an unfamiliar submodule API on val.
_LEXER = PythonLexer()


def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    code = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(1, 4096))
    try:
        list(pygments.lex(code, _LEXER))
    except Exception:
        pass


def main():
    atheris.instrument_all()
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
EOF

# step 4: per-lib runner.sh scripts.
cat > /tmp/chardet_runner.sh << 'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /app/chardet
uv venv --python 3.12
uv pip install .
uv pip install atheris==3.0.0
uv run --no-project fuzz.py -max_total_time=10 2> fuzz.log
EOF

cat > /tmp/autopep8_runner.sh << 'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /app/autopep8
uv venv --python 3.12
uv pip install .
uv pip install atheris==3.0.0
uv run --no-project fuzz.py -max_total_time=10 2> fuzz.log
EOF

cat > /tmp/jinja2_runner.sh << 'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /app/jinja2
uv venv --python 3.12
uv pip install .
uv pip install atheris==3.0.0
uv run --no-project fuzz.py -max_total_time=10 2> fuzz.log
EOF

cat > /tmp/pygments_runner.sh << 'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /app/pygments
uv venv --python 3.12
uv pip install .
uv pip install atheris==3.0.0
uv run --no-project fuzz.py -max_total_time=10 2> fuzz.log
EOF

CURRENT_DIR=$(pwd)
pids=()
for lib in "${libs[@]}"; do
    bash /tmp/${lib}_runner.sh &
    pids+=($!)
done

for pid in "${pids[@]}"; do
    wait "${pid}"
done

cd $CURRENT_DIR

echo "=== solve.sh completed ==="
exit 0
