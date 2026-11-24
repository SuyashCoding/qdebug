# A harder real bug: youtube-dl's --match-filter (BugsInPy youtube-dl bug 24).
#
# Build it from the qdebug folder (the "." at the end matters):
#   docker build -t qdebug-youtube-dl -f examples/youtube-dl/Dockerfile .
# Then:
#   docker run -it --rm qdebug-youtube-dl              # you answer the questions
#   docker run -it --rm qdebug-youtube-dl demo watch   # qdebug answers by comparing with the fixed version
#
# youtube-dl's code is downloaded from GitHub while building (two snapshots of about 2 MB each), so it is
# not copied into the qdebug repository. Nothing from youtube-dl runs on your own computer, only in here.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 COLUMNS=100
WORKDIR /qdebug
COPY . .
RUN pip install --no-cache-dir -e .

# youtube-dl just before the fix (buggy) and with the fix (fixed), as BugsInPy records them
ARG BUGGY=2c6da7df4a4d69ec933688e3c53795fd3436a1c6
ARG FIXED=e5a088dc4be4fdcc96927a9f1b7284d4cd49c415
RUN python - <<EOF
import io, tarfile, urllib.request
for name, commit in (("youtube-dl", "$BUGGY"), ("youtube-dl-fixed", "$FIXED")):
    url = f"https://github.com/ytdl-org/youtube-dl/archive/{commit}.tar.gz"
    data = urllib.request.urlopen(url, timeout=120).read()
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall("/demo", filter="data")
    import os; os.rename(f"/demo/youtube-dl-{commit}", f"/demo/{name}")
EOF
# Like BugsInPy: the buggy code gets the test file from the fix, which adds the test that shows the bug
RUN cp /demo/youtube-dl-fixed/test/test_YoutubeDL.py /demo/youtube-dl/test/test_YoutubeDL.py \
 && cp examples/youtube-dl/demo.sh /usr/local/bin/demo && chmod +x /usr/local/bin/demo

WORKDIR /demo/youtube-dl
CMD ["demo"]
