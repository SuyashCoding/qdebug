# qdebug: presentation script

About 10 minutes for 5 slides and a live demo. Plain text is what you **say**. Lines starting with 👉 are what you **do**.
You don't need to memorize the wording. Learn the **one-liner** for each slide, and talk around it.

## The three things to remember

1. **The pitch:** *A test fails. Instead of reading code, you answer yes/no questions about what function calls did, and qdebug finds the buggy line.*
2. **The four steps:** **Rank → Record → Ask → Zoom.**
3. **The demo story:** *10 pens, wrong price, four answers, line 24 (`>` should be `>=`).*

| Slide | Time | One-liner |
|---|---|---|
| 1. Title | 1 min | "Answer questions, get the buggy line." |
| 2. What qdebug does | 2 min | "Rank, Record, Ask, Zoom." |
| 3. Goal and research questions | 2 min | "Fewer, easier questions, and still right when you make mistakes." |
| 4. Demo | 3–4 min | "Four answers to line 24." (live in the terminal) |
| 5. Progress and results | 2 min | "It works; the classic method breaks with mistakes; ours holds, but isn't the winner yet." |

---

## Before you present (do this once, ~5 minutes)

👉 Open a terminal (Windows Terminal or PowerShell) in the project folder, and make the font big (Ctrl + `+`).

```bash
cd C:\Users\suy19\Desktop\Projects\QDebug
```

👉 Make sure the five buggy copies exist. This prints a table with 5 rows (bug_01 … bug_05).

```bash
python make_variants.py
```

👉 **Do one full dry run of the demo** (see the [Demo guide](#live-demo-guide-slide-4)) so nothing surprises you.

👉 Have the slides open in PowerPoint and the terminal ready, so you can switch with Alt + Tab.

---

## Slide 1: Title (1 min)

**One-liner:** *"Answer questions, get the buggy line."*

> Hi, I'm presenting **qdebug**, a research prototype for our testing and debugging course.
>
> Here's the problem. A test fails, and all you get is this. 👉 *point at the red text, top right:* "expected 1791, got 1890".
> It tells you *that* something is wrong, but not *where*.
>
> qdebug's idea: instead of you reading through the code, the tool asks you **simple yes/no questions** about what individual function calls did, like "given these inputs, is this output right?".
>
> 👉 *point at the bottom-right box:* In this real run it took **two questions about function calls and two quick checks**, and it pointed at the exact line: `if quantity > 10`.
>
> Let me show you how.

---

## Slide 2: What qdebug does (2 min)

**One-liner:** *"Rank, Record, Ask, Zoom."*

> It works in four steps.
>
> **1. Rank.** We run the whole test suite and score each function. Code that mostly runs in *failing* tests is more suspicious. That's a classic technique, but it only gives us a starting guess.
>
> **2. Record.** We re-run the failing test and record it as a **tree of function calls**: who called whom, with which inputs and outputs. To keep it cheap, we only record values for the most suspicious functions, and record more only when we need them.
>
> **3. Ask.** 👉 *point at the orange circle.* This is the heart of it. We pick the call whose answer will **tell us the most**, like the best question in 20 Questions. After every answer we update a probability for each call being the buggy one.
>
> **4. Zoom.** Once we've found the buggy *call*, we look inside it, line by line, and binary-search for the first line where the variables go wrong.
>
> 👉 *point at the screenshot:* This is what a question looks like. One function call: `line_total`, for 10 pens at $1.99. It returned 1890 cents. Is that right? You don't need to read any code to answer, just know what the function is *supposed* to do. 10 pens with a 10% bulk discount should be $17.91, so: **no**.
>
> 👉 *point at the grey box:* And because people make mistakes, the tool treats every answer as evidence, not as absolute truth.

---

## Slide 3: Goal and research questions (2 min)

**One-liner:** *"Fewer, easier questions, and still right when you make mistakes."*

> Our goal: help a developer find a bug with **as few, easy-to-answer questions as possible**, and stay right even when **some answers are wrong**.
>
> That gives us four research questions:
>
> - **RQ1, Efficiency.** Does choosing questions by "most informative first" need fewer questions than the classic strategies?
> - **RQ2, Robustness.** Classic algorithmic debugging throws away whole branches based on one answer. If that answer was a mistake, the bug is gone for good. Does our probability-based approach survive mistakes better?
> - **RQ3, Cost.** Recording everything is slow. Can we record only the suspicious parts and still find the bug?
> - **RQ4, Precision.** Can we go all the way to the exact *line*, even in a long, 90-line function?
>
> 👉 *point at "Test bed":* To measure this, we built a small online-shop library: cart, coupons, tax, shipping and invoices, with 35 tests. Then we made 5 copies and **planted one bug in each**. Because we planted them, we know the right answer, so we can score the tool.

---

## Slide 4: Demo (3–4 min, live)

**One-liner:** *"Four answers to line 24."*

> Let me show it live, on bug 1.

👉 **Switch to the terminal and follow the [Live demo guide](#live-demo-guide-slide-4) below.**

👉 When you're done, switch back to this slide and use it as the recap:

> So: the test failed, I answered two questions about function calls (both "no"), two quick checks inside the function, and it pointed at line 24.
>
> 👉 *point at the tree:* The tree shows its belief: 72.7% on `quantity_discount_rate`. The circles are calls where it didn't even record values, because they weren't suspicious.
>
> 👉 *point at the code box:* The bug is a classic off-by-one. `>` should be `>=`, so exactly 10 pens only got 5% off.

**If the live demo fails:** don't fight it. Say "here's the same run, recorded" and walk through this slide instead. It shows exactly what the demo would have shown.

---

## Slide 5: Progress and early results (2 min)

**One-liner:** *"It works; the classic method breaks with mistakes; ours holds, but isn't the winner yet."*

> Where we are. 👉 *point at "Done":* The tool works end to end, the test bed is built, there are 96 automated tests, and we ran 420 simulated debugging sessions.
>
> For the experiments, a **simulated developer** answers the questions by comparing against the correct version of the shop. To test mistakes, we made it give the **wrong** answer 10% or 20% of the time.
>
> 👉 *point at the left group of bars:* With correct answers, every strategy finds all 5 bugs and the exact line.
>
> 👉 *point at the red bars:* With mistakes, the classic top-down strategy **collapses**: 52%, then 28%. One wrong answer sends it down the wrong path.
>
> 👉 *point at the orange bars:* Ours holds up much better: 78% and 54%, and 62% if we let it ask more questions.
>
> But to be honest: 👉 *point at blue* divide-and-query, the other classic strategy, is just as robust here. So RQ2 isn't answered in our favour yet. That's a real finding, and it shapes what we do next.
>
> 👉 *point at "Next":* Next: try it on **real-world bugs**, run a **small study with real developers**, and plug in an **LLM to answer the questions**. The LLM would see what each function is supposed to do, but deliberately not its code.
>
> Thanks, happy to take questions.

---

## Live demo guide (slide 4)

**Total: about 3 minutes.** The answers are always the same: **n, n, n, n**.

### Step 1: Show the failing test (30 s)

👉 Go into the buggy copy and run the one failing test:

```bash
cd variants/bug_01
```

```bash
python -m pytest -q tests/test_invoice.py::test_bulk_invoice_qty_ten
```

**You'll see:** red `F`, `assert 1890 == 1791`, `1 failed`.

> The test buys 10 pens. It expects $17.91 and gets $18.90. pytest tells us it's wrong, not why.

👉 Go back to the project folder:

```bash
cd ../..
```

### Step 2: Start qdebug (20 s)

```bash
python -m qdebug debug --project variants/bug_01 --oracle human --save-dir sessions
```

**You'll see:** `Debugging tests/test_invoice.py::test_bulk_invoice_qty_ten ...`, then three lines like `↑ escalating monitoring tier 5% -> 10%`.

> It first records values for only the top 5% most suspicious functions, and widens to 25% when it needs more. That's the "Record" step, kept cheap.

### Step 3: Question 1, `line_total` (40 s)

**You'll see:** `── Question 1`, `line_total`, input `item = LineItem(sku='PEN-001', quantity=10, unit_price=199)`, `returned: 1890`.

👉 *(Optional, good for the audience)* Type `w` and press Enter.

> "w" means "why this question?". It shows that this is the most informative question right now, and its current top guesses.

👉 Type **`n`** and press Enter.

> 10 pens at $1.99 is $19.90. Minus 10% bulk discount is $17.91, so 1791, not 1890. **No.**

### Step 4: Question 2, `quantity_discount_rate` (40 s)

**You'll see:** `── Question 2`, `quantity_discount_rate`, `quantity = 10`, `returned: 0.05`.

👉 Type `tree` and press Enter.

> This is the tool's picture of the run. ✗ means "answered wrong", ○ means "values not recorded", and the percentages are how likely it thinks the bug is in each call.

👉 Type **`n`** and press Enter.

> The docstring says 10% from 10 units. 10 units should give 0.10, not 0.05. **No.**
> That function calls nothing else, so the bug must be inside it. Now it zooms in.

### Step 5: Line question 1, the end state (15 s)

**You'll see:** `── Line question 1`, `State at RETURN:`, `quantity = 10`, `returning: 0.05`.

👉 Type **`n`** and press Enter.

> It double-checks that the function really ends in a wrong state. Yes, that's still wrong.

### Step 6: Line question 2, inside the function (30 s)

**You'll see:** `State just BEFORE line 26 runs`, with the code shown and an arrow `->` at line 26 (`if quantity >= 5:`). `quantity = 10`.

👉 Type **`n`** and press Enter.

> With 10 pens we should already have returned 10% on line 25. Arriving at line 26 means the check on line 24 let us through. That's wrong.

### Step 7: Read the result (30 s)

**You'll see** a report. 👉 Scroll to these lines:

```
Buggy call found:
  function : shop/pricing.py::quantity_discount_rate  (line 22)
...
  region (1 line(s)) in shop/pricing.py:
    line   24  ochiai 0.378  if quantity > 10:
...
Questions: 2 function-level, 2 line-level
```

> Four answers, and it points at line 24: `>` should be `>=`.

👉 *(Optional)* Show the code in your editor:

```bash
code variants/bug_01/shop/pricing.py
```

### If something goes wrong during the demo

| Problem | Fix |
|---|---|
| You typed the wrong answer | Type `u` (undo); it asks that question again |
| Symbols show as boxes or `?` | Quit with `q`, re-run the command with `--ascii` added at the end |
| You're lost or out of time | Type `q`: it stops and prints the report so far. Then go back to slide 4 |
| Typing live feels risky | Let the tool answer itself (no typing needed): `python -m qdebug debug --project variants/bug_01 --oracle truth --fixed sample_project` |

### Bonus, if you have an extra minute: the hard bug

Bug 4 hides in the middle of a 90-line function (tax charged before the discount). Let the simulated developer answer:

```bash
python -m qdebug debug --project variants/bug_04 --oracle truth --fixed sample_project --save-dir sessions
```

> Classic ranking puts this line 49th. qdebug finds it exactly: line 114, `tax = compute_tax(taxable_subtotal, address)`.

---

## Likely questions (short answers)

**"How does the tool know the right answer?"**
It doesn't; *you* do. You're the "oracle". In our experiments a simulated developer answers by comparing with the correct version of the code.

**"Why not just use a debugger?"**
With a debugger *you* decide where to look and step through code. With qdebug the tool decides what to ask, and you only judge behaviour: "is this output right?".

**"What happens if I answer wrong?"**
One mistake doesn't eliminate anything, because the tool keeps probabilities. It also double-checks inside the function during zoom, and you can always undo with `u`.

**"What does 'most informative question' mean?"**
The question whose answer is expected to cut the remaining uncertainty the most, like asking "is it an animal?" first in 20 Questions.

**"Why a toy project?"**
Because we planted the bugs, we know exactly where they are, so we can measure the tool. Real-world bugs are the next step.

**"Is your strategy better than the classic ones?"**
Much better than top-down when answers can be wrong. About equal to divide-and-query so far. Ours is better only at the highest mistake rate, and only when it's allowed to ask more questions.

**"Isn't tracing slow?"**
Yes, the traced test runs roughly 15–30 times slower, but that's milliseconds here. That's why we record values only for suspicious functions.

**"Where would an LLM fit?"**
It would answer the questions instead of a human. It would see each function's description and examples, but deliberately not its code, so it can't talk itself into believing the buggy code is correct.

---

## Glossary (plain words)

| Term | Say this |
|---|---|
| Oracle | Whoever answers the questions (you, a simulation, or later an LLM) |
| Call tree | Which function called which, during the failing test |
| SBFL / Ochiai | "Code that runs mostly in failing tests is suspicious": a score per function or line |
| Belief / posterior % | How likely the tool thinks the bug is in each call, right now |
| Information gain | How much an answer is expected to reduce uncertainty |
| Hard pruning | Throwing away a whole branch after one answer (classic approach) |
| Soft update | Shifting probabilities instead of throwing things away (our approach) |
| Zoom | Looking inside the buggy function, line by line |
| Monitoring tier | How many functions we record values for (5% → 100%) |
