# AWS's own Lambda base image, not the generic uv image apps/api uses: it
# ships the Lambda Runtime Interface Client Lambda's own invoker expects to
# call, which a plain Python image does not provide. chdb ships compiled
# native extensions, so this is a container-image Lambda rather than a
# zip/layer package - a zip risks manylinux/glibc mismatches this base image
# sidesteps by matching Lambda's actual execution environment exactly.
FROM public.ecr.aws/lambda/python:3.13

# uv itself, not pip-installed dependencies: reuses the same
# `uv sync --frozen --no-dev` packaging convention as apps/api/Dockerfile,
# so this workspace's lockfile stays the single source of truth for
# resolved versions.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /workspace

COPY pyproject.toml uv.lock ./
COPY libs/adapters libs/adapters
COPY libs/application libs/application
COPY libs/domain libs/domain

# --package installs only zentra-adapter-sequence-execution's own runtime
# dependency set; every workspace member above still has to be present on
# disk for uv.lock's path-based sources to resolve at all, even ones this
# image never imports (e.g. zentra-application-connector, a transitive
# workspace-path dependency of the shared lockfile, not of this package).
#
# --no-editable: uv's default editable install writes a .pth file pointing
# back at libs/*/src: fine for the venv's own interpreter, invisible to the
# Lambda base image's system Python (which only gets PYTHONPATH, not this
# venv's site customization). Non-editable copies the real package files
# into site-packages, where a plain PYTHONPATH entry can actually find them.
RUN uv sync --frozen --no-dev --no-editable --package zentra-adapter-sequence-execution

# The Lambda Runtime Interface Client (baked into this base image's
# ENTRYPOINT) invokes the system Python directly, not `uv run` - it needs
# the synced venv's packages on its import path.
ENV PYTHONPATH="/workspace/.venv/lib/python3.13/site-packages"

CMD ["zentra_adapter_sequence_execution.lambda_entrypoint.handler"]
