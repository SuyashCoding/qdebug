# qdebug

**qdebug helps you find the bug behind a failing test, by asking you simple yes/no questions.**

When a test fails, you usually have to read a lot of code to work out where the mistake is. qdebug does the
searching for you. It runs your tests, then shows you one function call at a time, for example
*"`quantity_discount_rate(10)` returned `0.05`. Is that right?"*, and you answer **y** (yes) or **n** (no).
Each answer rules out a big part of the program. After a handful of questions it points at the exact line
that is wrong.

It works with Python projects that use [pytest](https://docs.pytest.org/) for their tests.

- [1. Install](#1-install)
- [2. Run the demo](#2-run-the-demo)
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

## 2. Run the demo

qdebug comes with a small online-shop program (in `benchmarks/shop/project`) and five copies of it, each
with one bug planted in it. In this demo you'll find the bug in the first copy, **without reading its code**.

### Step 1: Make the buggy copies

```bash
qdebug variants --suite shop
```

This creates the five buggy copies in `benchmarks/shop/variants/` and checks that each one really has a
failing test. It takes a few seconds. You only need to do it once.

### Step 2: Start qdebug on the first bug

```bash
qdebug debug --project benchmarks/shop/variants/bug_01
```

qdebug runs all 35 tests of the shop. Two of them fail:

```text
Step 1 of 3: Run the tests ────────────────────────────────────────────────
35 tests ran:  33 passed   2 failed
1  tests/test_pricing.py::test_line_total_bulk      AssertionError: assert 1890 == 1791
2  tests/test_invoice.py::test_bulk_invoice_qty_t…  AssertionError: assert 1890 == 1791
  Which test should we debug? (1-2) >
```

Type **1** and press Enter. qdebug lists the simplest test first, because it needs the fewest questions.

```text
┌─ The failing test ─────────────────────────────────────────────────────────┐
│ tests/test_pricing.py::test_line_total_bulk                                │
│ AssertionError: assert 1890 == 1791                                        │
│ +  where 1890 = line_total(LineItem(sku='PEN-001', quantity=10, ...))      │
└────────────────────────────────────────────────────────────────────────────┘
```

So: 10 pens at 1.99 each should cost 17.91 after a discount, but the program says 18.90.

### Step 3: Find the broken function

qdebug now shows you **one call** of a function: what went in, and what came out.

```text
┌─ Question 1 ───────────────────────────────────────────────────────────────┐
│ Bulk discount rate: 10% from 10 units, 5% from 5 units, otherwise none.    │
│ quantity_discount_rate was called with:                                    │
│ quantity  10                                                               │
│                                                                            │
│ and it returned:                                                           │
│ 0.05                                                                       │
└────────────────────────────────────────────────────────── shop/pricing.py:22 ─┘
  Is that the right result? (y yes, n no, ? not sure, h more) >
```

Read the first line, the function's description: *10% from 10 units*. The function got exactly 10 units,
so it should have returned `0.10` (10%), but it returned `0.05` (5%). That's wrong, so type **n**.

### Step 4: Find the exact line

qdebug now knows which function is broken. It replays that function and stops at different lines, showing
you the variables at that moment.

```text
┌─ Line check 1 ─────────────────────────────────────────────────────────────┐
│ When quantity_discount_rate finished:                                      │
│ The variables held:                                                        │
│ quantity  10                                                               │
│ Returning: 0.05                                                            │
└────────────────────────────────────────────────────────────────────────────┘
  Still on the right track here? (y yes, n no, ? not sure, h more) >
```

It's returning `0.05`, which we already know is wrong: type **n**.

```text
┌─ Line check 2 ─────────────────────────────────────────────────────────────┐
│ Inside quantity_discount_rate, just before line 27 runs:                   │
│ 24       if quantity > 10:                                                 │
│ 25           return 0.10                                                   │
│ 26       if quantity >= 5:                                                 │
│ 27 >         return 0.05                                                   │
│ 28       return 0.0                                                        │
│ (line 27 has not run yet)                                                  │
│                                                                            │
│ The variables held:                                                        │
│ quantity  10                                                               │
└────────────────────────────────────────────────────────────────────────────┘
  Still on the right track here? (y yes, n no, ? not sure, h more) >
```

This one is trickier. `quantity` is still 10, which is fine. But the program is about to
`return 0.05`, and with 10 units a correct program would never get here: it should already have returned
`0.10` at line 25. So something has already gone wrong: type **n**.

> **The rule for line checks:** answer **n** if a variable has a wrong value, **or** if a correct program
> would never be at this line with these inputs.

Line check 3 asks the same about line 26 (`if quantity >= 5:`). Again, a correct program would already
have returned at line 25, so type **n**.

### Step 5: The answer

```text
┌─ Found it ─────────────────────────────────────────────────────────────────┐
│ shop/pricing.py, line 24, in quantity_discount_rate                        │
│                                                                            │
│ 22    def quantity_discount_rate(quantity):                                │
│ 23        """Bulk discount rate: 10% from 10 units, 5% from 5 units, ..."""│
│ 24 >>     if quantity > 10:                                                │
│ 25            return 0.10                                                  │
│ 26        if quantity >= 5:                                                │
│                                                                            │
│ Confidence: High   Your answers point directly at this code.               │
│ The bad call: quantity_discount_rate(quantity=10) → 0.05                   │
└────────────────────────────────────────────────────────────────────────────┘
4 questions to search a project with 39 functions, without reading its code.
```

Line 24 says `quantity > 10`, but the description says *from* 10 units, so it should be `quantity >= 10`.
That's the bug: you found it with 4 answers: **1, n, n, n, n**.

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

### Try the other bugs

Each of these has a different kind of bug. Try to find it before qdebug tells you:

```bash
qdebug debug --project benchmarks/shop/variants/bug_03
```

Change the number at the end to `bug_02`, `bug_04` or `bug_05` for the others. There are 34 more in a
second practice program. Make those copies once (it takes about a minute), then pick any folder in
`benchmarks/planner/variants/`:

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

For example, the demo bug with Claude helping:

```bash
qdebug debug --project benchmarks/shop/variants/bug_01 --oracle hybrid
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

**`project directory not found: benchmarks/shop/variants/bug_01`.** You skipped
[Step 1 of the demo](#step-1-make-the-buggy-copies) (`qdebug variants --suite shop`), or your terminal
isn't in the qdebug folder (`cd qdebug`).

**`no failing test in ...`.** All of that project's tests pass, so there is nothing to debug.

**`the Claude features need ...`.** Follow what the message says: install the add-on
(`pip install -e ".[ai]"`), use Python 3.11 or newer, or set your API key (Step 3 above).

---

## Learn more

- [docs/DETAILS.md](docs/DETAILS.md): how qdebug works, every option, and the measured results
- [results/](results/): the benchmark results, including Claude Haiku answering every question
- [CHANGELOG.md](CHANGELOG.md): what changed in each version

qdebug is open source under the [MIT license](LICENSE).
