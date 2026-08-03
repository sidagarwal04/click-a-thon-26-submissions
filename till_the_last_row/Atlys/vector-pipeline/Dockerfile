FROM timberio/vector:0.39.0-debian

RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates \
 && update-ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    -r /tmp/requirements.txt

COPY vector.toml /etc/vector/vector.toml
COPY parquet_reader.py /app/parquet_reader.py

# Base image ENTRYPOINT is already /usr/bin/vector — just pass args
CMD ["--config", "/etc/vector/vector.toml"]
