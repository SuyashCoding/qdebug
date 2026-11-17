# A real bug in tqdm, for the qdebug demo

This folder is [tqdm](https://github.com/tqdm/tqdm), the popular Python progress-bar library, exactly as it
was at commit [`03b3476`](https://github.com/tqdm/tqdm/tree/03b347646492131d889871939b40457d29147216)
(2019), which has a real bug. It is bug 4 of tqdm in [BugsInPy](https://github.com/soarsmu/BugsInPy), a
collection of real bugs from real Python projects.

**The bug:** with a `unit_scale` but no known total, `tqdm.format_meter` runs `total *= unit_scale` while
`total` is `None`, and crashes with a `TypeError`. tqdm fixed it in commit
[`964dee6`](https://github.com/tqdm/tqdm/commit/964dee631d0ed30e2f799b42fc58ba5e73795a08) by only scaling
the total when there is one (`if total:`).

## What differs from tqdm at that commit

- `tqdm/tests/tests_tqdm.py` is the version from the fix commit, which adds `test_nototal`: the test that
  shows the bug. This is how BugsInPy sets up every bug.
- `nose/`, `conftest.py` and `pytest.ini` are **not part of tqdm**. tqdm's tests of 2019 import three
  helpers from the `nose` test library, which no longer runs on Python 3.10+, and call
  `sys.setcheckinterval`, which Python 3.9 removed. These files stand in for them so the tests run with
  pytest on a current Python. `pytest.ini` runs `tests_tqdm.py`, the test file BugsInPy uses for this bug
  (tqdm's other test files of 2019 also fail on a current Python, for unrelated reasons). tqdm's own code is
  unchanged.
- On the buggy code, `tests_tqdm.py` has 50 passing tests and one failing test, `test_nototal`.
- `DEMO.ipynb` and `logo.png` were left out.

tqdm is released under the MIT and MPL 2.0 licences; see [LICENCE](LICENCE).
