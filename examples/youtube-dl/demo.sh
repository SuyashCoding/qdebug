#!/bin/sh
# Runs qdebug on youtube-dl's failing test. "demo" asks you; "demo watch" answers by itself.
# --suite: only run test_YoutubeDL.py (youtube-dl's other tests download real videos from the internet).
set -e
TEST=test/test_YoutubeDL.py::TestYoutubeDL::test_match_filter
if [ "$1" = "watch" ]; then
    exec qdebug debug --project /demo/youtube-dl --suite test/test_YoutubeDL.py --test "$TEST" \
        --oracle truth --fixed /demo/youtube-dl-fixed
fi
exec qdebug debug --project /demo/youtube-dl --suite test/test_YoutubeDL.py --test "$TEST"
