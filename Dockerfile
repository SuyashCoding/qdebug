# qdebug in a container: works the same on Windows, macOS and Linux.
#
#   docker build -t qdebug .
#   docker run -it --rm qdebug                       # the real-bug demo (tqdm)
#   docker run -it --rm qdebug qdebug debug --project benchmarks/shop/variants/bug_01
#   docker run -it --rm -e ANTHROPIC_API_KEY qdebug qdebug debug --project examples/tqdm --oracle hybrid
#
# -it is needed: qdebug asks you questions.
# Another Python: docker build --build-arg PYTHON=3.10 -t qdebug .
ARG PYTHON=3.12
FROM python:${PYTHON}-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 COLUMNS=100
WORKDIR /qdebug
COPY . .
RUN pip install --no-cache-dir -e ".[ai]" \
 && qdebug variants --suite shop

CMD ["qdebug", "debug", "--project", "examples/tqdm"]
