#!/bin/bash
wget -O pyyaml.tar.gz https://github.com/yaml/pyyaml/archive/refs/tags/6.0.2.tar.gz \
    && tar xvf pyyaml.tar.gz \
    && mv pyyaml-6.0.2 pyyaml &

wget -O mistune.tar.gz https://github.com/lepture/mistune/archive/refs/tags/v3.1.3.tar.gz \
    && tar xvf mistune.tar.gz && mv mistune-3.1.3 mistune &

wget -O chardet.tar.gz https://github.com/chardet/chardet/archive/refs/tags/5.2.0.tar.gz \
    && tar xvf chardet.tar.gz && mv chardet-5.2.0 chardet &

wget -O dateutil.tar.gz https://github.com/dateutil/dateutil/archive/refs/tags/2.9.0.post0.tar.gz \
    && tar xvf dateutil.tar.gz && mv dateutil-2.9.0.post0 dateutil &

wait
rm -rf *.tar.gz
