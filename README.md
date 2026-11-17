# qdebug

**qdebug helps you find the bug behind a failing test, by asking you simple yes/no questions.**

When a test fails, you usually have to read a lot of code to work out where the mistake is. qdebug does the
searching for you. It runs your tests, then shows you one function call at a time, for example
*"`quantity_discount_rate(10)` returned `0.05`. Is that right?"*, and you answer **y** (yes) or **n** (no).
Each answer rules out a big part of the program. After a handful of questions it points at the exact line
that is wrong.

It works with Python projects that use [pytest](https://docs.pytest.org/) for their tests.

- [1. Install](#1-install)
- [2. Run the demo: a real bug in a real library](#2-run-the-demo-a-real-bug-in-a-real-library)
  (or [in Docker](#no-luck-installing-run-the-demo-in-docker))
- [3. Use it on your own project](#3-use-it-on-your-own-project)
- [4. Optional: let Claude help](#4-optional-let-claude-help)
- [Troubleshooting](#troubleshooting)

---

## 1. Install

You need **Python 3.10 or newer**. You also need **git** to download qdebug, or you can download a ZIP
instead (see [Other computers](#other-computers)).

Pick your computer below and type each command into a terminal, one at a time, pressing Enter after each.

### Windows

1. **Install Python** if you don't have it: download it from
   [python.org/downloads](https://www.python.org/downloads/). In the installer, tick
   **"Add python.exe to PATH"** before clicking *Install Now*.
2. **Install git** if you don't have it: [git-scm.com/download/win](https://git-scm.com/download/win)
   (the default options are fine).
3. Open **Command Prompt** (press the Windows key, type `cmd`, press Enter) and check Python works:

   ```bash
   python --version
   ```

   It should print `Python 3.10` or higher.
4. Download qdebug and go into its folder:

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

   Your prompt now starts with `(.venv)`. You need to run this `activate` line again every time you open
   a new terminal.
6. Install qdebug:

   ```bash
   pip install -e .
   ```

### macOS

1. Open **Terminal** (press Cmd+Space, type `Terminal`, press Enter) and check Python:

   ```bash
   python3 --version
   ```

   If it says "command not found" or a version below 3.10, install Python from
   [python.org/downloads](https://www.python.org/downloads/). If macOS offers to install the
   *command line developer tools*, accept: that also installs git.
2. Download qdebug and go into its folder:

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

   Your prompt now starts with `(.venv)`. Run the `source` line again every time you open a new terminal.
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

Then follow the macOS steps from step 2.

### Other computers

qdebug runs anywhere Python 3.10+ runs. If you can't use git, open
[github.com/SuyashCoding/qdebug](https://github.com/SuyashCoding/qdebug), click the green **Code** button,
choose **Download ZIP**, unzip it, open a terminal in the unzipped folder, and continue from the
"virtual environment" step for your system.

### Check it worked

```bash
qdebug --version
```

This should print `qdebug 0.2.0`.

---

## 2. Run the demo: a real bug in a real library

In this demo you'll use qdebug on a real bug in a real program that you've probably never seen the code of.

### What is tqdm?

[tqdm](https://github.com/tqdm/tqdm) (from "taqaddum", Arabic for *progress*) is a Python library that adds a
**progress bar** to any loop. You wrap the thing you loop over in `tqdm(...)`:

```python
from tqdm import tqdm

for file in tqdm(files_to_download):
    download(file)
```

and while the loop runs, the terminal shows how far along it is, how fast it's going and how long is left:

```text
 76%|███████████████▏    | 763/1000 [00:02<00:00, 380.12it/s]
```

It's one of the most downloaded packages on [PyPI](https://pypi.org/project/tqdm/), Python's package
store, and many well-known tools use it. If you've ever installed a machine-learning model or dataset in
Python and watched a bar fill up, that was probably tqdm.

### Why this counts as a real program

- **Nobody wrote it for this demo.** It's tqdm's own code, written over years by its developers and many
  outside contributors, for real users: 10 source files, about 2,600 lines, with classes, background
  threads and locks. qdebug has to search through 109 functions.
- **The bug really happened.** In 2019, using `unit_scale` on a loop with no known length made tqdm crash.
  tqdm's developers
  [fixed it in public](https://github.com/tqdm/tqdm/commit/964dee631d0ed30e2f799b42fc58ba5e73795a08). The
  failing test you'll see is the one *they* wrote for it.
- **Researchers use it to test debugging tools.** This exact bug is "tqdm bug 4" in
  [BugsInPy](https://github.com/soarsmu/BugsInPy), a collection of real bugs from 17 real Python projects
  that research papers use to measure debugging tools.

The folder `examples/tqdm` holds tqdm's code exactly as it was **before** the fix, with 52 tests
([exactly what's there, and the few small files added so its 2019 tests run on today's
Python](examples/tqdm/QDEBUG_DEMO.md)). The shop bugs in [More practice](#more-practice-bugs-planted-in-a-small-program)
are the opposite: a small program written for qdebug, with bugs planted on purpose.

Your job: find tqdm's bug **without reading its code**, by answering 7 questions.

### Step 1: Start qdebug

In the qdebug folder, with your virtual environment switched on:

```bash
qdebug debug --project examples/tqdm
```

qdebug runs tqdm's tests. One of them fails:

```text
Step 1 of 3: Run the tests ────────────────────────────────────────────────
52 tests ran:  50 passed   1 failed
┌─ The failing test ─────────────────────────────────────────────────────────┐
│ tqdm/tests/tests_tqdm.py::test_nototal                                     │
│ TypeError: unsupported operand type(s) for *=: 'NoneType' and 'int'        │
└────────────────────────────────────────────────────────────────────────────┘
```

Here is that test. You don't need to understand tqdm to follow it:

```python
def test_nototal():
    """Test unknown total length"""
    with closing(StringIO()) as our_file:
        for i in tqdm((i for i in range(10)), file=our_file, unit_scale=10):
            pass
        assert "100it" in our_file.getvalue()
```

It loops over 10 items with a progress bar. Two details matter:

- The items come from a *generator* `(i for i in range(10))`, which has no length, so tqdm **can't know the
  total**. That's allowed: tqdm should just count, without a percentage.
- `unit_scale=10` means "count every item as 10". After 10 items, the bar should say `100it` (100 items).

Instead, the program crashes with a `TypeError`: something tried to multiply `None` by a number.

### Step 2: Find the broken function

qdebug now shows you **one call** of a function: what went in, and what came out. You only judge whether the
result makes sense. (qdebug also shows the functions it suspects most; you can ignore that.)

```text
┌─ Question 1 ───────────────────────────────────────────────────────────────┐
│ Use `self.sp` and to display `msg` in the specified `pos`.                 │
│ tqdm.display was called with:                                              │
│ self  {'iterable': <generator object ...>, 'desc': '', 'total': None, ...  │
│ msg   None                                                                 │
│ pos   None                                                                 │
│                                                                            │
│ and it raised an error:                                                    │
│ TypeError: TypeError("unsupported operand type(s) for *=: 'NoneType' ...   │
└───────────────────────────────────────────────────────── tqdm/_tqdm.py:1283 ─┘
  Is that the right result? (y yes, n no, ? not sure, h more) >
```

`display` draws the progress bar. Drawing a progress bar should never crash, so this result is wrong: type
**n**.

**Question 2** asks about `tqdm.__repr__`, which turns the bar into text. It crashed with the same error.
Turning a bar into text shouldn't crash either: type **n**.

```text
┌─ Question 3 ───────────────────────────────────────────────────────────────┐
│ Public API for read-only member access                                     │
│ tqdm.format_dict was called with:                                          │
│ self  {'iterable': <generator object ...>, 'desc': '', 'total': None, ...  │
│                                                                            │
│ and it returned:                                                           │
│ {'n': 0, 'total': None, 'elapsed': 0, 'ncols': None, 'prefix': '',         │
│ 'ascii': True, 'unit': 'it', 'unit_scale': 10, 'rate': None,               │
│ 'bar_format': None, 'postfix': None, 'unit_divisor': 1000}                 │
└────────────────────────────────────────────────────────── tqdm/_tqdm.py:950 ─┘
  Is that the right result? (y yes, n no, ? not sure, h more) >
```

This one just collects the bar's settings. Check them against the test: `total` is `None` (right, the
generator has no length), `unit_scale` is `10` (right, the test asked for that), and `n` (items counted so
far) is `0` (right, the bar is just starting). Everything is correct: type **y**.

```text
┌─ Question 4 ───────────────────────────────────────────────────────────────┐
│ Return a string-based progress bar given some parameters                   │
│ tqdm.format_meter was called with:                                         │
│ n             0                                                            │
│ total         None                                                         │
│ unit_scale    10                                                           │
│ ...                                                                        │
│ and it raised an error:                                                    │
│ TypeError: TypeError("unsupported operand type(s) for *=: 'NoneType' ...   │
└────────────────────────────────────────────────────────── tqdm/_tqdm.py:252 ─┘
  Is that the right result? (y yes, n no, ? not sure, h more) >
```

`format_meter` gets exactly the correct settings from Question 3, and should turn them into a progress bar.
It crashed instead: type **n**.

Now qdebug knows which function is broken: `format_meter` got correct inputs and still went wrong.

### Step 3: Find the exact line

qdebug replays `format_meter` and stops at different lines, showing you the variables at that moment.

**Line check 1** shows the function at its end, raising the `TypeError`. We already know that's wrong:
type **n**.

```text
┌─ Line check 2 ─────────────────────────────────────────────────────────────┐
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
│ ...                                                                        │
└──────────────────────────────────────────────────────────── tqdm/_tqdm.py ─┘
  Still on the right track here? (y yes, n no, ? not sure, h more) >
```

This is the tricky one. Every variable still has a fine value. But line 323 is about to multiply `total` by
10, and `total` is `None` (there is no total). A correct program would never try that, so it should never be
at this line with these values: type **n**.

> **The rule for line checks:** answer **n** if a variable has a wrong value, **or** if a correct program
> would never be at this line with these values.

**Line check 3** stops just before line 322, `if unit_scale and unit_scale not in (True, 1):`. Nothing has
gone wrong yet: the values are the same correct ones from Question 3. Type **y**.

### Step 4: The answer

```text
┌─ Found it ─────────────────────────────────────────────────────────────────┐
│ tqdm/_tqdm.py, line 322, in tqdm.format_meter                              │
│                                                                            │
│ 320                                                                        │
│ 321            # apply custom scale if necessary                           │
│ 322 >>         if unit_scale and unit_scale not in (True, 1):              │
│ 323                total *= unit_scale                                     │
│ 324                n *= unit_scale                                         │
│                                                                            │
│ Confidence: High   Your answers point directly at this code.               │
└────────────────────────────────────────────────────────────────────────────┘
7 questions to search a project with 109 functions, without reading its code.
```

Things were fine before line 322 and wrong right after it, so line 322 is the culprit. It checks the scale,
but forgets to check that there **is** a total before line 323 multiplies it. That's exactly the bug tqdm's
developers fixed: [their fix](https://github.com/tqdm/tqdm/commit/964dee631d0ed30e2f799b42fc58ba5e73795a08)
adds an `if total:` check right there.

You found a real bug in a 2,600-line library with 7 answers: **n, n, y, n, n, n, y**.

### All the keys you can press

| key | for a function call | for a line check |
|---|---|---|
| **y** | the result is right | still on the right track |
| **n** | the result is wrong | a value is wrong, or this line shouldn't be reached |
| **?** | I'm not sure (qdebug works around it) | I'm not sure |
| **i** | the *inputs* already look wrong | – |
| **t** | I trust this function, stop asking about it | – |
| **s** | show the function's code | show the function's code |
| **e** | show how this function behaved in tests that pass | – |
| **w** | why are you asking this? | – |
| **u** | undo my last answer | undo my last answer |
| **q** | stop and show what you have so far | stop |
| **h** | help | help |

Don't worry about making a mistake: qdebug treats every answer as a clue that might be wrong, checks its
conclusion, and you can always press **u** to undo.

### No luck installing? Run the demo in Docker

[Docker](https://www.docker.com/products/docker-desktop/) runs qdebug in a ready-made Linux box, so it works
the same on Windows, macOS and Linux and you don't need to install Python. Install **Docker Desktop**, open it
and wait until it says *Engine running*. Then, in a terminal in the qdebug folder (`git clone` and `cd qdebug`
from [Install](#1-install)):

```bash
docker build -t qdebug .
```

This takes a minute or two the first time. Then start the demo:

```bash
docker run -it --rm qdebug
```

You get the same questions as above. Any other qdebug command works too, by adding it to the end, for example
`docker run -it --rm qdebug qdebug debug --project benchmarks/shop/variants/bug_01`.

### More practice: bugs planted in a small program

qdebug also comes with a small online-shop program and five copies of it, each with one bug planted in it.
They're smaller than tqdm, so they make quick practice. Make the copies once:

```bash
qdebug variants --suite shop
```

Then debug the first one:

```bash
qdebug debug --project benchmarks/shop/variants/bug_01
```

Two tests fail; pick **1**. Hint: read each function's description (the first line of each question). With
the answers **n, n, n, n**, qdebug lands on line 24, `if quantity > 10:`, which should be `>= 10`.

Change the end to `bug_02` up to `bug_05` for the others. There are 34 more in a second practice program
(making the copies takes about a minute), in `benchmarks/planner/variants/`:

```bash
qdebug variants --suite planner
```

```bash
qdebug debug --project benchmarks/planner/variants/p09-weekend-boundary
```

---

## 3. Use it on your own project

Point qdebug at any folder whose pytest tests have at least one failure:

```bash
qdebug debug --project path/to/your/project
```

If you are already inside your project's folder, `qdebug debug` on its own is enough. Two tips:

- If your project needs packages that are installed in **its own** virtual environment, tell qdebug where
  that environment is: `qdebug debug --project myproject --python myproject/.venv`
- To just see which functions look most suspicious, without any questions: `qdebug rank --project myproject`

---

## 4. Optional: let Claude help

qdebug can ask **Claude**, Anthropic's AI model, to look at the failing test first, answer questions for
you, and explain the bug at the end with a suggested fix. You don't need this: everything above works
without it.

You need Python **3.11 or newer** and an **Anthropic API key**. The API is paid, but qdebug uses the small,
cheap model (Claude Haiku); a debugging session should cost well under one cent.

### Step 1: Get an API key

Sign in to the Claude Console at [platform.claude.com](https://platform.claude.com), open **API Keys**,
and create a key.
It starts with `sk-ant-`. Copy it.

> **Keep your key secret.** Never paste it into your code, never commit it to git, and don't share it.
> Anyone with the key can spend money on your account.

### Step 2: Install the Claude add-on

With your virtual environment switched on, in the qdebug folder:

```bash
pip install -e ".[ai]"
```

### Step 3: Give qdebug your key

The key goes in an *environment variable* called `ANTHROPIC_API_KEY`, which qdebug reads when it starts.
Replace `sk-ant-...` with your key.

**Windows (Command Prompt)**: for the current window only:

```bash
set ANTHROPIC_API_KEY=sk-ant-...
```

To keep it for every new window, use `setx ANTHROPIC_API_KEY sk-ant-...` once, then open a new window.

**Windows (PowerShell)**: for the current window only:

```bash
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

**macOS and Linux**: for the current window only:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

To keep it, add that same `export` line to the end of `~/.zshrc` (macOS) or `~/.bashrc` (Linux), then open
a new terminal.

### Step 4: Debug with Claude

Choose how much Claude does:

| command | who answers the questions |
|---|---|
| `qdebug debug --project ... --ai` | **you**; Claude takes a first look and explains the bug at the end |
| `qdebug debug --project ... --oracle hybrid` | **Claude** when it's sure, **you** when it isn't (it shows you its guess) |
| `qdebug debug --project ... --oracle claude` | **Claude** answers everything; you just watch |

For example, the tqdm demo bug with Claude helping:

```bash
qdebug debug --project examples/tqdm --oracle hybrid
```

In Docker, set the key in your terminal as above, then pass it into the container with `-e`:

```bash
docker run -it --rm -e ANTHROPIC_API_KEY qdebug qdebug debug --project examples/tqdm --oracle hybrid
```

If the add-on isn't installed or your Python is too old, qdebug stops and tells you what to install. If
the key is missing or wrong, `--oracle claude` stops too, while `--ai` and `--oracle hybrid` carry on with
you answering every question.

Want to teach Claude about your project? Run `qdebug init-agent --project path/to/your/project`. It copies
Claude's instructions into `.qdebug/agent.md` inside your project, where you can edit them, for example to
explain that all prices are in cents.

---

## Troubleshooting

**`python` is not recognized / command not found.** Python isn't installed, or wasn't added to PATH.
Reinstall it from [python.org](https://www.python.org/downloads/) (on Windows tick *"Add python.exe to
PATH"*). On macOS and Linux use `python3` instead of `python`.

**`qdebug` is not recognized / command not found.** Your virtual environment isn't switched on. Run
`.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (macOS/Linux) from the qdebug folder.
`python -m qdebug` also works anywhere `qdebug` would.

**PowerShell says "running scripts is disabled on this system".** Use Command Prompt (`cmd`) instead,
where `.venv\Scripts\activate` works.

**`project directory not found: examples/tqdm`.** Your terminal isn't in the qdebug folder: `cd qdebug`
first.

**`project directory not found: benchmarks/shop/variants/bug_01`.** You haven't made the practice copies yet
(`qdebug variants --suite shop`, see [More practice](#more-practice-bugs-planted-in-a-small-program)), or
your terminal isn't in the qdebug folder.

**Docker says it can't connect (`error during connect`, `Cannot connect to the Docker daemon`).** Docker
Desktop isn't running. Open it and wait until it says *Engine running*.

**Docker says `the input device is not a TTY`.** You're in Git Bash on Windows. Use Command Prompt or
PowerShell instead, or put `winpty` in front: `winpty docker run -it --rm qdebug`.

**`no failing test in ...`.** All of that project's tests pass, so there is nothing to debug.

**`the Claude features need ...`.** Follow what the message says: install the add-on
(`pip install -e ".[ai]"`), use Python 3.11 or newer, or set your API key (Step 3 above).

---

## Learn more

- [docs/DETAILS.md](docs/DETAILS.md): how qdebug works, every option, and the measured results
- [results/](results/): the benchmark results, including Claude Haiku answering every question
- [CHANGELOG.md](CHANGELOG.md): what changed in each version

qdebug is open source under the [MIT license](LICENSE).
