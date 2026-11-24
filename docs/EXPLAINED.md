# qdebug, explained like you've never heard of it

This is the no-jargon version. If you've never seen qdebug before (or you read the paper and went "huh?"),
start here. The [paper](paper/qdebug-paper.docx) says the same things in about a quarter of the words, and
[DETAILS.md](DETAILS.md) has every option and number.

---

## The problem

You write some code. You also write *tests*: little programs that run your code and check the answer.
Something like "if I add a $10 item and a $5 item to the cart, the total should be $15."

One day a test fails. It says "expected 15, got 20." Cool, now you know *something* is broken. But **where?**
The test only tells you the final answer was wrong. The actual mistake could be in any of the dozens (or
thousands) of functions that ran on the way there. So you start reading code, adding print statements,
stepping through with a debugger... it can take ages, especially in code someone else wrote.

## The idea

qdebug turns finding the bug into a game of **20 questions**.

It runs the failing test and secretly records every function call that happens: what went into each one and
what came out. Then it shows you one call at a time and asks:

> `apply_discount` was called with `price = 100, percent = 10` and returned `110`. **Is that right?**

You don't need to read any code to answer. You just need to know what the function is *supposed* to do. A
10% discount on 100 should be 90, not 110, so you say **n** (no).

Each answer rules out a big chunk of the program:

- If a call's answer is **right**, the bug isn't inside that call (or anything it called), so qdebug stops
  looking there.
- If a call's answer is **wrong**, but everything *it* called gave right answers, then the bug must be in
  that function's own code. Found it!

After a few questions qdebug knows which function is broken. Then it zooms in: it replays that one function
line by line, shows you the variables at different points, and asks "does this still look OK?" until it can
point at the exact line.

That's the whole thing. **You answer easy yes/no questions about values; qdebug does the searching.**

## The clever bits (still in plain English)

### 1. It guesses where to look first

Before asking anything, qdebug runs *all* your tests, not just the failing one, and notes which lines of
code each test ran. Then it uses a simple idea: **code that the failing tests run a lot, but the passing
tests rarely run, is suspicious.** If every failing test goes through `apply_discount` and almost no passing
test does, that's a good first guess.

This trick has a name in research: *spectrum-based fault localization* (SBFL), and the formula qdebug uses
is called **Ochiai**. Lots of tools stop here and just hand you a ranked list ("here are the 10 most
suspicious functions, good luck"). The problem is that people don't actually read those lists top to
bottom, and the real bug is often at #7 or #30. qdebug only uses this list as a **starting hunch**.

### 2. It asks the most useful question, not just the next one

Classic "ask about every call" debuggers (the idea is from 1983 and is called *algorithmic debugging*) go in
a fixed order, like top to bottom. qdebug instead picks **the question whose answer will tell it the most**.
It's like the 20 questions trick of asking "is it an animal?" before "is it a cat?", because the first one
splits the possibilities in half. In math terms it picks the question with the biggest *expected
information gain*, but you can just think of it as "the question that rules out the most."

### 3. It doesn't fully trust your answers

People make mistakes. If you answer one question wrong, a normal algorithmic debugger confidently walks off
into the wrong part of the program and never comes back.

qdebug keeps a **probability for every call** ("I'm 60% sure the bug is in here") and treats each answer as
strong evidence, not as gospel (by default it assumes any answer has a 10% chance of being wrong). One bad
answer just lowers some probabilities a bit; the next few answers usually outvote it. It stops when one
function holds at least 90% of the probability, or when it has airtight proof (a call that's wrong with all
of its sub-calls right).

### 4. It records a little, then more if needed

Recording every value of every call in a big program is slow and huge. So qdebug first records full details
only for the most suspicious **5%** of functions. If that's not enough to find the bug, it reruns the test
and records more (10%, 15%, 25%, 50%, then everything).

### 5. It finds the line, not just the function

Once it knows the function, it replays that call and stops before different lines to show you the
variables. The question becomes "still on the right track here?", and the rule is:

> Say **no** if a variable already has a wrong value, **or** if a correct program would never be at this line
> with these values. Otherwise say **yes**.

The line where things go from "fine" to "wrong" is the bug. This part also uses probabilities, so one
mistaken answer doesn't wreck it.

### 6. It notices when there's more than one bug

Sometimes 6 tests fail, but they're caused by 2 different bugs. That confuses the "suspicious code" trick,
because it assumes there's one bug. So qdebug first **groups the failing tests** by the bug that probably
causes each group (tests that crash the same way at the same line go together, and groups merge if one line
explains both). You pick a test from one group, and qdebug only uses that group to make its first guess. At
the end it tells you which other failing tests the same bug probably explains.

### 7. Extra rules learned from mistakes ("tuned" vs "baseline")

We watched qdebug fail on practice bugs and added a few rules of thumb. For example: "if the program
crashed, the functions the error passed through are extra suspicious." The plain version with none of these
extra rules is called the **baseline** policy, and the version with them is **tuned** (the default). We
tested whether these rules actually help on real code (spoiler: same accuracy, fewer questions).

### 8. Optional: let an AI answer for you

If you have an Anthropic API key, qdebug can ask **Claude** (Anthropic's AI) to help. This is totally
optional.

- `--ai`: you still answer, but Claude takes a first look at the failure and explains the bug and a fix at
  the end.
- `--oracle hybrid`: Claude answers the questions it's confident about; you answer the rest.
- `--oracle claude`: Claude answers everything and you just watch.

Claude never sees the function's code when answering (only its description, inputs and outputs), because an
AI shown buggy code tends to say "looks intentional to me!"

---

## Everything qdebug can do

### While you're answering questions

| key | means |
|---|---|
| `y` | yes, that result is right (or: still on track) |
| `n` | no, that's wrong |
| `?` | not sure; qdebug works around it |
| `i` | the *inputs* already look wrong, so the bug happened earlier |
| `t` | I trust this function, stop asking about it |
| `s` | show me this function's code |
| `e` | show how this function behaved in tests that passed |
| `w` | why are you asking me this? |
| `u` | undo my last answer |
| `q` | stop and show what you have so far |
| `h` | help |

### Commands

| command | what it does |
|---|---|
| `qdebug debug` | the main thing: debug a failing test by answering questions |
| `qdebug rank` | skip the questions, just show the "most suspicious code" list |
| `qdebug init-agent` | copy Claude's instructions into your project so you can edit them (e.g. "all prices are in cents") |
| `qdebug variants` | build the practice projects with bugs planted in them |
| `qdebug eval` | run lots of debugging sessions on the practice bugs and measure them |
| `qdebug eval-groups` | test the "more than one bug" grouping |
| `qdebug eval-ai` | measure how good Claude is at answering the questions |
| `qdebug bugsinpy` | run qdebug on real bugs from real open-source projects |
| `qdebug study-report` | turn those real-bug results into tables with statistics |

### Useful options for `qdebug debug`

| option | what it does |
|---|---|
| `--project PATH` | which project to debug (default: the folder you're in) |
| `--test ID` | which failing test (otherwise it lets you pick) |
| `--suite PATH` | only run some test files (faster on big projects) |
| `--python PATH` | use the project's own Python / virtual environment |
| `--no-group` | don't group failing tests |
| `--oracle truth --fixed PATH` | answer automatically by comparing with a copy of the project that has no bug (for demos and testing) |
| `--policy baseline` | turn off the extra rules from section 7 |
| `--strategy topdown` / `divide` | use the classic 1980s question orders instead of "most useful question" |

---

## How we tested it

You can't test a debugger by having a person sit there answering thousands of questions. So we used a
**robot answerer** (we call it the *oracle*): we give it a copy of the program **with the bug fixed**, and
it answers each question by running the same call in the fixed version and checking whether the output
matches. It's a stand-in for a careful person who knows what the code should do.

To see what happens when people make mistakes, we also made the robot **lie on purpose** 10% or 20% of the
time.

### Round 1: bugs we planted ourselves

Two small practice projects (an online shop and a project planner) with **39 bugs** we put in on purpose:
off-by-one errors, swapped arguments, missing `return`s, shared lists that shouldn't be shared, and so on.
qdebug found the broken function in **all 39** and the exact line in 34. When Claude answered the questions
instead of the robot, it also found all 39 functions and 34 lines.

But that's kind of cheating: we built the extra rules (section 7) by looking at these same bugs. Of course it
does well on them. So:

### Round 2: real bugs from real projects (the real test)

[**BugsInPy**](https://github.com/soarsmu/BugsInPy) is a collection researchers use to test debugging tools.
It has real bugs from 17 well-known Python projects, each with the code before and after the developers
fixed it, and the test that shows the bug.

We split the projects into two piles:

- **Development set** (6 projects: PySnooper, cookiecutter, httpie, thefuck, tqdm, youtube-dl; 96 bugs):
  we'd used these before while building qdebug, so they don't really count.
- **Held-out set** (6 projects: black, fastapi, luigi, sanic, tornado, scrapy; 133 bugs): qdebug had
  **never** been run on these. We froze the code and ran them **once**.

And here's the honest-science part: we **wrote down the whole plan before running it**
([EVALUATION_PLAN.md](EVALUATION_PLAN.md)): what we'd measure, what we'd compare against, which statistical
tests we'd use, and what would count as "qdebug works." That way we couldn't move the goalposts after
seeing the results. Everything we had to change during the run (mostly fixing how old projects get
installed) is listed at the bottom of that file.

**What we compared against (the "baselines"):**

- **Ochiai top-1 / top-3 / top-5**: just read the suspicious-code ranking. Is the buggy function first? In
  the top 3? The top 5? (This is what most fault-localization tools give you.)
- **DStar**: a different ranking formula, same idea.
- **Crash location**: if the program crashed, the function where it crashed (that's what a stack trace
  tells you for free).
- **Classic algorithmic debugging**: ask questions top-down, or "divide and query", instead of qdebug's
  "most useful question" approach.

**"Success" was defined as:** qdebug finds the buggy function more often than Ochiai's #1 guess on the
held-out projects, with statistics saying it's not a fluke (p < 0.05), **and** the tuned rules don't make
things worse.

## The results

Out of 133 held-out bugs, 110 actually reproduced on our setup (the rest wouldn't install on a modern
machine, or the test didn't fail the way it should), and 105 gave a full debugging session.

| | finds the buggy function | finds the buggy line |
|---|---|---|
| **qdebug** (one answer) | **49 / 105 (47%)** | **37 / 105 (35%)** |
| Ochiai's #1 guess | 23 / 105 (22%) | 13 / 105 (12%) |
| Ochiai's top 3 | 41 / 105 (39%) | 29 / 105 (28%) |
| Ochiai's top 5 | 54 / 105 (51%) | 36 / 105 (34%) |
| where it crashed (only works on the 20 crashes) | 11 / 20 | – |

In normal words:

- **qdebug's single answer is right about twice as often as the ranking's #1 guess.** The statistics say
  that's very unlikely to be luck (p < 0.001). So yes, **the success criterion was met.**
- qdebug's one answer is about as good as reading the **top 3** of the ranking, and a little behind the
  top 5 (neither gap is statistically meaningful).
- It takes about **11 questions** on average.
- The **tuned rules** didn't find more bugs, but cut the questions from 13.4 to 10.7 on average.
- With the robot **lying 10% of the time**, qdebug still found 39% of the buggy functions; at **20% lies**,
  35%. Still better than the ranking's #1 guess. Finding the exact *line* suffers more (24% and 16%).
- **Big programs don't scare it.** On tests that made 100+ function calls, qdebug still found 47%, while
  the ranking's #1 guess dropped to 13%. That's where asking questions helps most: in a big run, lots of
  functions look equally suspicious, and a couple of answers tell them apart.
- On the development projects (the ones we'd seen before), qdebug found 78% vs 59% for Ochiai #1.

**Where it struggles:** about half the held-out bugs were still missed. It did worst on tornado (3 of 14)
and fastapi (4 of 15), which do a lot of their work in asynchronous code (code that pauses and resumes,
which qdebug doesn't follow well). Some bugs also don't live on a line that "runs" (like a wrong default
value), so qdebug can only point at the function.

**Caveats, honestly:**

- The robot answerer never gets confused the way people do. The lying robot is only a rough stand-in. A
  real user study is planned ([USER_STUDY.md](USER_STUDY.md)) but not done.
- Old projects needed old library versions; a few had to be swapped for newer ones that still install.
- The study found one real bug in qdebug itself (it choked on a weird kind of class that the `pydantic`
  library creates). We fixed it and re-ran every affected bug.

All the numbers, per project and per research question: [results/bugsinpy-2026/study.md](../results/bugsinpy-2026/study.md).

---

## Tiny glossary

- **Test**: a small program that runs your code and checks the answer.
- **pytest**: the most common tool for running Python tests. qdebug works with projects that use it.
- **Function call**: one time a function runs, with specific inputs and a specific output.
- **Oracle**: whoever answers qdebug's questions: you, Claude, or the robot that compares with the fixed code.
- **SBFL / Ochiai / DStar**: ways of ranking code by how much more the failing tests run it than the passing
  tests do.
- **Algorithmic debugging**: the 1983 idea of finding a bug by asking whether each function call's result
  was right.
- **Held-out set**: data you hide from yourself while building something, so you can test it fairly later.
- **p-value**: roughly, "how likely is a difference this big if there were really no difference?" Small
  (under 0.05) means probably not luck.
- **McNemar's test**: a way to compare two methods on the same bugs by looking only at the bugs where one
  succeeded and the other didn't (here: 28 bugs only qdebug found, 2 only Ochiai #1 found).
