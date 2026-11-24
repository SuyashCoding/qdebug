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
      alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, spacing: { after: 0, line: 228 }, keepNext: true,
      children: [new TextRun({ text, font: FONT, size: 19, bold: r === 0 || rows[r][0] === "qdebug" })],
    })],
  });
  return new Table({
    width: { size: widths.reduce((a, b) => a + b), type: WidthType.DXA },
    columnWidths: widths, alignment: AlignmentType.CENTER,
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: rows.map((row, r) => new TableRow({ cantSplit: true, children: row.map((t, i) => cell(t, i, r)) })),
  });
}
const caption = (segs) => new Paragraph({
  children: runs(segs), alignment: AlignmentType.CENTER, spacing: { before: 60, after: 100, line: 240 },
});
const e = (t) => ({ t, i: true });
const sub = (t) => ({ t, i: true, sub: true });

const TITLE = "qdebug: Finding Python Bugs with Yes/No Questions";
const li = (n, segs) => new Paragraph({
  children: runs([{ t: `${n}. `, b: true }].concat(segs)), alignment: AlignmentType.JUSTIFIED,
  indent: { left: 300, hanging: 300 }, spacing: { after: 60, line: 252 },
});

const body = [
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: TITLE, font: FONT, size: 32, bold: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: "Suyash Patel", font: FONT, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED, indent: { left: 540, right: 540 },
    spacing: { after: 200, line: 252 },
    children: runs([{ t: "Abstract. ", b: true },
      "A failing test shows that a program is wrong, but not where. qdebug finds the faulty line by asking the developer simple questions about values: given these inputs, is this output " +
      "right? It starts from a ranking of suspicious code, picks each question to rule out the most, and " +
      "allows for wrong answers. We tested it on real bugs from twelve open-source " +
      "Python projects. On the six projects that were never used while building it, qdebug named the buggy " +
      "function for 47% of 105 bugs, about twice as often as the top entry of a standard ranking (22%)."]),
  }),

  h1("1  Introduction"),
  p("Suppose a test for an online shop expects a total of 15 and gets 20. Something is wrong, but the " +
    "mistake could be in any function that ran on the way to that total. Two families of tools help. Spectrum-based fault localization (SBFL) ranks functions or lines by " +
    "how much more often failing tests run them than passing tests do [1, 2]. The developer still has to go " +
    "down the list, and Parnin and Orso [3] found that developers do not read such lists in order. Algorithmic debugging [4] instead records the failing run " +
    "as a tree of function calls and asks, for one call at a time, whether its result was right. If a call " +
    "returned a wrong result while every call it made returned a right one, the bug must be in that call’s " +
    "own code, so the developer only judges values. But a large program needs many questions, and one wrong " +
    "answer sends the search the wrong way."),
  p("qdebug combines the two. It uses the SBFL ranking as a starting guess, always asks the question that is " +
    "expected to tell it the most, treats every answer as possibly wrong, and then narrows the bug down from " +
    "a function to a line. We describe how it works and report a study on real bugs, planned before it ran."),

  h1("2  Background and Related Work"),
  p(["For each piece of code, SBFL counts the failing tests that run it, ", e("e"), sub("f"),
     ", and the passing tests that run it, ", e("e"), sub("p"), ". With ", e("F"), " failing tests in total, " +
     "Ochiai [1] scores it as ", e("e"), sub("f"), " / √(", e("F"), "(", e("e"), sub("f"), " + ", e("e"),
     sub("p"), ")) and DStar [2] as ", e("e"), sub("f"), { t: "2", sup: true }, " / (", e("e"), sub("p"),
     " + ", e("F"), " − ", e("e"), sub("f"), "). Both are high for code that many failing and few passing " +
     "tests run, and both assume there is only one bug. On BugsInPy, Rezaalipour and Furia [6] found that " +
     "for crashes, pointing at the innermost project function in the stack trace is hard to beat. " +
     "Algorithmic debugging began with Shapiro [4]; later strategies such as top-down and divide-and-query " +
     "differ in which call they ask about next [7]. The closest work to ours is Enlighten [8], which asks " +
     "Java developers about method calls chosen with help from SBFL. qdebug differs in three ways: it chooses " +
     "questions by expected information gain, it models wrong answers, and it continues down to a line."]),

  h1("3  How qdebug Works"),
  li(1, [{ t: "Rank. ", i: true }, "qdebug, a plugin for the pytest test runner, runs the whole suite once, records which code each test " +
    "runs, and gives every function an Ochiai score."]),
  li(2, [{ t: "Record. ", i: true }, "It reruns the failing test and records one node per function call, " +
    "with its arguments and its return value or exception. At first only the most suspicious 5% of " +
    "functions are recorded in full, and more if needed. Values are printed the same way every run " +
    "(addresses hidden, random seeds fixed), so calls can be compared across runs."]),
  li(3, [{ t: "Ask about calls. ", i: true }, "For every call, qdebug keeps a probability that the bug is in " +
    "that call’s own code, starting from its function’s Ochiai score. A question shows one call’s inputs and " +
    "output and asks whether the output is right. Each answer is assumed to be correct with probability 0.9, " +
    "and Bayes’ rule updates the probabilities, so later answers can outvote a wrong one. " +
    "The next question is the one expected to reduce uncertainty (entropy) the most, like asking “is it an " +
    "animal?” first in twenty questions. The search stops when one function holds 90% " +
    "of the probability, or when a call has been judged wrong and all the calls it made right."]),
  li(4, [{ t: "Find the line. ", i: true }, "qdebug replays the blamed call, records its local variables " +
    "before every line, and asks at chosen lines whether the program is still on the right track: no if a " +
    "variable is already wrong or a correct program would never be at that line with these values. The " +
    "same model of wrong answers finds the first line where things go wrong."]),
  li(5, [{ t: "Extras. ", i: true }, "Since Ochiai assumes one bug, qdebug groups the failing tests " +
    "by the bug that probably causes them (same exception at the same line, or one line that explains " +
    "both groups) and ranks the debugged test only against its own group. A few extra rules, the tuned " +
    "policy, came from qdebug’s failures on bugs we planted; for example, in a crash the calls the " +
    "exception passed through start more suspect. Without them, it is the baseline policy."]),

  h1("4  How We Evaluated It"),
  p([{ t: "Data. ", i: true }, "Since the tuned rules came from 39 bugs we planted, we tested on real bugs, " +
    "with a plan written first. BugsInPy [5] collects 493 real bugs from 17 Python projects, each with the code before and " +
    "after the developers’ fix and a test that shows the bug. The ", { t: "development set", i: true },
    " is six projects used for an earlier version of qdebug (PySnooper, cookiecutter, httpie, thefuck, tqdm " +
    "and youtube-dl; 96 bugs). The ", { t: "held-out set", i: true }, " is six projects qdebug had never " +
    "been run on (black, fastapi, luigi, sanic, tornado and scrapy; 133 bugs), run once with the code " +
    "frozen; the other five projects need heavy native builds. Bugs ran in a " +
    "Linux Docker container and counted only if the failing test failed before the fix and passed after it."]),
  p([{ t: "Answers and sessions. ", i: true }, "A program answers the questions: it runs the same call in " +
    "the fixed version and says “right” if the outputs match. To imitate human mistakes, it was also made " +
    "to answer wrongly 10% and 20% of the time. Each bug got twelve sessions: information gain, top-down " +
    "and divide-and-query under both policies, plus tuned information gain at 10% and 20% wrong (3 seeds)."]),
  p([{ t: "Questions. ", i: true }, "RQ1: how often does qdebug find the buggy function and line, against " +
    "the top 1, 3 and 5 entries of the Ochiai and DStar rankings and the crash location? RQ2: do the tuned " +
    "rules help? RQ3: do the answers hold on held-out projects? RQ4: how much do wrong answers hurt? RQ5: " +
    "which bugs does qdebug miss? A function is found if the fix changes it, and a line if a changed line " +
    "is in the reported region. We compared methods on the same bugs with McNemar’s exact test, which looks " +
    "only at bugs one method finds and the other misses, and with the Wilcoxon signed-rank test for " +
    "question counts (α = 0.05). Success meant beating Ochiai’s top entry on the held-out set with " +
    "p < 0.05, with the tuned policy no worse than the baseline."]),

  h1("5  Results"),
  p("Of the 133 held-out bugs, 110 reproduced and 105 gave a completed session; of the 96 development " +
    "bugs, 81 did. Table 1 shows how often each technique found the buggy function and line."),
  p([{ t: "RQ1 and RQ3: qdebug beats the top of the ranking. ", i: true },
     "On the held-out set, qdebug found the buggy function twice as often as Ochiai’s top entry. Only " +
     "qdebug found it for 28 bugs and only Ochiai for 2 (McNemar p < 0.001), and qdebug found the line " +
     "almost three times as often (p < 0.001), so the success criterion was met. Its single answer did " +
     "about as well as reading Ochiai’s top three (p = 0.17). Every number is lower on the held-out " +
     "projects, but Ochiai’s fell further (59% to 22%, against 78% to 47%); 45 of 105 held-out failing " +
     "tests made 100 or more calls, against 13 of 81."]),
  p([{ t: "RQ2: the tuned rules save questions. ", i: true },
     "They found no more bugs than the baseline (49 against 50, p = 1.0) but asked fewer questions, 10.7 " +
     "against 13.4 on average (Wilcoxon p < 0.001). Information gain found about as many bugs as top-down " +
     "and divide-and-query, and asked significantly fewer questions only on the development set."]),
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
  p([{ t: "RQ4 and RQ5: wrong answers hurt lines more than functions. ", i: true },
     "With 10% and 20% of answers wrong, qdebug still found the held-out function in 39% and 35% of " +
     "sessions, but the line in only 24% and 16%. It did as well on runs of 100+ calls as on smaller ones " +
     "(47%), where Ochiai’s top entry fell from 28% to 13%. Results ranged from 18 of 26 bugs on scrapy to " +
     "3 of 14 on tornado. The run also exposed a bug in qdebug, now fixed: classes without __module__, " +
     "which the pydantic library creates, stopped the tracer, so all fastapi bugs were run again."]),

  h1("6  Discussion and Threats to Validity"),
  p("The questions help most where the ranking is weakest. In a large failing run, many functions are " +
    "likely run by every failing test and tie near the top of the ranking, and a few answers about values " +
    "tell them apart. One answer that is as good as a top-three list matters, since developers rarely read " +
    "far down a list [3]. Still, half the held-out bugs were missed, and we have not yet studied why; the " +
    "worst projects, tornado and fastapi, do much of their work in asynchronous code."),
  p("The automatic answerer never makes the mistakes people make. The runs with wrong answers only " +
    "approximate that, so a user study is planned. Using only the bug’s own test files weakens the rankings " +
    "and qdebug’s guess alike. Some old library versions were replaced, and a fix can change unrelated lines."),

  h1("7  Conclusion"),
  p("qdebug treats an SBFL ranking as a starting guess and asks yes/no questions about recorded calls until " +
    "one function is likely enough, then narrows it to a line. On real bugs from projects it was never " +
    "tuned on, it found the buggy function more than twice as often as Ochiai’s top entry, with about eleven " +
    "questions, and stayed ahead of it with one answer in five wrong."),

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
  title: TITLE,
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
