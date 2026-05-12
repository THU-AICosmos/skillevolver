#!/bin/bash
# NOTE: this solution is to validate whether the tests work
# Agent's actions are verified by executing the generated fuzz driver dynamically
set -e
export PATH="$HOME/.local/bin:$PATH"
echo "=== solve.sh starting ==="
echo "PWD: $(pwd)"
echo "Contents of /app:"
# Use this file to solve the task.

# step 1: discover the libraries installed
ls > libraries.txt

# step 2: discover important APIs
libs=("pyyaml" "chardet" "mistune" "dateutil")
for lib in "${libs[@]}"; do
    echo "some notes for testing here.." >> /app/$lib/notes_for_testing.txt
done

# step 3: hardcode fuzz.py files for each library
# pyyaml fuzz.py
cat > /app/pyyaml/fuzz.py << 'EOF'
import sys

import atheris

with atheris.instrument_imports():
    import yaml


def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    yaml_string = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(1, 4096))

    try:
        yaml.safe_load(yaml_string)
    except yaml.YAMLError:
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

# chardet fuzz.py
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

# mistune fuzz.py
cat > /app/mistune/fuzz.py << 'EOF'
import sys

import atheris

with atheris.instrument_imports():
    import mistune


def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    markdown_text = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(1, 4096))

    try:
        mistune.html(markdown_text)
    except Exception:
        pass


def main():
    atheris.instrument_all()
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
EOF

# dateutil fuzz.py
cat > /app/dateutil/fuzz.py << 'EOF'
import sys

import atheris

with atheris.instrument_imports():
    from dateutil.parser import parse as dateutil_parse


def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    date_string = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(1, 256))

    try:
        dateutil_parse(date_string)
    except (ValueError, OverflowError, TypeError):
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

# step 4: setup runner scripts for each library
# pyyaml runner.sh
cat > /tmp/pyyaml_runner.sh << 'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /app/pyyaml
uv venv --python 3.12
uv pip install .
uv pip install atheris==3.0.0
uv run --no-project fuzz.py -max_total_time=10 2> fuzz.log
EOF

# chardet runner.sh
cat > /tmp/chardet_runner.sh << 'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /app/chardet
uv venv --python 3.12
uv pip install .
uv pip install atheris==3.0.0
uv run --no-project fuzz.py -max_total_time=10 2> fuzz.log
EOF

# mistune runner.sh
cat > /tmp/mistune_runner.sh << 'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /app/mistune
uv sync --python 3.12
uv pip install atheris==3.0.0
uv run fuzz.py -max_total_time=10 2> fuzz.log
EOF

# dateutil runner.sh
cat > /tmp/dateutil_runner.sh << 'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
cd /app/dateutil
uv venv --python 3.12
uv pip install python-dateutil
uv pip install atheris==3.0.0
uv run --no-project fuzz.py -max_total_time=10 2> fuzz.log
EOF

CURRENT_DIR=$(pwd)
# projects management using uv
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
