#!/bin/bash
# Train variant libraries: difficulty-graded set that forces learning API scouting.
#   chardet  : trivial top-level `.detect()` (baseline)
#   autopep8 : config-object pattern `fix_code(src, options={...})` (~= val black.Mode)
#   jinja2   : deep-submodule `jinja2.Environment().from_string(s).render()` (~= val arrow.parser, IPython.core.splitinput)
#   pygments : scouting-required `pygments.lex(code, lexer)` via pygments.lexers (~= val minisgl unfamiliarity)
wget -O chardet.tar.gz https://github.com/chardet/chardet/archive/refs/tags/5.2.0.tar.gz \
    && tar xvf chardet.tar.gz \
    && mv chardet-5.2.0 chardet &

wget -O autopep8.tar.gz https://github.com/hhatto/autopep8/archive/refs/tags/v2.3.2.tar.gz \
    && tar xvf autopep8.tar.gz && mv autopep8-2.3.2 autopep8 &

wget -O jinja2.tar.gz https://github.com/pallets/jinja/archive/refs/tags/3.1.6.tar.gz \
    && tar xvf jinja2.tar.gz && mv jinja-3.1.6 jinja2 &

wget -O pygments.tar.gz https://github.com/pygments/pygments/archive/refs/tags/2.19.2.tar.gz \
    && tar xvf pygments.tar.gz && mv pygments-2.19.2 pygments &

wait
rm -rf *.tar.gz
