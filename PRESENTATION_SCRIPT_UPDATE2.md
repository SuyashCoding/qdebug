# qdebug on real code: presentation script

For `qdebug_changes.pptx`. About 13–15 minutes for 9 slides, plus an optional live demo on slide 8.
Plain text is what you **say**. Lines starting with 👉 are what you **do**.
You don't need to memorize the wording. Learn the **one-liner** for each slide, and talk around it.

## The three things to remember

1. **The pitch:** *qdebug used to work only on the toy shop we built for it. Now it runs on real Python projects, and we tested it on 80 real bugs.*
2. **The honest result:** *It names the buggy function in 50 of 80 bugs, and the exact line in 31. That's about as good as reading SBFL's top three, not better. It fails on big tests.*
3. **The demo story:** *youtube-dl's `urljoin`, called 20 times. Only the last call is wrong. The old version checks the first four calls and gives up; the new one checks the last call first and finds line 1871.*

| Slide | Time | One-liner |
|---|---|---|
| 1. Title | 1 min | "From the toy project to real code." |
| 2. Enlighten | 1.5 min | "Rank, slice, ask about values, re-rank." |
| 3. qdebug vs Enlighten | 2 min | "We add information gain, noise and zoom; we lack data flow." |
| 4. What changed | 1.5 min | "Real projects, real objects, a fair oracle, the right call." |
| 5. Seeing inside objects | 1.5 min | "Before, every account looked the same." |
| 6. What it is tested on | 1.5 min | "5 planted bugs, then 96 real ones." |
| 7. Results | 2 min | "On par with SBFL's top 3; zero on big tests." |
| 8. Demo | 2 min (+3 live) | "Old checks the first calls; new checks the last one." |
| 9. Limits and next steps | 1 min | "Scale is the problem; data flow is the fix." |

---

## Before you present (do this once, ~5 minutes)

👉 Open PowerShell in the project folder and make the font big (Ctrl + `+`).

```powershell
cd C:\Users\suy19\Desktop\Projects\QDebug
```

👉 If `demo\work` doesn't exist yet, build it (about 1 minute, downloads youtube-dl):

```powershell
python demo\setup_demo.py
```

👉 Set `HOME`, so youtube-dl's unrelated `test_expand_path` doesn't fail in PowerShell. Without it the output still works, but says "3 failing" and shows a different Ochiai number than the slide.

```powershell
$env:HOME = $env:USERPROFILE
```

👉 **Do one dry run of the live demo** (see [Live demo guide](#live-demo-guide-slide-8)). Each run takes 10–20 seconds, so you know how long the pauses are.

👉 Open the slides in PowerPoint, with the terminal ready behind them for Alt + Tab.

---

## Slide 1: Title (1 min)

**One-liner:** *"From the toy project to real code."*

> Last time I showed qdebug on a small online-shop library we wrote ourselves, with bugs we planted. It worked well there. The obvious question was: does it work on **real code**?
>
> This update answers that. Three parts: **what we had to change** to run on real Python projects, **how qdebug compares to Enlighten**, the paper we started from, and **how it does on 80 real bugs** from open-source projects.
>
> 👉 *point at the screenshot:* This is a real question qdebug asks on a real bug in **youtube-dl**, the video downloader. It shows one call: `urljoin`, with `base = None` and `path = 'rtmp://foo.de'`, which returned `None`. You don't read the code. You only judge: is that output right? Here it isn't: an `rtmp://` address is already a complete URL, so it should come back unchanged. So you answer **n**.

---

## Slide 2: Starting point: Enlighten (1.5 min)

**One-liner:** *"Rank, slice, ask about values, re-rank."*

> Our starting point is **Enlighten**, from ICSE 2018, by Li, Zhu, d'Amorim and Orso at Georgia Tech. It's interactive fault localization in four steps.
>
> **1. Rank:** classic spectrum-based fault localization. Every statement gets an Ochiai score: code that runs mostly in failing tests is suspicious.
>
> **2. Slice:** it builds a full **dynamic dependence graph** of the failing test, which value was computed from which, using Java PathFinder.
>
> **3. Ask:** 👉 *point at the orange circle.* It shows the developer the inputs and outputs of the most suspicious method call, and the developer marks **individual values** right or wrong.
>
> **4. Re-rank:** each answer becomes a weighted "virtual test" that updates the scores, and it repeats.
>
> 👉 *point at the three boxes:* They tested it on **1,807 Java faults**, with a simulated developer: at most 10 questions for 85% of the real faults and 96% of the mutants. In a user study with **24 people**, debugging took **39 to 59% less time**.

---

## Slide 3: How qdebug differs from Enlighten (2 min)

**One-liner:** *"We add information gain, noise and zoom; we lack data flow."*

> Same idea, different choices. Row by row:
>
> - **The question.** Enlighten asks about single values. We ask about a whole call: is its output right? You can also say "don't know", or "the inputs were already wrong".
> - **Which call to ask.** Enlighten takes the most suspicious one. We take the one whose answer is expected to **tell us the most**, information gain over a probability for every call.
> - **Wrong answers.** Enlighten is robust in practice. We model mistakes explicitly with an error rate, so one wrong answer never throws anything away for good.
> - **Inside the method.** Enlighten stops at the method; the developer says "it's here". We **zoom** to the line, with a binary search over the variables.
> - **Tracing.** Enlighten needs the full dependence graph, which only works for the part of Java that Java PathFinder supports. We record a call tree, and values only for suspicious functions.
> - **Evaluation.** They have 1,807 faults and a user study. We have 5 seeded and 96 real bugs, and **no user study yet**.
>
> 👉 *point at the bottom line:* In short: we **add** information gain, a noise model, line-level zoom and cheap tracing. We **lack** Enlighten's value-level answers and its data flow. Keep that last part in mind; it comes back in the results.

---

## Slide 4: What changed since the prototype (1.5 min)

**One-liner:** *"Real projects, real objects, a fair oracle, the right call."*

> Four changes.
>
> **1. It runs on real projects.** It uses the project's own Python environment, back to Python 3.8 and pytest 3.2, loads the project's pytest plugins, reads files in any encoding, and puts a limit on huge call trees. The old version crashed or gave up on most of that.
>
> **2. It sees inside objects.** I'll show this on the next slide.
>
> **3. The automatic oracle is fair.** In experiments, a simulated developer answers by comparing with the fixed version of the program. Random numbers, temporary file names and folder paths used to make every comparison differ. Now they're seeded or masked. And if a test runs differently the second time, we report that instead of trusting it.
>
> **4.** 👉 *point at the orange 4:* **It zooms into the right call.** When a function is called many times, it now checks the **latest** call first, because a test stops at its first failing assertion. You'll see this in the demo.
>
> Changes 3 and 4 came out of the real-bug evaluation itself.

---

## Slide 5: Seeing inside objects (1.5 min)

**One-liner:** *"Before, every account looked the same."*

> Same planted bug, same first question about the same call: `transfer` moves 100,000 cents from alice to bob.
>
> 👉 *point left:* **Before.** Both accounts print as "Account object at some address". Before and after the call, that text is identical, so the tool reports **"mutated arguments: none"**. Nobody can see the bug, not you and not the automatic oracle. The old version ended up blaming the wrong function.
>
> 👉 *point right:* **After.** Now you see the fields. Alice had 200,000. Transfers above 50,000 cost a 1% fee on the excess, so 500, and she should end with 99,500. She ends with **100,000**. 👉 *point at the orange line:* The fee is written into her history, but never subtracted.
>
> That's a two-second "no" for a human, and it leads straight to line 25 of `withdraw`.

---

## Slide 6: What it is tested on (1.5 min)

**One-liner:** *"5 planted bugs, then 96 real ones."*

> Two test beds.
>
> 👉 *point left:* The **seeded bugs** from last time: the online shop, five planted one-line bugs, 420 simulated sessions. Those results are **identical** before and after this update. That's our check that nothing broke.
>
> 👉 *point right:* The new one is **BugsInPy**, a benchmark of real bugs from real Python projects. Each bug comes with a buggy commit, a fixed commit and the test that exposes it. We ran **all 96 bugs** of six projects, including youtube-dl, thefuck and tqdm. For each bug we build a buggy and a fixed copy and a Python 3.8 environment, and the simulated developer answers by comparing each call with the fixed copy. The baseline is classic SBFL on the same tests.
>
> 👉 *point at the funnel:* 87 of the 96 fail on the buggy version and pass on the fixed one on my machine. 80 lead to a debugging session. In the other 7, the test never reaches the project's code (it imports a function the fix adds), or the test depends on timing.

---

## Slide 7: Results: on par with SBFL's top 3 (2 min)

**One-liner:** *"On par with SBFL's top 3; zero on big tests."*

> 👉 *point at the orange bars:* Out of 80 real bugs, qdebug names the buggy function in **50**. SBFL's single top entry is right in 46. It finds the exact line in **31**, in a region of about one and a half lines. That's about what you get by reading SBFL's top **three** lines.
>
> 👉 *point at "2 + 4":* When it works, it's cheap: a median of 2 questions about calls and 4 about lines.
>
> So, honestly: on real bugs it's **comparable to SBFL, not a replacement**. It wins on 15 bugs where SBFL doesn't rank the buggy function first, and loses 11 where SBFL does.
>
> 👉 *point at the red "0 / 12":* And the clear weakness: when the failing test makes **100 or more calls**, it found **none** of the 12 bugs. Most ran out of the 30-question budget. With hundreds of calls, asking about calls one at a time is too slow. That's exactly what Enlighten's data flow solves: only ask about calls whose values actually reach the wrong output.

---

## Slide 8: Demo: a real youtube-dl bug (2 min, or 3–4 min live)

**One-liner:** *"Old checks the first calls; new checks the last one."*

👉 *Optional:* switch to the terminal and follow the [Live demo guide](#live-demo-guide-slide-8). Then come back to this slide as the recap. If you don't demo live, just present the slide.

> This is bug 13 from youtube-dl. `urljoin` should leave any full URL alone, like `rtmp://`, but its pattern only accepted `http` and `https`.
>
> The test calls `urljoin` **20 times**, and only the **last** call is wrong, because a test stops at its first failing assertion.
>
> 👉 *point left:* Both versions agree the bug is in `urljoin`. The **old** version then zooms into calls 0, 1, 2 and 3. All four are correct, it runs out of rounds, and it reports **no line**.
>
> 👉 *point right:* The **new** version first asks about the **latest** call, number 19, `urljoin(None, 'rtmp://foo.de')` returning `None`. That's wrong, so it zooms in. Four state checks later it points at **line 1871**, which is exactly the line the real fix changed.
>
> Everything here is real output. The commands are in `demo/DEMO.md`, so anyone can rerun it.

---

## Slide 9: Limits and next steps (1 min)

**One-liner:** *"Scale is the problem; data flow is the fix."*

> To close, the limits.
>
> 👉 *point left:* The big one is **scale**: none of the 12 bugs with large failing tests. Code that installs its own tracer, like the debugging tool PySnooper, and async or threaded code don't work. And our developer is **simulated**: no user study yet.
>
> 👉 *point right:* Next steps follow from that. First, borrow Enlighten's best idea: use **data flow** to ask only about calls that can affect the wrong output. Second, look at the 14 cases where it blames the wrong function. Third, faster tracing, and a small study with real people.
>
> 👉 *point at the bottom line:* The code, the full results and the demo instructions are all in the repository.
>
> Thanks, happy to take questions.

---

## Live demo guide (slide 8)

Run everything from the project folder in PowerShell, with `$env:HOME` set (see [Before you present](#before-you-present-do-this-once-5-minutes)).

### Option A: the comparison (about 1 minute, no typing of answers)

The simulated developer answers, so both versions get exactly the same answers.

👉 Run the **new** version:

```powershell
python -m qdebug debug --project demo\work\yt13\buggy --test test/test_utils.py::TestUtil::test_urljoin --oracle truth --fixed demo\work\yt13\fixed --save-dir demo\work
```

**You'll see** (scroll to it):

```text
Buggy call found:
  function : youtube_dl/utils.py::urljoin  (line 1866)
  call path: TestUtil.test_urljoin/urljoin#19
...
    line 1871  ochiai 0.707  if re.match(r'^(?:https?:)?//', path):
Questions: 1 function-level, 4 line-level
```

> One question about a call, four about lines, and it's on line 1871.

👉 Run the **old** version. It has to run from its own folder:

```powershell
cd demo\qdebug_before
```

```powershell
python -W ignore -m qdebug debug --project ..\work\yt13\buggy --test test/test_utils.py::TestUtil::test_urljoin --oracle truth --fixed ..\work\yt13\fixed --save-dir ..\work
```

```powershell
cd ..\..
```

**You'll see** four red-flag lines at the top:

```text
  zoom refuted TestUtil.test_urljoin/urljoin#0 (refuted_output); resuming the search
  ...
  zoom refuted TestUtil.test_urljoin/urljoin#3 (refuted_output); resuming the search
```

> Same function, but it looked at calls 0 to 3, which were all fine, and stopped without a line.

### Option B: you are the developer (about 3 minutes, new version only)

👉 Run without `--oracle`, so qdebug asks you:

```powershell
python -m qdebug debug --project demo\work\yt13\buggy --test test/test_utils.py::TestUtil::test_urljoin --save-dir demo\work
```

The answers are always **n, n, n, y, y**.

| You'll see | Type | Say |
|---|---|---|
| Question 1: `urljoin`, `base = None`, `path = 'rtmp://foo.de'`, `returned: None` | `n` | "`rtmp://foo.de` is already a full URL; it should come back unchanged, not `None`." |
| Line question 1: state at RETURN, `returning: None` | `n` | "It still ends wrong; this confirms the call." |
| Line question 2: state before line 1873 | `n` | "We shouldn't even get here. A full URL should have returned on line 1872." |
| Line question 3: state before line 1869 | `y` | "At the start, the inputs are just the inputs. Fine." |
| Line question 4: state before line 1871 | `y` | "Still fine right before the check, so the check on 1871 is what goes wrong." |

**You'll see** the same result as option A: line 1871, 1 function-level and 4 line-level questions.

👉 *(Optional, during question 1)* type `w`: it shows why this question was chosen and the current top guesses. `tree` shows all 20 calls.

### If something goes wrong

| Problem | Fix |
|---|---|
| You typed the wrong answer | Type `u` (undo); it asks again |
| It says "3 failing" and `ochiai 0.577` | `HOME` isn't set. Harmless; the result is the same |
| `demo\work` is missing | Run `python demo\setup_demo.py` (needs internet, about 1 minute) |
| Old version: `No module named qdebug` or it runs the new one | You're not in `demo\qdebug_before`; `cd` there first |
| Anything else, or you're out of time | Type `q`, go back to slide 8 and present it as a recording |

---

## Likely questions (short answers)

**"So is qdebug better than SBFL?"**
Not on real bugs, not yet. It names the right function slightly more often than SBFL's top entry (50 vs 46), and finds the line about as often as reading SBFL's top three. It's a different way to get there, through questions, and it's much cheaper when it works: about 6 questions.

**"Isn't comparing to SBFL's top 3 unfair?"**
It's the fair comparison for lines. qdebug reports one region of about 1.6 lines; with SBFL a developer reads down the list, and three lines is roughly the same reading effort.

**"Why does it fail on big tests?"**
It asks about calls one at a time, with a budget of 30 questions. With hundreds or thousands of calls, that's not enough. Enlighten's data flow would let it skip calls that can't affect the wrong value.

**"Who answers the questions in the real-bug experiment?"**
A simulated developer: it compares each call with the same call in the fixed version. In real use, you answer. If you have a known-good version, for example the last working commit, qdebug can answer itself the same way.

**"Didn't you tune it on the same benchmark you report?"**
Partly, yes, and that's a fair point. Two fixes, the fair oracle and the latest-call-first zoom, came from looking at BugsInPy failures. They raised the score from 47 to 50 functions and from 24 to 31 lines. They're general fixes, not special cases, and the seeded-bug results didn't change, but a fresh benchmark would be the cleaner test.

**"Why Python 3.8?"**
BugsInPy's bugs are from 2013–2020 and need Python 3.6 to 3.8 with old dependency versions. 3.8 is the oldest Python we can install automatically.

**"Why only 80 of 96 bugs?"**
9 don't reproduce on my machine (mostly thefuck tests that pass on the buggy version here). 6 tests import a function the fix adds, so on the buggy version they fail before running any project code; no dynamic technique can localize those. 1 depends on timing.

**"Did you reimplement Enlighten?"**
No. The tool link in the paper no longer works, and it's for Java. We compare designs and reported numbers, not head-to-head on the same bugs. A Python Enlighten-style baseline would be a good next step.

**"Can I use it on my own project?"**
Yes, any Python project with pytest and a failing test: `python -m qdebug debug --project PATH --python PATH\.venv`. The README has the details.

**"What's the 'line-level zoom'?"**
Once a call is blamed, qdebug takes a snapshot of the local variables at every line of that call, and binary-searches for the first line where they go wrong.

---

## Glossary (plain words)

| Term | Say this |
|---|---|
| Enlighten | The 2018 paper we started from: SBFL plus developer feedback, for Java |
| SBFL / Ochiai | "Code that runs mostly in failing tests is suspicious": a score per function or line |
| Top-1 / top-3 | Whether the buggy function or line is first, or among the first three, in SBFL's ranking |
| Oracle | Whoever answers the questions (you, or a simulation using the fixed version) |
| BugsInPy | A benchmark of real bugs from real Python projects, each with a buggy and a fixed commit |
| Information gain | How much an answer is expected to reduce uncertainty |
| Error rate ε | How often we assume an answer might be wrong |
| Data flow / dependence | Which values were computed from which (Enlighten has it; qdebug doesn't yet) |
| Zoom | Looking inside the buggy call, line by line |
| Seeded bug | A bug we planted ourselves, so we know exactly where it is |
