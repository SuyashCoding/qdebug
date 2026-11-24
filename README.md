# qdebug

**qdebug finds the bug behind a failing test by asking you simple yes/no questions.**

When a test fails, it tells you the final answer was wrong, not *where* the mistake is. Finding that usually
means reading a lot of code. qdebug does the searching instead. It runs the failing test, records every
function call (what went in, what came out), and shows you one call at a time:

> `apply_discount` was called with `price = 100, percent = 10` and returned `110`. **Is that the right result?**

You answer **y** or **n**. You don't have to read any code, only know what the function is supposed to
do. Each answer rules out a big part of the program, and after a handful of questions qdebug points at the
exact line that is wrong.

It works with Python projects tested with [pytest](https://docs.pytest.org/), the most common Python test
tool.

| | Section | What's in it |
|---|---|---|
| 1 | [How it works](#1-how-it-works) | The idea in five steps. |
| 2 | [Does it work?](#2-does-it-work) | Results on 229 real bugs, compared with existing techniques. |
| 3 | [Try it: a real bug in tqdm](#3-try-it-a-real-bug-in-tqdm) | **Start here.** A 10-minute demo. You only need Docker. |
| 4 | [A harder one: youtube-dl](#4-a-harder-one-youtube-dl) | A real bug buried 7 calls deep in a 100,000-line project. |
| 5 | [Install qdebug on your computer](#5-install-qdebug-on-your-computer) | Windows, macOS and Linux, without Docker. |
| 6 | [Use it on your own project](#6-use-it-on-your-own-project) | Your own code, or any project from GitHub. |
| 7 | [Optional: let Claude help](#7-optional-let-claude-help) | An AI that answers the questions for you. |
| 8 | [Reproduce the results](#8-reproduce-the-results) | The tests, the benchmarks and the real-bug study. |
| 9 | [What's in this repository](#9-whats-in-this-repository) | Every command and every folder. |
| | [Troubleshooting](#troubleshooting) | If something doesn't work. |

---

## 1. How it works

qdebug combines two older ideas from debugging research and fixes the main weakness of each.

1. **Make a first guess.** qdebug runs all the tests and notes which code each one runs. Code that the
   failing tests run a lot and the passing tests rarely run is *suspicious*. This is called spectrum-based
   fault localization; qdebug uses the common **Ochiai** formula. Many tools stop here and give you a ranked
   list, but the real bug is often not near the top, and people don't read long lists.
2. **Record the failing test.** It reruns the failing test and records every call as a tree: who called
   whom, with what inputs, and what came back. To stay fast it records full values for only the most
   suspicious 5% of functions first, and more only if it needs them.
3. **Ask the most useful question.** This is *algorithmic debugging* (Shapiro, 1983): if a call's result is
   wrong but every call it made gave a right result, the bug is in that function. Classic versions ask in a
   fixed order; qdebug starts from the guess in step 1 and always asks the question expected to rule out the
   most (the highest *information gain*).
4. **Don't trust any single answer.** People make mistakes, and one wrong answer sends a classic algorithmic
   debugger the wrong way for good. qdebug keeps a probability for every call and treats each answer as
   evidence that is wrong 10% of the time, so later answers can outvote a mistake. It stops when one function
   holds 90% of the probability, or when a call is proven wrong with all its sub-calls right.
5. **Find the line.** It replays the broken function and shows you the variables before different lines,
   asking "still on the right track here?". The line where things go from right to wrong is the bug.

Two more things it does: if several tests fail, it **groups them by the bug that probably causes each
group**, so a second bug doesn't throw off the first guess. And a few **search rules learned from failures**
on practice bugs (the *tuned* policy, the default) cut the number of questions; `--policy baseline` turns
them off. Each rule, and the failure it came from, is described in [qdebug/tuning.py](qdebug/tuning.py).

---

## 2. Does it work?

We tested qdebug on **real bugs from real open-source projects**, using
[BugsInPy](https://github.com/soarsmu/BugsInPy), a collection that research papers use to measure debugging
tools: each bug comes with the code before and after the developers fixed it, and the test that shows it.

**How the test was set up**

- **A robot answers the questions.** Nobody can answer thousands of questions by hand, so an *oracle*
  answers each one by running the same call in the fixed version of the project and checking whether the
  output matches. It stands in for a careful person. To see what happens when people make mistakes, it was
  also made to answer wrong on purpose 10% and 20% of the time.
- **Held-out projects.** Six projects qdebug had already been tried on (96 bugs) are the *development* set.
  Six projects it had **never** been run on (black, fastapi, luigi, sanic, tornado, scrapy; 133 bugs) are
  the *held-out* set. We finished qdebug's code first and then ran these bugs a single time, without
  changing any of qdebug's settings after seeing results, so qdebug could not be tuned to fit them. The
  conclusions rest on the held-out set.
- **Plan written first.** What to measure, what to compare against, which statistical tests to use and what
  counts as success were all written down **before** the run: [results/bugsinpy-2026/PLAN.md](results/bugsinpy-2026/PLAN.md).
  Every change made during the run is listed there under *Deviations*.
- **Compared with:** the top 1, 3 and 5 entries of the Ochiai and DStar rankings (what fault-localization
  tools give you), the place where the program crashed (what a stack trace gives you), and the classic
  top-down and divide-and-query question orders. Comparisons are on the same bugs, with McNemar's exact test
  and the Wilcoxon signed-rank test.
- **Success meant:** qdebug finds the buggy function more often than Ochiai's top entry on the held-out
  set (p < 0.05), and the tuned rules are no worse than the baseline.

**Results on the held-out projects** (105 bugs with a completed session; 23 more could not be reproduced on
a current machine and 5 failed for other reasons, all reported):

| technique | finds the buggy function | finds the buggy line |
|---|---|---|
| **qdebug** (one answer, about 11 questions) | **49 (47%)** | **37 (35%)** |
| Ochiai, top entry | 23 (22%) | 13 (12%) |
| Ochiai, top 3 | 41 (39%) | 29 (28%) |
| Ochiai, top 5 | 54 (51%) | 36 (34%) |
| DStar, top entry | 23 (22%) | 13 (12%) |
| crash location (only for the 20 crashes) | 11 of 20 | – |

- **The success criterion was met.** qdebug names the buggy function twice as often as Ochiai's top entry
  (28 bugs found only by qdebug, 2 only by Ochiai; p < 0.001), and the line almost three times as often.
  Its single answer is about as good as reading the top three of the ranking.
- **Tuned vs baseline rules:** the same bugs found (49 vs 50, p = 1.0), with fewer questions (10.7 vs 13.4
  on average, p < 0.001).
- **Wrong answers:** with 10% of answers wrong it still finds 39% of the buggy functions, and 35% with 20%
  wrong. Lines suffer more (24% and 16%).
- **Big runs:** on failing tests with 100 or more calls it still finds 47%, while Ochiai's top entry drops
  to 13%. That's where asking questions helps most.
- **Where it struggles:** about half the bugs are still missed; tornado (3 of 14) and fastapi (4 of 15),
  which do much of their work in asynchronous code, were the hardest.
- On the development projects, qdebug found 78% against 59% for Ochiai's top entry.

Every table (per research question and per project): [results/bugsinpy-2026/study.md](results/bugsinpy-2026/study.md).
On the 39 bugs we planted in two practice projects, qdebug finds all 39 functions and 34 exact lines, and
so does it with **Claude Haiku** answering instead of the robot ([details](results/claude-haiku/README.md)).

**Limits to keep in mind:** the robot never gets confused the way people do (a study with real users is still to be
done); old projects needed some library versions swapped for ones
that still install; and qdebug looks for one bug at a time in a test that behaves the same on every run.

---

## 3. Try it: a real bug in tqdm

You'll find a real bug in a real library in about 10 minutes, using Docker. Docker runs programs inside a
*container*, a small ready-made Linux computer, so this works the same on Windows, macOS and Linux and you
don't need to install Python.

### The bug you'll find

[**tqdm**](https://github.com/tqdm/tqdm) is a Python library that adds a **progress bar** to any loop:

```python
from tqdm import tqdm

for file in tqdm(files_to_download):
    download(file)
```

```text
 76%|███████████████▏    | 763/1000 [00:02<00:00, 380.12it/s]
```

It's one of the most downloaded Python packages. In 2019 it crashed when you used `unit_scale` on a loop
whose length it couldn't know. tqdm's developers
[fixed it](https://github.com/tqdm/tqdm/commit/964dee631d0ed30e2f799b42fc58ba5e73795a08), and the failing
test you'll see is the one *they* wrote. It is "tqdm bug 4" in BugsInPy. The code is tqdm's own (10 files,
about 2,600 lines, 109 functions), exactly as it was before the fix: see
[examples/tqdm/QDEBUG_DEMO.md](examples/tqdm/QDEBUG_DEMO.md) for the few small files added so its 2019 tests
run on today's Python.

### Step 1: Install Docker Desktop

Download it from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
(free for personal and school use) and install it. Open **Docker Desktop** and wait until the bottom left
corner says **Engine running**. You don't need to sign in.

### Step 2: Open a terminal

- **Windows:** press the Windows key, type `cmd`, press Enter.
- **macOS:** press Cmd+Space, type `Terminal`, press Enter.
- **Linux:** open your terminal app.

Type each command below and press Enter after each one.

### Step 3: Download qdebug

```bash
git clone https://github.com/SuyashCoding/qdebug.git
```

```bash
cd qdebug
```

No `git`? Open [github.com/SuyashCoding/qdebug](https://github.com/SuyashCoding/qdebug), click the green
**Code** button, choose **Download ZIP**, unzip it, and `cd` into the unzipped folder instead. (On macOS,
if a window offers to install the *command line developer tools*, accept: that installs git.)

### Step 4: Build the container

```bash
docker build -t qdebug .
```

The `.` at the end matters: it means "this folder". It takes a minute or two the first time.

### Step 5: Start the demo

```bash
docker run -it --rm qdebug
```

qdebug runs tqdm's 52 tests and finds the one that fails:

```text
Step 1 of 3: Run the tests ──────────────────────────────────────────────────
52 tests ran:  50 passed   1 failed
╭─ The failing test ─────────────────────────────────────────────────────────╮
│ tqdm/tests/tests_tqdm.py::test_nototal                                     │
│ TypeError: unsupported operand type(s) for *=: 'NoneType' and 'int'        │
╰────────────────────────────────────────────────────────────────────────────╯
```

Here is that test. You'll need it to answer the questions:

```python
def test_nototal():
    """Test unknown total length"""
    with closing(StringIO()) as our_file:
        for i in tqdm((i for i in range(10)), file=our_file, unit_scale=10):
            pass
        assert "100it" in our_file.getvalue()
```

- The items come from a *generator*, `(i for i in range(10))`, which has no length. So tqdm **can't know the
  total**, and `total` is `None`. That's allowed: tqdm should just count, without a percentage.
- `unit_scale=10` means "count every item as 10". After 10 items, the bar should say `100it`.

Instead, the program crashes: something tried to multiply `None` by a number.

### Step 6: Answer the questions

qdebug asks 7 questions. Type the answer and press **Enter**:

| qdebug asks about | What it shows | Your answer | Why |
|---|---|---|---|
| Question 1 | `tqdm.display` raised an error | `n` | Drawing a progress bar should never crash. |
| Question 2 | `tqdm.__repr__` raised an error | `n` | Turning the bar into text should never crash. |
| Question 3 | `tqdm.format_dict` returned the bar's settings | `y` | The settings match the test. |
| Question 4 | `tqdm.format_meter` raised an error | `n` | It got correct settings and still crashed. |
| Line check 1 | `format_meter` at its end, raising the error | `n` | The crash is wrong. |
| Line check 2 | just before line 323, `total *= unit_scale` | `n` | It's about to multiply `None`. |
| Line check 3 | just before line 322, the `if` above it | `y` | Nothing has gone wrong yet. |

The first four are about **function calls** ("is that the right result?"). Once qdebug knows the broken
function, it switches to **line checks** ("still on the right track here?"), where the rule is:

> Answer **n** if a variable already has a wrong value, **or** if a correct program would never be at this
> line with these values. Otherwise answer **y**.

<details>
<summary><b>Show every question as qdebug shows it, with the reasoning</b></summary>

#### Question 1

```text
╭─ Question 1 ───────────────────────────────────────────────────────────────╮
│ Use `self.sp` and to display `msg` in the specified `pos`.                 │
│ tqdm.display was called with:                                              │
│ self  {'iterable': <generator object ...>, 'desc': '', 'total': None, ...  │
│ msg   None                                                                 │
│ pos   None                                                                 │
│                                                                            │
│ and it raised an error:                                                    │
│ TypeError: TypeError("unsupported operand type(s) for *=: 'NoneType' ...   │
╰──────────────────────────────────────────────────────── tqdm/_tqdm.py:1283 ─╯
  Is that the right result? (y yes, n no, ? not sure, h more) >
```

**Answer: `n`.** `display` draws the progress bar. Drawing a progress bar should never crash.

#### Question 2

```text
╭─ Question 2 ───────────────────────────────────────────────────────────────╮
│ tqdm.__repr__ was called with:                                             │
│ self  {'iterable': <generator object ...>, 'desc': '', 'total': None, ...  │
│                                                                            │
│ and it raised an error:                                                    │
│ TypeError: TypeError("unsupported operand type(s) for *=: 'NoneType' ...   │
╰───────────────────────────────────────────────────────── tqdm/_tqdm.py:965 ─╯
```

**Answer: `n`.** `__repr__` turns the bar into text. That should never crash either.

#### Question 3

```text
╭─ Question 3 ───────────────────────────────────────────────────────────────╮
│ Public API for read-only member access                                     │
│ tqdm.format_dict was called with:                                          │
│ self  {'iterable': <generator object ...>, 'desc': '', 'total': None, ...  │
│                                                                            │
│ and it returned:                                                           │
│ {'n': 0, 'total': None, 'elapsed': 0, 'ncols': None, 'prefix': '',         │
│ 'ascii': True, 'unit': 'it', 'unit_scale': 10, 'rate': None,               │
│ 'bar_format': None, 'postfix': None, 'unit_divisor': 1000}                 │
╰───────────────────────────────────────────────────────── tqdm/_tqdm.py:950 ─╯
```

**Answer: `y`.** This just collects the bar's settings, and they match the test: `total` is `None` (the
generator has no length), `unit_scale` is `10` and `n`, the count so far, is `0`.

#### Question 4

```text
╭─ Question 4 ───────────────────────────────────────────────────────────────╮
│ Return a string-based progress bar given some parameters                   │
│ tqdm.format_meter was called with:                                         │
│ n             0                                                            │
│ total         None                                                         │
│ unit_scale    10                                                           │
│ ... (the other settings from Question 3)                                   │
│                                                                            │
│ and it raised an error:                                                    │
│ TypeError: TypeError("unsupported operand type(s) for *=: 'NoneType' ...   │
╰───────────────────────────────────────────────────────── tqdm/_tqdm.py:252 ─╯
```

**Answer: `n`.** `format_meter` got the correct settings from Question 3 and should turn them into a
progress bar. It crashed instead. qdebug now knows `format_meter` is broken, and starts the line checks.

#### Line check 1

```text
╭─ Line check 1 ─────────────────────────────────────────────────────────────╮
│ When tqdm.format_meter finished:                                           │
│                                                                            │
│ The variables held:                                                        │
│ n             0                                                            │
│ total         None                                                         │
│ unit_scale    10                                                           │
│ ...                                                                        │
│ Raising: TypeError: TypeError("unsupported operand type(s) for *=: ...     │
╰───────────────────────────────────────────────────────────── tqdm/_tqdm.py ─╯
  Still on the right track here? (y yes, n no, ? not sure, h more) >
```

**Answer: `n`.** This is the end of the function, and it's crashing.

#### Line check 2

```text
╭─ Line check 2 ─────────────────────────────────────────────────────────────╮
│ Inside tqdm.format_meter, just before line 323 runs:                       │
│ 321           # apply custom scale if necessary                            │
│ 322           if unit_scale and unit_scale not in (True, 1):               │
│ 323 >             total *= unit_scale                                      │
│ 324               n *= unit_scale                                          │
│ (line 323 has not run yet)                                                 │
│                                                                            │
│ The variables held:                                                        │
│ n             0                                                            │
│ total         None                                                         │
│ unit_scale    10                                                           │
╰───────────────────────────────────────────────────────────── tqdm/_tqdm.py ─╯
```

**Answer: `n`.** The tricky one. Every variable still has a fine value, but line 323 is about to multiply
`total` by 10, and `total` is `None`. A correct program would never be here with these values.

#### Line check 3

```text
╭─ Line check 3 ─────────────────────────────────────────────────────────────╮
│ Inside tqdm.format_meter, just before line 322 runs:                       │
│ 321           # apply custom scale if necessary                            │
│ 322 >         if unit_scale and unit_scale not in (True, 1):               │
│ 323               total *= unit_scale                                      │
│ (line 322 has not run yet)                                                 │
│                                                                            │
│ The variables held:                                                        │
│ n             0                                                            │
│ total         None                                                         │
│ unit_scale    10                                                           │
╰───────────────────────────────────────────────────────────── tqdm/_tqdm.py ─╯
```

**Answer: `y`.** The values are the same correct ones as in Question 3, and nothing has gone wrong yet.

</details>

### Step 7: The answer

```text
╭─ Found it ─────────────────────────────────────────────────────────────────╮
│ tqdm/_tqdm.py, line 322, in tqdm.format_meter                              │
│                                                                            │
│ 321            # apply custom scale if necessary                           │
│ 322 >>         if unit_scale and unit_scale not in (True, 1):              │
│ 323                total *= unit_scale                                     │
│ 324                n *= unit_scale                                         │
│                                                                            │
│ Confidence: High   Your answers point directly at this code.               │
╰────────────────────────────────────────────────────────────────────────────╯
7 questions to search a project with 109 functions, without reading its code.
```

Line 322 checks the scale but forgets to check that there **is** a total before line 323 multiplies it.
That's exactly what tqdm's developers fixed:
[their fix](https://github.com/tqdm/tqdm/commit/964dee631d0ed30e2f799b42fc58ba5e73795a08) adds an
`if total:` check right there.

### More to try in the same container

5 smaller practice bugs, planted on purpose in a small online-shop program:

```bash
docker run -it --rm qdebug qdebug debug --project benchmarks/shop/variants/bug_01
```

Two tests fail: type `1` to pick the first. The answers are `n`, `n`, `n`, `n`, and qdebug lands on
line 24, `if quantity > 10:`, which should be `>= 10`. Change `bug_01` to `bug_02` up to `bug_05` for the
others.

### All the keys you can press

| key | for a function call | for a line check |
|---|---|---|
| `y` | the result is right | still on the right track |
| `n` | the result is wrong | a value is wrong, or this line shouldn't be reached |
| `?` | I'm not sure (qdebug works around it) | I'm not sure |
| `i` | the *inputs* already look wrong | – |
| `t` | I trust this function, stop asking about it | – |
| `s` | show the function's code | show the function's code |
| `e` | show how this function behaved in tests that pass | – |
| `w` | why are you asking this? | – |
| `u` | undo my last answer | undo my last answer |
| `q` | stop and show what you have so far | stop |
| `h` | help | help |

Don't worry about making a mistake: qdebug treats every answer as a clue that might be wrong, and `u` undoes.

---

## 4. A harder one: youtube-dl

The tqdm bug is a crash, close to where the error shows up. Most real bugs are harder: no crash, just a
**wrong result**, produced deep inside a big program. This demo is one of those.

[**youtube-dl**](https://github.com/ytdl-org/youtube-dl) downloads videos from YouTube and over a thousand
other sites. In 2016 it was **701 files and about 104,000 lines** of code, and qdebug has to search through
2,278 functions. The bug is BugsInPy's "youtube-dl bug 24", from qdebug's development set.

### The bug

youtube-dl has a `--match-filter` option to download only the videos you want, like
`--match-filter "duration < 600"` (under 10 minutes) or `--match-filter "playlist_id = 42"`. The test gives
it two fake videos and the filter `playlist_id = 42`:

| video | `id` | `playlist_id` |
|---|---|---|
| first | `'1'` | `'42'` |
| second | `'2'` | `'43'` |

The first video should be downloaded and the second skipped. Instead **nothing** is downloaded:

```text
AssertionError: Lists differ: [] != ['1']
```

Notice the quotes: the video's `playlist_id` is the **text** `'42'`, not the number `42`. That will matter.

### Run it

Build this demo's container (in the qdebug folder, after [Steps 1 to 3](#step-1-install-docker-desktop) of
the tqdm demo). It downloads youtube-dl's code from GitHub, about 4 MB, so it takes a few minutes:

```bash
docker build -t qdebug-youtube-dl -f examples/youtube-dl/Dockerfile .
```

Then either **answer the questions yourself**:

```bash
docker run -it --rm qdebug-youtube-dl
```

or **watch qdebug answer them on its own**, by comparing each call with youtube-dl's fixed version (the
same robot answerer used in the study):

```bash
docker run -it --rm qdebug-youtube-dl demo watch
```

### The answers

qdebug asks 7 questions about calls, following the wrong result down from the top of youtube-dl to the
function that produced it, then 6 line checks. After Question 3 you'll see *"Not enough to go on yet, so
QDebug is looking at more functions"*: it is recording more of the program (section 1, step 2).

| | qdebug shows | Answer | Why |
|---|---|---|---|
| Question 1 | `process_ie_result` handled video `'1'` with `download=True` | `n` | Video 1 passes the filter and should be downloaded. The test shows it wasn't. |
| Question 2 | `process_video_result` on video `'1'` | `n` | Same video, same reason. |
| Question 3 | `process_info` on video `'1'` returned `None` | `n` | Same: this is the step that should download it. |
| Question 4 | `_match_entry` returned `'one does not pass filter playlist_id = 42, skipping ..'` | `n` | Video 1's `playlist_id` is `'42'`. It **does** pass. |
| Question 5 | `_match_func` returned the same message | `n` | Same reason. |
| Question 6 | `match_str('playlist_id = 42', video 1)` returned `False` | `n` | Should be `True`. |
| Question 7 | `_match_one('playlist_id = 42', video 1)` returned `False` | `n` | Should be `True`. |
| Line check 1 | the end of `_match_one`: `comparison_value 42`, `actual_value '42'`, returning `False` | `n` | It compares the number `42` with the text `'42'`, and in Python those are never equal. |
| Line check 2 | before line 2345, `m = operator_rex.search(filter_part)` | `y` | Nothing has happened yet. |
| Line check 3 | before line 2354, the `try:` that turns `42` into a number | `n` | The video's value is text, so a correct program wouldn't go this way. |
| Line check 4 | before line 2347, `op = COMPARISON_OPERATORS[...]` | `y` | It has only parsed the filter. Fine. |
| Line check 5 | before line 2348, `if m.group('strval') is not None:` | `y` | Still fine: `op` is "equals". |
| Line check 6 | before line 2355, `comparison_value = int(...)` | `n` | About to turn `42` into a number. |

```text
╭─ Found it ───────────────────────────────────────────────────────────────────────────────────╮
│ youtube_dl/utils.py, line 2348, in _match_one                                                │
│                                                                                              │
│ 2346        if m:                                                                            │
│ 2347            op = COMPARISON_OPERATORS[m.group('op')]                                     │
│ 2348 >>         if m.group('strval') is not None:                                            │
│ 2349                if m.group('op') not in ('=', '!='):                                     │
│ 2350                    raise ValueError(                                                    │
│                                                                                              │
│ Confidence: High   Your answers point directly at this code.                                 │
│ The bad call: _match_one(filter_part='playlist_id = 42', dct={'id': '1', 'url':              │
│ 'http://localhost/...) → False                                                               │
╰──────────────────────────────────────────────────────────────────────────────────────────────╯
13 questions to search a project with 2,278 functions, without reading its code.
```

Line 2348 decides whether to compare as text or as a number by looking **only at the filter**: `42` looks
like a number, so it becomes the number `42`. It never checks that the video's own value is text. That's
the line youtube-dl's developers changed:
[their fix](https://github.com/ytdl-org/youtube-dl/commit/e5a088dc4be4fdcc96927a9f1b7284d4cd49c415) also
compares as text when the video's value is text.

Ochiai's ranking put this function 2nd here; on the other hard youtube-dl bugs it is often much lower (15th
for bug 8). What's in this container and where it comes from: [examples/youtube-dl](examples/youtube-dl/README.md).

---

## 5. Install qdebug on your computer

Use this to run qdebug without Docker. You need **Python 3.10 or newer** and **git**.

### Windows

1. **Install Python** from [python.org/downloads](https://www.python.org/downloads/). In the installer,
   tick **"Add python.exe to PATH"** before clicking *Install Now*.
2. **Install git** from [git-scm.com/download/win](https://git-scm.com/download/win) (the default options
   are fine).
3. Open **Command Prompt** (Windows key, type `cmd`, Enter) and check Python works:

   ```bash
   python --version
   ```

   It should print `Python 3.10` or higher.
4. Download qdebug (skip this if you already did it for Docker):

   ```bash
   git clone https://github.com/SuyashCoding/qdebug.git
   ```

   ```bash
   cd qdebug
   ```

5. Create a *virtual environment* (a private space for qdebug's packages) and switch it on:

   ```bash
   python -m venv .venv
   ```

   ```bash
   .venv\Scripts\activate
   ```

   Your prompt now starts with `(.venv)`. Run the `activate` line again in every new terminal.
6. Install qdebug:

   ```bash
   pip install -e .
   ```

### macOS

1. Open **Terminal** (Cmd+Space, type `Terminal`, Enter) and check Python:

   ```bash
   python3 --version
   ```

   If it says "command not found" or a version below 3.10, install Python from
   [python.org/downloads](https://www.python.org/downloads/). If macOS offers to install the
   *command line developer tools*, accept: that also installs git.
2. Download qdebug (skip this if you already did it for Docker):

   ```bash
   git clone https://github.com/SuyashCoding/qdebug.git
   ```

   ```bash
   cd qdebug
   ```

3. Create a virtual environment and switch it on:

   ```bash
   python3 -m venv .venv
   ```

   ```bash
   source .venv/bin/activate
   ```

   Run the `source` line again in every new terminal.
4. Install qdebug:

   ```bash
   pip install -e .
   ```

### Linux

Same as macOS. If Python or git are missing, install them with your package manager, for example on
Ubuntu or Debian:

```bash
sudo apt install python3 python3-venv git
```

### Check it worked

```bash
qdebug --version
```

This should print `qdebug 0.2.0`. Then run the tqdm demo without Docker (same questions and answers as
[in Docker](#step-6-answer-the-questions)):

```bash
qdebug debug --project examples/tqdm
```

For the practice bugs, build them once, then debug the first:

```bash
qdebug variants --suite shop
```

```bash
qdebug debug --project benchmarks/shop/variants/bug_01
```

---

## 6. Use it on your own project

qdebug works on any Python project with **pytest tests and at least one failing test**. It runs the
project's tests, so the project's own packages must be installed where qdebug runs.

No failing test? Plant a bug yourself: change one small thing, for example a `>=` into a `>`, check that a
test fails, and see whether qdebug finds your change.

### With qdebug installed (section 5)

1. Get the project, for example from GitHub:

   ```bash
   git clone https://github.com/someone/some-project.git
   ```

2. With qdebug's virtual environment switched on, install the project's own packages. Most projects use one
   of these (run it in the project's folder):

   ```bash
   pip install -e .
   ```

   ```bash
   pip install -r requirements.txt
   ```

3. Run qdebug on it:

   ```bash
   qdebug debug --project path/to/some-project
   ```

If the project has its **own** virtual environment, skip step 2 and point qdebug at it instead:
`qdebug debug --project some-project --python some-project/.venv` (that environment needs pytest).

### With Docker

Build the container first ([Steps 1 to 4](#step-1-install-docker-desktop)). Then `cd` into **your
project's folder** and start the container with that folder inside it.

Windows, Command Prompt:

```bash
docker run -it --rm -v "%cd%:/work" -w /work qdebug bash
```

Windows, PowerShell:

```bash
docker run -it --rm -v "${PWD}:/work" -w /work qdebug bash
```

macOS and Linux:

```bash
docker run -it --rm -v "$(pwd):/work" -w /work qdebug bash
```

Inside the container, install the project's packages (`pip install -e .` or
`pip install -r requirements.txt`), then run `qdebug debug`. Type `exit` to leave. Changes to files in
`/work` are real changes to your folder; anything you install is gone when you leave.

### When several tests fail

One bug often makes several tests fail, and a project can have more than one bug. qdebug guesses which
failing tests share a bug and shows them in groups:

```text
QDebug thinks these failures come from 2 different bugs. Debug one test from a group: its bug probably
explains the rest of that group.
Probable bug 1 (4 tests): they all run shop/shipping.py:41
  1  tests/test_shipping.py::test_zone_eu         AssertionError: assert 'international' == 'eu'
  2  tests/test_shipping.py::test_zone_international  AssertionError: assert 'eu' == 'international'
  3  tests/test_shipping.py::test_shipping_eu_parcel  AssertionError: assert 3499 == 2199
  4  tests/test_invoice.py::test_eu_invoice       AssertionError: assert 'international' == 'eu'
Probable bug 2 (2 tests): they all run shop/pricing.py:27
  5  tests/test_pricing.py::test_line_total_bulk  AssertionError: assert 1890 == 1791
  6  tests/test_invoice.py::test_bulk_invoice_qty_ten  AssertionError: assert 1890 == 1791
```

Pick one test from a group. At the end qdebug says which other failing tests the bug it found probably
explains too. Fix it, run the tests again, and run qdebug on what still fails. The groups are a guess
(right for 88% of the two-bug cases we measured: [results/multi-bug](results/multi-bug/planner.md)); `--no-group` turns them off.

### Handy options

| option | what it does |
|---|---|
| `--test ID` | debug this failing test (otherwise qdebug lets you pick) |
| `--suite tests/test_one_file.py` | only run these tests (faster on big projects) |
| `--python PATH` | the project's own Python or virtual environment |
| `--oracle truth --fixed PATH` | answer automatically by comparing with a bug-free copy of the project |
| `--policy baseline` | turn off the tuned search rules |
| `--strategy topdown` or `divide` | the classic question orders, instead of the most useful question |
| `qdebug rank --project PATH` | just show the most suspicious functions and lines, no questions |

Every option: `qdebug debug -h`.

---

## 7. Optional: let Claude help

qdebug can ask **Claude**, Anthropic's AI model, to look at the failing test first, answer questions for
you, and explain the bug at the end with a suggested fix. Nothing else in this README needs it.

You need an **Anthropic API key**. The API is paid, but qdebug uses the small, cheap model (Claude Haiku).

1. **Get a key.** Sign in at [platform.claude.com](https://platform.claude.com), open **API Keys**, and
   create a key (it starts with `sk-ant-`).

   > **Keep your key secret.** Never paste it into code, never commit it to git, and don't share it.

2. **Give it to qdebug** for the current terminal (replace `sk-ant-...` with your key).

   Windows, Command Prompt:

   ```bash
   set ANTHROPIC_API_KEY=sk-ant-...
   ```

   Windows, PowerShell:

   ```bash
   $env:ANTHROPIC_API_KEY = "sk-ant-..."
   ```

   macOS and Linux:

   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

3. **Choose how much Claude does** by adding one of these to a `qdebug debug` command:

   | add this | who answers the questions |
   |---|---|
   | `--ai` | **you**; Claude takes a first look and explains the bug at the end |
   | `--oracle hybrid` | **Claude** when it's sure, **you** when it isn't (it shows you its guess) |
   | `--oracle claude` | **Claude** answers everything; you watch |

   In Docker (`-e ANTHROPIC_API_KEY` passes your key into the container):

   ```bash
   docker run -it --rm -e ANTHROPIC_API_KEY qdebug qdebug debug --project examples/tqdm --oracle hybrid
   ```

   Without Docker you need Python **3.11 or newer** and the add-on, installed once:

   ```bash
   pip install -e ".[ai]"
   ```

Claude sees each call's description, inputs and outputs, but not the function's code: a model shown the
buggy code tends to explain the bug away as intended. To teach it about your project (for example "all
prices are in cents"), run `qdebug init-agent --project path/to/project` and edit `.qdebug/agent.md`.

---

## 8. Reproduce the results

Everything in [section 2](#2-does-it-work) can be re-run. All commands are run in the qdebug folder.

### The unit tests (under a minute)

In Docker, after [building the container](#step-4-build-the-container):

```bash
docker run --rm qdebug python -m pytest -q -m "not e2e"
```

Or with qdebug installed (section 5): `pytest -m "not e2e"`. Leave out `-m "not e2e"` to also run the
end-to-end tests, which debug seeded bugs for real (a few minutes).

### The practice bugs (about 6 minutes)

The 39 bugs planted in the shop and planner projects, answered by the robot oracle:

```bash
docker run --rm qdebug qdebug eval --suite planner --strategies infogain --noise 0
```

```bash
docker run --rm qdebug qdebug eval --suite shop --strategies infogain --noise 0,0.1,0.2 --seeds 10
```

Each prints one line per bug (`found=1/1 line=1/1 meanQ=...`); compare with
[results/planner/summary.md](results/planner/summary.md) and [results/shop/summary.md](results/shop/summary.md).

### The real-bug study (minutes for one bug, about a day for all 229)

This has its own container, because it downloads and installs each project's 2019–2020 code and libraries.
They only ever run inside the container. A Docker *volume* keeps the downloads between runs.

```bash
docker build -t qdebug-bugsinpy -f benchmarks/bugsinpy.Dockerfile benchmarks
```

```bash
docker volume create qdebug-bugsinpy
```

Run one bug first, tqdm bug 4 (the demo bug). The command depends on your terminal. Windows, Command Prompt:

```bash
docker run --rm -v "%cd%:/qdebug" -v qdebug-bugsinpy:/work qdebug-bugsinpy qdebug bugsinpy --bugsinpy /work/BugsInPy --work /work/w --strategies infogain,topdown,divide --policies baseline,tuned --noise 0.1,0.2 --seeds 3 --out /qdebug/results/my-study --bugs tqdm:4
```

Windows, PowerShell: the same with `"${PWD}:/qdebug"` instead of `"%cd%:/qdebug"`. macOS and Linux: the same
with `"$(pwd):/qdebug"`.

The results land in `results/my-study/results.csv`, one row per session. To run the whole study, replace
`--bugs tqdm:4` with
`--bugs PySnooper,cookiecutter,httpie,thefuck,tqdm,youtube-dl,black,fastapi,luigi,sanic,tornado,scrapy`
(you can stop and rerun the same command: bugs already in `results.csv` are skipped). Then make the tables:

```bash
docker run --rm -v "%cd%:/qdebug" -v qdebug-bugsinpy:/work qdebug-bugsinpy qdebug study-report --results /qdebug/results/my-study/results.csv
```

That writes `results/my-study/study.md`, in the same format as
[results/bugsinpy-2026/study.md](results/bugsinpy-2026/study.md). Expect small differences: a few bugs
behave differently from run to run (these are reported as *nondeterministic*), and the plan's
[Deviations](results/bugsinpy-2026/PLAN.md#deviations) explain the setup fixes made during our run.

---

## 9. What's in this repository

| command | what it does |
|---|---|
| `qdebug debug` | debug a failing test by answering questions (or let Claude answer) |
| `qdebug rank` | rank functions and lines by suspiciousness, no questions |
| `qdebug init-agent` | copy Claude's instructions into a project to customise them |
| `qdebug variants` | build and check the buggy copies of the practice projects |
| `qdebug eval` | batch experiments on the practice bugs (strategies, policies, wrong answers) |
| `qdebug eval-groups` | put two bugs in one project and measure the grouping of failing tests |
| `qdebug eval-ai` | measure Claude as the answerer (costs API usage) |
| `qdebug bugsinpy` | run the real-bug study on BugsInPy |
| `qdebug study-report` | the study's tables and statistics from its results |

```text
qdebug/            the tool
  cli.py             the commands above
  session.py         a debugging session: recording tiers, questions, undo, line search, fallback
  belief.py          the probability for every call, and the information gain of each question
  strategies.py      information gain (qdebug's), top-down and divide-and-query
  tuning.py          the tuned search rules, each with the failure it came from
  zoom.py            the line-level search inside the broken function
  ranking.py         Ochiai and DStar scores; groups.py: grouping failing tests
  runner.py, plugin.py, tracer.py   running pytest in a subprocess and recording calls and values
  oracles.py         who answers: you, the robot (ground truth), or the robot with wrong answers
  ai/                the optional Claude integration
  ui.py, report.py   the terminal interface and the saved session report
  evaluate.py, bugsinpy.py, study.py   the experiments and the real-bug study
benchmarks/        the practice projects (shop: 5 bugs, planner: 34 bugs) and the study's Dockerfile
examples/          the tqdm and youtube-dl demos
results/           every result table, as CSV and markdown; bugsinpy-2026/ holds the real-bug study,
                   its plan (PLAN.md) and its report (study.md)
tests/             unit and end-to-end tests
```

---

## Troubleshooting

### Docker

**`error during connect` or `Cannot connect to the Docker daemon`.** Docker Desktop isn't running. Open it
and wait until it says *Engine running*.

**`unable to find image 'qdebug:latest'` or `pull access denied for qdebug`.** You haven't built the
container yet: run `docker build -t qdebug .` in the qdebug folder ([Step 4](#step-4-build-the-container)).
For the youtube-dl demo the image is `qdebug-youtube-dl` ([section 4](#run-it)).

**`failed to read dockerfile` or `no such file or directory`.** Your terminal isn't in the qdebug folder:
`cd qdebug` first.

**The youtube-dl build fails while downloading.** It needs internet access to github.com. Try again; if
you are behind a proxy, Docker needs to know about it.

**`the input device is not a TTY`.** You're in Git Bash on Windows. Use Command Prompt or PowerShell
instead, or put `winpty` in front: `winpty docker run -it --rm qdebug`.

**qdebug shows "Best guess ... You stopped early" without waiting for your answer.** You left out `-it` in
`docker run -it --rm ...`. It's what lets you type into the container.

### Without Docker

**`python` is not recognized / command not found.** Python isn't installed, or wasn't added to PATH.
Reinstall it from [python.org](https://www.python.org/downloads/) (on Windows tick *"Add python.exe to
PATH"*). On macOS and Linux use `python3` instead of `python`.

**`qdebug` is not recognized / command not found.** Your virtual environment isn't switched on. Run
`.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (macOS/Linux) from the qdebug folder.
`python -m qdebug` also works anywhere `qdebug` would.

**PowerShell says "running scripts is disabled on this system".** Use Command Prompt (`cmd`) instead.

**`project directory not found: benchmarks/shop/variants/bug_01`.** Make the practice bugs first:
`qdebug variants --suite shop`.

### Both

**`no failing test in ...`.** All of that project's tests pass, so there is nothing to debug.

**`ModuleNotFoundError` in the test results.** The project's own packages aren't installed where qdebug
runs. See [Use it on your own project](#6-use-it-on-your-own-project).

**`the Claude features need ...`.** Install the add-on (`pip install -e ".[ai]"`), use Python 3.11 or
newer, or set your API key.

---

## Learn more

- [results/bugsinpy-2026/study.md](results/bugsinpy-2026/study.md): every table of the real-bug study
- [results/bugsinpy-2026/PLAN.md](results/bugsinpy-2026/PLAN.md): the study's plan, written before it ran
- [results/claude-haiku/README.md](results/claude-haiku/README.md): Claude Haiku answering the questions
- [results/multi-bug/planner.md](results/multi-bug/planner.md): grouping failing tests when two bugs are present
- [CHANGELOG.md](CHANGELOG.md): what changed in each version

qdebug is open source under the [MIT license](LICENSE).
