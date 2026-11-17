# qdebug

**qdebug helps you find the bug behind a failing test, by asking you simple yes/no questions.**

When a test fails, you usually have to read a lot of code to work out where the mistake is. qdebug does the
searching for you. It runs the tests, then shows you one function call at a time (what went in, what came
out) and asks *"Is that the right result?"*. You answer **y** (yes) or **n** (no). Each answer rules out a
big part of the program, and after a handful of questions qdebug points at the exact line that is wrong.

It works with Python projects that test with [pytest](https://docs.pytest.org/).

| | Section | What it's for |
|---|---|---|
| 1 | [Try the demo in Docker](#1-try-the-demo-in-docker) | **Start here.** Find a real bug in a real library. You only need Docker. |
| 2 | [Install qdebug on your computer](#2-install-qdebug-on-your-computer) | Windows, macOS and Linux, to use qdebug without Docker. |
| 3 | [Use qdebug on your own project](#3-use-qdebug-on-your-own-project) | Your own code, or any public project from GitHub. |
| 4 | [Optional: let Claude help](#4-optional-let-claude-help) | An AI that can answer the questions for you. Not needed. |
| | [Troubleshooting](#troubleshooting) | If something doesn't work. |

---

## 1. Try the demo in Docker

Docker runs programs inside a *container*: a small, ready-made Linux computer. The qdebug container has
Python, qdebug and a buggy copy of a real library already inside, so it works the same on Windows, macOS
and Linux, and you don't have to install Python.

### The bug you'll find

[**tqdm**](https://github.com/tqdm/tqdm) (from *taqaddum*, Arabic for "progress") is a Python library that
adds a **progress bar** to any loop. You wrap the thing you loop over in `tqdm(...)`:

```python
from tqdm import tqdm

for file in tqdm(files_to_download):
    download(file)
```

and while the loop runs, the terminal shows how far along it is, how fast it's going and how long is left:

```text
 76%|███████████████▏    | 763/1000 [00:02<00:00, 380.12it/s]
```

It's one of the most downloaded packages on [PyPI](https://pypi.org/project/tqdm/), Python's package store.
If you've ever installed a machine-learning model or dataset in Python and watched a bar fill up, that was
probably tqdm.

**Why this counts as a real program:**

- **Nobody wrote it for this demo.** It's tqdm's own code, written over years by its developers and many
  outside contributors, for real users: 10 source files, about 2,600 lines, with classes, background
  threads and locks. qdebug has to search through 109 functions.
- **The bug really happened.** In 2019, tqdm crashed when you used `unit_scale` on a loop whose length it
  couldn't know. tqdm's developers
  [fixed it in public](https://github.com/tqdm/tqdm/commit/964dee631d0ed30e2f799b42fc58ba5e73795a08), and
  the failing test you'll see is the one *they* wrote for it.
- **Researchers use it to test debugging tools.** This exact bug is "tqdm bug 4" in
  [BugsInPy](https://github.com/soarsmu/BugsInPy), a collection of real bugs from 17 real Python projects
  that research papers use to measure debugging tools.

The folder `examples/tqdm` holds tqdm's code exactly as it was **before** the fix
([what's in it, and the few small files added so its 2019 tests run on today's Python](examples/tqdm/QDEBUG_DEMO.md)).

### Step 1: Install Docker Desktop

Download it from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
(free for personal and school use) and install it. Open **Docker Desktop** and wait until the bottom left
corner says **Engine running**. You don't need to sign in.

### Step 2: Open a terminal

- **Windows:** press the Windows key, type `cmd`, press Enter.
- **macOS:** press Cmd+Space, type `Terminal`, press Enter.
- **Linux:** open your terminal app.

Type each command below into it and press Enter after each one.

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

The `.` at the end matters: it means "this folder". This takes a minute or two the first time, and you only
need to do it once.

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

It loops over 10 items with a progress bar. Two details matter:

- The items come from a *generator*, `(i for i in range(10))`, which has no length. So tqdm **can't know the
  total**, and `total` is `None`. That's allowed: tqdm should just count, without a percentage.
- `unit_scale=10` means "count every item as 10". After 10 items, the bar should say `100it` (100 items).

Instead, the program crashes: something tried to multiply `None` by a number.

### Step 6: Answer the questions

qdebug asks 7 questions. Here are all the answers at once:

| qdebug asks about | What it shows | Your answer | Why |
|---|---|---|---|
| Question 1 | `tqdm.display` raised an error | `n` | Drawing a progress bar should never crash. |
| Question 2 | `tqdm.__repr__` raised an error | `n` | Turning the bar into text should never crash. |
| Question 3 | `tqdm.format_dict` returned the bar's settings | `y` | The settings match the test. |
| Question 4 | `tqdm.format_meter` raised an error | `n` | It got correct settings and still crashed. |
| Line check 1 | `format_meter` at its end, raising the error | `n` | The crash is wrong. |
| Line check 2 | just before line 323, `total *= unit_scale` | `n` | It's about to multiply `None`. |
| Line check 3 | just before line 322, the `if` above it | `y` | Nothing has gone wrong yet. |

Type the answer and press **Enter**. Below, each question is shown as qdebug shows it (shortened a little),
with the reason for the answer. Under each question qdebug also lists the functions it suspects most right
now; you can ignore that.

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
  Is that the right result? (y yes, n no, ? not sure, h more) >
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
  Is that the right result? (y yes, n no, ? not sure, h more) >
```

**Answer: `y`.** This just collects the bar's settings, and they match the test: `total` is `None` (the
generator has no length), `unit_scale` is `10` (the test asked for that) and `n`, the count so far, is `0`
(the bar is just starting).

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
  Is that the right result? (y yes, n no, ? not sure, h more) >
```

**Answer: `n`.** `format_meter` got the correct settings from Question 3 and should turn them into a
progress bar. It crashed instead.

qdebug now knows which function is broken: `format_meter` got correct inputs and still went wrong. Next it
looks for the line. It replays `format_meter`, stops at different lines and shows you the variables. The
question changes to *"Still on the right track here?"*, and the rule is:

> Answer **n** if a variable already has a wrong value, **or** if a correct program would never be at this
> line with these values. Otherwise answer **y**.

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

**Answer: `n`.** This is the end of the function, and it's crashing. We already know that's wrong.

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
│ ...                                                                        │
╰───────────────────────────────────────────────────────────── tqdm/_tqdm.py ─╯
  Still on the right track here? (y yes, n no, ? not sure, h more) >
```

**Answer: `n`.** This is the tricky one. Every variable still has a fine value, but line 323 is about to
multiply `total` by 10, and `total` is `None`. A correct program would never be here with these values.

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
│ ...                                                                        │
╰───────────────────────────────────────────────────────────── tqdm/_tqdm.py ─╯
  Still on the right track here? (y yes, n no, ? not sure, h more) >
```

**Answer: `y`.** The values are the same correct ones as in Question 3, and the program hasn't done anything
wrong yet. It's fine for it to reach this `if`.

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

Things were fine just before line 322 and wrong just after it, so line 322 is the culprit. It checks the
scale, but forgets to check that there **is** a total before line 323 multiplies it. That's exactly what
tqdm's developers fixed: [their fix](https://github.com/tqdm/tqdm/commit/964dee631d0ed30e2f799b42fc58ba5e73795a08)
adds an `if total:` check right there.

You found a real bug in a 2,600-line library with 7 answers, without reading its code.

### More to try in Docker

The container also has 5 smaller practice bugs, planted on purpose in a small online-shop program written
for qdebug. Try the first one:

```bash
docker run -it --rm qdebug qdebug debug --project benchmarks/shop/variants/bug_01
```

Two tests fail: type `1` to pick the first. Then read each function's description (the first line of each
question) and decide if the result matches it. The answers are `n`, `n`, `n`, `n`, and qdebug lands on
line 24, `if quantity > 10:`, which should be `>= 10`. Change `bug_01` to `bug_02` up to `bug_05` for the
others.

To try qdebug on your own code in Docker, see [Use qdebug on your own project](#3-use-qdebug-on-your-own-project).

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

Don't worry about making a mistake: qdebug treats every answer as a clue that might be wrong, checks its
conclusion, and you can always press `u` to undo.

---

## 2. Install qdebug on your computer

Use this to run qdebug without Docker. You need **Python 3.10 or newer** and **git**. Type each command into
a terminal and press Enter after each one.

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
4. Download qdebug and go into its folder (skip this if you already did it for Docker):

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
2. Download qdebug and go into its folder (skip this if you already did it for Docker):

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

### Check it worked

```bash
qdebug --version
```

This should print `qdebug 0.2.0`.

### Run the demo without Docker

In the qdebug folder, with the virtual environment switched on:

```bash
qdebug debug --project examples/tqdm
```

It's the same tqdm bug, with the same questions and the same answers as
[in Docker](#step-6-answer-the-questions).

For the practice bugs, make them once, then debug the first:

```bash
qdebug variants --suite shop
```

```bash
qdebug debug --project benchmarks/shop/variants/bug_01
```

---

## 3. Use qdebug on your own project

qdebug works on any Python project that has **pytest tests with at least one failing test**. qdebug runs the
project's tests, so the project's own packages must be installed where qdebug runs.

To try it on a project that has no failing test, plant a bug yourself: change one small thing in its code,
for example a `>=` into a `>`, run the tests to check one fails, and see whether qdebug finds your change.

### With qdebug installed (section 2)

1. Get the project. For a public project on GitHub, download it (replace the address with the project's):

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

   If you are already in the project's folder, `qdebug debug` on its own is enough.

If the project already has its **own** virtual environment with everything installed, skip step 2 and tell
qdebug where it is instead: `qdebug debug --project some-project --python some-project/.venv` (that
environment needs pytest).

### With Docker

First build the container ([Steps 1 to 4 of the demo](#1-try-the-demo-in-docker)). Then, in a terminal, go
into **your project's folder** (`cd path/to/some-project`) and start the container with that folder inside it.
The command depends on your terminal:

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

You're now inside the container, in your project's folder (`/work`). Install the project's packages
(`pip install -e .` or `pip install -r requirements.txt`, as above), then run:

```bash
qdebug debug
```

Type `exit` to leave the container. Changes to your project's files inside `/work` are real changes to the
folder on your computer. Anything you install inside the container is gone when you leave it.

### Handy extras

- To just see which functions look most suspicious, without any questions: `qdebug rank --project some-project`
- To make qdebug only run some of the tests (faster on big projects):
  `qdebug debug --project some-project --suite tests/test_one_file.py`

---

## 4. Optional: let Claude help

qdebug can ask **Claude**, Anthropic's AI model, to look at the failing test first, answer questions for
you, and explain the bug at the end with a suggested fix. You don't need this: everything above works
without it.

You need an **Anthropic API key**. The API is paid, but qdebug uses the small, cheap model (Claude Haiku);
a debugging session should cost well under one cent.

### Step 1: Get an API key

Sign in to the Claude Console at [platform.claude.com](https://platform.claude.com), open **API Keys**,
and create a key. It starts with `sk-ant-`. Copy it.

> **Keep your key secret.** Never paste it into your code, never commit it to git, and don't share it.
> Anyone with the key can spend money on your account.

### Step 2: Give qdebug your key

The key goes in an *environment variable* called `ANTHROPIC_API_KEY`, which qdebug reads when it starts.
Replace `sk-ant-...` with your key. This sets it for the current terminal window only.

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

To keep it for every new window: on Windows run `setx ANTHROPIC_API_KEY sk-ant-...` once; on macOS or Linux,
add the `export` line to the end of `~/.zshrc` (macOS) or `~/.bashrc` (Linux).

### Step 3: Debug with Claude

Choose how much Claude does by adding one of these to the end of a `qdebug debug` command:

| add this | who answers the questions |
|---|---|
| `--ai` | **you**; Claude takes a first look and explains the bug at the end |
| `--oracle hybrid` | **Claude** when it's sure, **you** when it isn't (it shows you its guess) |
| `--oracle claude` | **Claude** answers everything; you just watch |

**In Docker** (the container already has everything Claude needs), `-e ANTHROPIC_API_KEY` passes your key
into the container:

```bash
docker run -it --rm -e ANTHROPIC_API_KEY qdebug qdebug debug --project examples/tqdm --oracle hybrid
```

**Without Docker** you need Python **3.11 or newer**. Install the Claude add-on once, in the qdebug folder
with the virtual environment switched on:

```bash
pip install -e ".[ai]"
```

Then:

```bash
qdebug debug --project examples/tqdm --oracle hybrid
```

If the add-on isn't installed or your Python is too old, qdebug stops and tells you what to install. If
the key is missing or wrong, `--oracle claude` stops too, while `--ai` and `--oracle hybrid` carry on with
you answering every question.

Want to teach Claude about your project? Run `qdebug init-agent --project path/to/your/project`. It copies
Claude's instructions into `.qdebug/agent.md` inside your project, where you can edit them, for example to
explain that all prices are in cents.

---

## Troubleshooting

### Docker

**`error during connect` or `Cannot connect to the Docker daemon`.** Docker Desktop isn't running. Open it
and wait until it says *Engine running*.

**`unable to find image 'qdebug:latest'` or `pull access denied for qdebug`.** You haven't built the
container yet: run `docker build -t qdebug .` in the qdebug folder ([Step 4](#step-4-build-the-container)).

**`failed to read dockerfile` or `no such file or directory`.** Your terminal isn't in the qdebug folder:
`cd qdebug` first.

**`the input device is not a TTY`.** You're in Git Bash on Windows. Use Command Prompt or PowerShell
instead, or put `winpty` in front: `winpty docker run -it --rm qdebug`.

**qdebug shows "Best guess ... You stopped early" without waiting for your answer.** You left out `-it` in
`docker run -it --rm qdebug`. It's what lets you type into the container.

### Without Docker

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

**`project directory not found: benchmarks/shop/variants/bug_01`.** You haven't made the practice bugs yet:
run `qdebug variants --suite shop` once.

### Both

**`no failing test in ...`.** All of that project's tests pass, so there is nothing to debug.

**`ModuleNotFoundError` in the test results.** The project's own packages aren't installed where qdebug
runs. See [Use qdebug on your own project](#3-use-qdebug-on-your-own-project).

**`the Claude features need ...`.** Follow what the message says: install the add-on
(`pip install -e ".[ai]"`), use Python 3.11 or newer, or set your API key.

---

## Learn more

- [docs/DETAILS.md](docs/DETAILS.md): how qdebug works, every option, and the measured results
- [results/](results/): the benchmark results, including Claude Haiku answering every question
- [CHANGELOG.md](CHANGELOG.md): what changed in each version

qdebug is open source under the [MIT license](LICENSE).
