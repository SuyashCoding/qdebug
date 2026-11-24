# The real-bug study (results/bugsinpy-2026/PLAN.md) in a Linux container, so the downloaded projects and their
# tests never run on your own machine, and every run sees the same environment.
#
#   docker build -t qdebug-bugsinpy -f benchmarks/bugsinpy.Dockerfile benchmarks
#   docker volume create qdebug-bugsinpy          # clones, Pythons and virtualenvs, kept between runs
#   docker run --rm -v "$(pwd):/qdebug" -v qdebug-bugsinpy:/work qdebug-bugsinpy \
#       qdebug bugsinpy --bugsinpy /work/BugsInPy --work /work/w --bugs tqdm:4 --out /qdebug/results/x
#
# The qdebug source is mounted at /qdebug (not copied), so the image does not change with the code.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git build-essential pkg-config \
      libxml2-dev libxslt1-dev libffi-dev libssl-dev zlib1g-dev \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir uv

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_CACHE_DIR=/work/uv-cache UV_LINK_MODE=copy
WORKDIR /qdebug
# install the mounted qdebug, fetch BugsInPy once, then run the command
ENTRYPOINT ["sh", "-c", "pip install -q --root-user-action=ignore -e /qdebug && { [ -d /work/BugsInPy ] || git clone -q https://github.com/soarsmu/BugsInPy /work/BugsInPy; } && exec \"$@\"", "--"]
CMD ["qdebug", "--help"]
