const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell, WidthType,
        BorderStyle } = require("docx");

const FONT = "Times New Roman";
const out = process.argv[2];

// A paragraph from segments: "plain", {t, i}, {t, b}, {t, sub}, {t, sup}
function runs(segs) {
  return (Array.isArray(segs) ? segs : [segs]).map((s) =>
    typeof s === "string"
      ? new TextRun({ text: s, font: FONT, size: 22 })
      : new TextRun({ text: s.t, font: FONT, size: 22, italics: !!s.i, bold: !!s.b,
                      subScript: !!s.sub, superScript: !!s.sup, color: s.color }));
}
const p = (segs, opts = {}) => new Paragraph({
  children: runs(segs), alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 100, line: 252 }, ...opts,
});
const h1 = (text) => new Paragraph({ heading: "Heading1", children: [new TextRun(text)] });
const h2 = (text) => new Paragraph({ heading: "Heading2", children: [new TextRun(text)] });
const todo = (text) => p([{ t: `[${text}]`, i: true, color: "7F7F7F" }]);
const ref = (n, text) => new Paragraph({
  children: runs(`[${n}] ${text}`), indent: { left: 360, hanging: 360 },
  spacing: { after: 40, line: 240 },
});
// A three-line table: rules above and below the header and at the bottom only
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const RULE = { style: BorderStyle.SINGLE, size: 6, color: "000000" };
function table(rows, widths) {
  const cell = (text, i, r) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    margins: { top: 15, bottom: 15, left: 60, right: 60 },
    borders: { left: NONE, right: NONE,
               top: r <= 1 ? RULE : NONE, bottom: r === 0 || r === rows.length - 1 ? RULE : NONE },
    children: [new Paragraph({
      alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, spacing: { after: 0, line: 228 },
      children: [new TextRun({ text, font: FONT, size: 19, bold: r === 0 || rows[r][0] === "qdebug" })],
    })],
  });
  return new Table({
    width: { size: widths.reduce((a, b) => a + b), type: WidthType.DXA },
    columnWidths: widths, alignment: AlignmentType.CENTER,
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: rows.map((row, r) => new TableRow({ children: row.map((t, i) => cell(t, i, r)) })),
  });
}
const caption = (segs) => new Paragraph({
  children: runs(segs), alignment: AlignmentType.CENTER, spacing: { before: 60, after: 100, line: 240 },
});
const e = (t) => ({ t, i: true });
const sub = (t) => ({ t, i: true, sub: true });

const body = [
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "qdebug: Locating Faults in Python Programs with Yes/No Questions",
                             font: FONT, size: 32, bold: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: "Suyash Patel", font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED, indent: { left: 540, right: 540 },
    spacing: { after: 200, line: 252 },
    children: runs([{ t: "Abstract. ", b: true },
      "Spectrum-based fault localization ranks code by how often failing tests run it, but leaves the " +
      "developer to decide which entry is the bug. Algorithmic debugging asks about individual function calls " +
      "instead, but on large programs it asks many questions. qdebug, a debugger for Python projects tested " +
      "with pytest, combines the two. The spectrum becomes a prior over which call holds the bug, each yes/no " +
      "question is chosen for the information it is expected to give, and answers are treated as noisy " +
      "evidence. Once a function is blamed, qdebug narrows the fault to a line. On 105 real bugs from six " +
      "BugsInPy projects held out from development, its single answer named the buggy function in 47% of " +
      "cases, against 22% for the top of the Ochiai ranking."]),
  }),

  h1("1  Introduction"),
  p("When a test fails, the error usually shows where the program noticed the problem, not where it started. " +
    "Spectrum-based fault localization (SBFL) helps by ranking functions or lines by how much more often " +
    "failing tests run them than passing tests do [1, 2]. The result is a list, though, and Parnin and Orso " +
    "[3] found that developers do not read such lists from top to bottom, and that a good rank on its own did " +
    "little to speed them up."),
  p("Algorithmic debugging [4] records the failing run as a tree of calls and asks whether each call returned " +
    "the right result. A call that is wrong while every call it made is right must contain the bug, so the " +
    "developer only judges values and never reads code. The cost is the number of questions, and one wrong " +
    "answer sends the search into the wrong part of the tree. qdebug uses the SBFL ranking as a prior over " +
    "which call contains the bug, asks the question expected to be most informative, and assumes any answer " +
    "might be wrong."),

  h1("2  Background and Related Work"),
  p(["SBFL counts, for each element, the failing tests ", e("e"), sub("f"), " and passing tests ", e("e"),
     sub("p"), " that execute it. Ochiai [1] scores it as ", e("e"), sub("f"), " / √(", e("F"), "(", e("e"),
     sub("f"), " + ", e("e"), sub("p"), ")), where ", e("F"), " is the number of failing tests, and DStar [2] " +
     "uses ", e("e"), sub("f"), { t: "2", sup: true }, " / (", e("e"), sub("p"), " + ", e("F"), " − ", e("e"),
     sub("f"), "). Both assume a single fault. On BugsInPy, Rezaalipour and Furia [6] found that for " +
     "crashes, the innermost project frame of the stack trace is hard to beat. Algorithmic debugging began " +
     "with Shapiro [4], and later strategies such as top-down and divide-and-query pick questions in " +
     "different ways [7]. The closest work to ours is Enlighten [8], which asks Java developers about method " +
     "calls chosen with help from SBFL. qdebug differs in choosing questions by expected information gain, " +
     "modelling wrong answers, and continuing down to a line."]),

  h1("3  Approach"),
  h2("3.1  Recording the failing test"),
  p("qdebug is a pytest plugin. It runs the suite once with coverage to build the spectrum, then reruns the " +
    "failing test under a tracer that records one node per call, with its arguments and its return value or " +
    "exception. Values are kept at first only for the most suspicious 5% of functions, and the test is rerun " +
    "with a larger share when the search needs more. Values are rendered deterministically, with addresses " +
    "masked and random seeds fixed, so calls can be compared across runs."),
  h2("3.2  Questions and lines"),
  p(["For each call ", e("b"), ", qdebug keeps the probability that the bug is in ", e("b"), "’s own code, " +
     "starting from the Ochiai score of ", e("b"), "’s function. A question shows one call’s inputs and " +
     "output and asks whether the output is right. Each answer is taken to be correct with probability " +
     "1 − ε (ε = 0.1), and the belief is updated with Bayes’ rule. The next question is the call with the " +
     "largest expected drop in entropy. The search stops when one function holds 90% of the belief, or when " +
     "a call has been judged wrong and all its callees right. qdebug then replays that call with its local " +
     "variables recorded before every line, and searches for the first line where the state goes wrong " +
     "using the same model of noisy answers."]),
  h2("3.3  Search rules and grouping"),
  p("A few extra rules, the tuned policy, were added after failures on seeded bugs; for instance, in a crash " +
    "the calls the exception passed through get a higher prior. Turning them off gives the baseline policy. " +
    "Because Ochiai assumes one bug, qdebug also groups the failing tests first. Tests with the same " +
    "exception at the same project line start together, and two groups merge when a single line explains " +
    "them at least as well as each group’s own best line. The debugged test is ranked only against its group."),

  h1("4  Evaluation Design"),
  p("The tuned rules were built on 39 bugs we seeded into two small projects, so good numbers there say " +
    "little about real code. We therefore wrote down the plan, including what would count as success, " +
    "before running it."),
  h2("4.1  Data and setup"),
  p("BugsInPy [5] has 493 real bugs from 17 projects. The development set is the six projects used for an " +
    "earlier version of qdebug (PySnooper, cookiecutter, httpie, thefuck, tqdm and youtube-dl; 96 bugs). " +
    "The held-out set is six projects qdebug had never been run on (black, fastapi, luigi, sanic, tornado " +
    "and scrapy; 133 bugs), run once with the code frozen; the other five need heavy native builds. Bugs " +
    "run in a Linux Docker container and count only if the failing test fails before the fix and passes " +
    "after it. An oracle answers by comparing each call with the same call in the fixed version. Each bug " +
    "gets twelve sessions: three strategies (information gain, top-down, divide-and-query) under both " +
    "policies, plus the tuned information-gain search at 10% and 20% wrong answers, three seeds each."),
  h2("4.2  Research questions and analysis"),
  p("RQ1 asks how often qdebug names the buggy function and line, compared with the top 1, 3 and 5 entries " +
    "of the Ochiai and DStar rankings and with the crash location. RQ2 asks whether the tuned rules help, " +
    "RQ3 whether both answers hold on the held-out projects, RQ4 how much wrong answers hurt, and RQ5 which " +
    "bugs qdebug misses. A function counts as found if the fix changes it, and a line if a changed line is " +
    "in the reported region. Comparisons are paired on the same bugs, with McNemar’s exact test for found " +
    "or not and the Wilcoxon signed-rank test for question counts (α = 0.05). The study succeeds if qdebug " +
    "beats Ochiai’s top entry on the held-out set with p < 0.05 and the tuned policy is no worse than the " +
    "baseline."),

  h1("5  Results"),
  p("Of the 133 held-out bugs, 110 reproduced and 105 gave a completed session; of the 96 development " +
    "bugs, 81 did. Table 1 shows how often each technique found the buggy function and line."),
  table([
    ["", "Held-out function", "Held-out line", "Dev. function", "Dev. line"],
    ["qdebug", "49 (47%)", "37 (35%)", "63 (78%)", "35 (43%)"],
    ["Ochiai top-1", "23 (22%)", "13 (12%)", "48 (59%)", "20 (25%)"],
    ["Ochiai top-3", "41 (39%)", "29 (28%)", "62 (77%)", "32 (40%)"],
    ["Ochiai top-5", "54 (51%)", "36 (34%)", "64 (79%)", "42 (52%)"],
    ["DStar top-1", "23 (22%)", "13 (12%)", "45 (56%)", "19 (23%)"],
    ["Crash location (crashes only)", "11/20", "–", "18/24", "–"],
  ], [2700, 1500, 1400, 1500, 1300]),
  caption([{ t: "Table 1. ", b: true }, "Bugs where the buggy function or line was found (held-out " +
    "n = 105, development n = 81). qdebug uses the tuned policy, information gain, and no wrong answers."]),
  p([{ t: "RQ1 and RQ3. ", i: true },
     "On the held-out set qdebug named the buggy function twice as often as Ochiai’s top entry (28 bugs " +
     "found only by qdebug, 2 only by Ochiai; McNemar p < 0.001), and the buggy line almost three times as " +
     "often (p < 0.001), which meets the success criterion. Its one answer did about as well as Ochiai’s " +
     "top three (p = 0.17). All numbers drop on the held-out projects, Ochiai’s most (59% to 22%, against " +
     "78% to 47%). These projects are larger: 45 of 105 failing tests made 100 or more calls, against 13 " +
     "of 81."]),
  p([{ t: "RQ2. ", i: true },
     "The tuned rules found no more bugs than the baseline (49 against 50, p = 1.0) but asked fewer " +
     "questions, 10.7 against 13.4 on average (Wilcoxon p < 0.001). Information gain found about as many " +
     "bugs as top-down and divide-and-query, and asked significantly fewer questions only on the " +
     "development set."]),
  p([{ t: "RQ4 and RQ5. ", i: true },
     "With 10% and 20% of answers wrong, qdebug still found the held-out function in 39% and 35% of " +
     "sessions, but the line in only 24% and 16%. It did as well on runs of 100+ calls as on smaller ones " +
     "(47%), where Ochiai’s top entry fell from 28% to 13%. Results ranged from 18 of 26 bugs on scrapy to " +
     "3 of 14 on tornado. The run also exposed a qdebug bug, now fixed: pydantic’s classes without " +
     "__module__ stopped the tracer, so all fastapi bugs were run again."]),

  h1("6  Discussion and Threats to Validity"),
  p("The questions help most where the ranking is weakest. In a large failing run, many functions are " +
    "likely run by every failing test and tie near the top, and a few answers about values tell them " +
    "apart. One answer as good as a top-three list matters, since developers rarely read far down a list " +
    "[3]. Still, half the held-out bugs were missed, and we have not yet studied why; the worst projects, " +
    "tornado and fastapi, do much of their work in asynchronous code."),
  p("The oracle never errs, and people do. The noisy runs only approximate that, so a small user study is " +
    "planned. A spectrum from the bug’s own test files weakens SBFL and qdebug’s prior alike. Some old " +
    "pins were relaxed, and a fix can change lines unrelated to the bug."),

  h1("7  Conclusion"),
  p("qdebug treats an SBFL ranking as a prior and asks yes/no questions about recorded calls until one " +
    "function is likely enough, then narrows it to a line. On real bugs from projects it was never tuned " +
    "on, it found the buggy function more than twice as often as Ochiai’s top entry, with about eleven " +
    "questions, and stayed ahead of it with one answer in five wrong. Next we will test it with " +
    "developers and study the bugs it misses."),

  h1("References"),
  ref(1, "R. Abreu, P. Zoeteweij, and A. J. C. van Gemund. On the accuracy of spectrum-based fault " +
         "localization. In TAICPART-MUTATION, 2007."),
  ref(2, "W. E. Wong, V. Debroy, R. Gao, and Y. Li. The DStar method for effective software fault " +
         "localization. IEEE Transactions on Reliability, 63(1), 2014."),
  ref(3, "C. Parnin and A. Orso. Are automated debugging techniques actually helping programmers? In ISSTA, 2011."),
  ref(4, "E. Y. Shapiro. Algorithmic Program Debugging. MIT Press, 1983."),
  ref(5, "R. Widyasari et al. BugsInPy: A database of existing bugs in Python programs to enable controlled " +
         "testing and debugging studies. In ESEC/FSE, 2020."),
  ref(6, "M. Rezaalipour and C. A. Furia. An empirical study of fault localization in Python programs. " +
         "Empirical Software Engineering, 2024."),
  ref(7, "J. Silva. A survey on algorithmic debugging strategies. Advances in Engineering Software, 42(11), 2011."),
  ref(8, "X. Li, S. Zhu, M. d’Amorim, and A. Orso. Enlightened debugging. In ICSE, 2018."),
];

const doc = new Document({
  creator: "Suyash Patel",
  title: "qdebug: Locating Faults in Python Programs with Yes/No Questions",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true },
        paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 22, bold: true, italics: true },
        paragraph: { spacing: { before: 120, after: 40 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
                          margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    children: body,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(out, buf); console.log("wrote", out); });
