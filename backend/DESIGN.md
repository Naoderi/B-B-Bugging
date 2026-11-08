---
name: Campus Index
description: A paper ETF research lab for UK university students, kept like a ledger book.
colors:
  navy-buckram: "#1d2a44"
  navy-link: "#2f4a78"
  navy-hover: "#26365a"
  page: "#fbfcfd"
  sheet: "#ffffff"
  ink: "#1a2233"
  sub-ink: "#465269"
  feint-rule: "#9fb6d6"
  feint-line: "#d5dfec"
  edge: "#6f84a6"
  pale-blue: "#eef2f8"
  margin-red: "#b3372f"
  red-wash: "#fcf3f2"
  rail-label: "#a9bbd8"
  rail-text: "#d3dcea"
  rail-divider: "#34476e"
  series-1: "#1d2a44"
  series-2: "#4a6aa0"
  series-3: "#8a6a2c"
  series-4: "#7f9cc8"
  series-5: "#5e7387"
  series-6: "#c4d2e6"
  series-cash: "#dbe4f0"
typography:
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.015em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  section:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    fontFeature: "tnum"
  body-small:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "0.08em"
  mono:
    fontFamily: "ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
rounded:
  none: "0px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "36px"
components:
  button-primary:
    backgroundColor: "{colors.navy-buckram}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.none}"
    padding: "10px 16px"
    height: "42px"
  button-primary-hover:
    backgroundColor: "{colors.navy-hover}"
  button-secondary:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.navy-buckram}"
    rounded: "{rounded.none}"
    padding: "10px 16px"
    height: "42px"
  button-secondary-hover:
    backgroundColor: "{colors.pale-blue}"
  input:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0 11px"
    height: "44px"
  nav-item:
    textColor: "{colors.rail-text}"
    typography: "{typography.body-small}"
    padding: "10px"
  nav-item-active:
    backgroundColor: "{colors.navy-hover}"
    textColor: "{colors.sheet}"
  tag:
    textColor: "{colors.navy-buckram}"
    rounded: "{rounded.none}"
    padding: "3px 9px"
  tag-warning:
    backgroundColor: "{colors.red-wash}"
    textColor: "{colors.margin-red}"
  notice:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    padding: "11px 13px"
  notice-warning:
    backgroundColor: "{colors.red-wash}"
    textColor: "{colors.ink}"
---

# Design System: Campus Index

## Overview

**Creative North Star: "The Ledger Book"**

Every proposal is a ledger entry, referenced by its Guardian digest and closed with a double rule only when the student signs. The app is bound like an account book: a navy buckram rail down the left, a cool white page ruled in feint blue, and a red margin rule separating the binding from the work. Entries sit on ruled lines rather than in floating cards; the reader scans a book, not a dashboard.

Density is moderate and tabular. Numbers line up (tabular figures everywhere), every figure in the Coach's prose carries a red footnote number that resolves to a numbered fact list, and the agent trace reads like a column of journal postings, with tool names in mono. State is carried by form before colour: a double rule closes, a dashed box waits, red ink with a red box vetoes, a line-through rejects. Colour alone never carries a state.

The system rejects the green-on-cream fintech look it replaced: no cream page, no serif display hero, no glows, no sparkle, no rounded pills with dots, no tinted icon tiles, no shadows.

**Key Characteristics:**
- Navy buckram rail, cool white page, feint-blue ruling, one red margin rule.
- One system sans; tabular figures; mono only for digests, tool names and ids.
- Square corners and flat colour throughout.
- State grammar by form: double rule, dashed box, red box, line-through.
- Red footnote citations tied to a numbered fact list.

## Colors

A cool, paper-and-binding palette: navy and blue-grey carry structure, ink carries text, and one red is reserved for the margin, citations and refusal.

### Primary
- **Navy Buckram** (navy-buckram): the binding. Sidebar rail, mobile top bar and nav strip, primary button fill, completed step markers, the toast, the "Paper trading" double underline, and the first data series. Also the `theme-color` and the mark's ground.
- **Ledger Link Navy** (navy-link): links, focus rings (2px outline), quiet buttons, inline icons, and the "you said" citation.
- **Buckram Shade** (navy-hover): rail hover and active nav fill; primary button hover.

### Secondary
- **Margin Red** (margin-red): reserved. Only the 3px double margin rule down the work area, citation superscripts and fact-list markers, veto and warning ink (warning tag, warning notice title, failed agent icon, rejected-quote text, form errors), and the bad-citation marker. Never decorative, never for emphasis.
- **Red Wash** (red-wash): the ground behind a warning notice or warning tag, and the targeted fact in the fact list.

### Neutral
- **Cool Page** (page): the page ground. Cool white, never cream.
- **Sheet White** (sheet): top bar, footer, entries, inputs, option tiles.
- **Ledger Ink** (ink): body text, headings, the closing double rule.
- **Sub Ink** (sub-ink): secondary text, meta lines, page-head folios, rejected (struck) figures.
- **Feint Rule** (feint-rule): the primary ruling line: top/bottom of entries, top bar and footer, stat grid, page-head divider, the trace's left rule, neutral tag border.
- **Feint Line** (feint-line): lighter inner ruling: rows inside entries, table rows, trace rows, form dividers.
- **Binding Edge** (edge): input and option borders, table header underline, step markers, scrollbar thumb, breadcrumb slash.
- **Pale Blue** (pale-blue): the student's own chat entry, selected option ground, secondary hover, allocation bar track.
- **Rail Label / Rail Text / Rail Divider** (rail-label, rail-text, rail-divider): pale-blue labels, nav text and hairline dividers on the navy rail.

### Data series
Six series in fixed order (series-1 to series-6, from the app's `colour` array), plus series-cash for uninvested cash. Used for allocation bar segments, holding swatches and benchmark chart lines (series-1 drawn at 3px, the third series dashed 5 3). Swatches are square with a faint ink outline.

### Named Rules
**The Reserved Red Rule.** Red marks the margin, the citations and refusals. Nothing else is red; if a new element wants red, it is either a veto/warning or it is wrong.

**The Never Cream Rule.** The page is cool white (page) on feint-blue ruling. Warm paper tones are the world this system replaced.

## Typography

**Body Font:** the system sans stack (-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif)
**Label/Mono Font:** ui-monospace, SF Mono, Menlo, Consolas, monospace

**Character:** One plain system sans does every job, from page title to footnote, the way a printed account book uses one face. Mono appears only where the content is machine-identity: digests, tool names, fact ids, run ids, CSV previews.

### Hierarchy
- **Headline** (700, 30px, 1.15, -0.015em): page titles; also the plan's balance figure in the snapshot. 26px on mobile.
- **Title** (700, 24px, 1.2): decision headings ("Proposed allocation", "Proposal rejected").
- **Form title** (700, 22px, 1.25): setup step headings; 20px on mobile.
- **Section** (700, 20px, 1.3): entry headings ("Agent trace", "Target holdings"); stat figures also sit at 20px (18px mobile).
- **Body** (400, 15px, 1.55): base text; 14px inside chat entries, notices and nav.
- **Body small** (13px, about 1.45): meta lines, trace details (12px), table cells, legends.
- **Label** (650, 11px, 0.08em, uppercase): rail group labels, and the frozen uppercase copy described below.
- **Mono** (12px; 13px/600 for tool names in the trace).

### Named Rules
**The One Face Rule.** No display face, no serif, no Georgia. Hierarchy comes from size and weight in the system sans only.

**The Tabular Rule.** `font-variant-numeric: tabular-nums` is set on the body and restated on inputs, stats, tables and allocation figures. Every column of numbers aligns.

**The Frozen Folio Rule.** The existing uppercase labels (for example "AGENTIC ETF COACH", "AGENT DECISION", "YOUR FICTIONAL PLAN") are copy the user froze word-for-word. The system places them as a right-aligned folio on the title row of the page head, or beneath an h2 via column-reverse/ordering, never as a kicker above a heading. New work must not add new eyebrow labels.

## Layout

A fixed navy rail (224px; 192px under 1100px) holds the brand, Workspace and Research nav groups and a foot seal. The workspace to its right has a 64px white top bar (breadcrumb left, "Paper trading" right), then `main` behind the red margin: a 3px double red left border, max 1220px wide, inset 36px (23px under 1100px). The page head is a two-column grid: title left, folio label right, both on one baseline, with the intro below a feint rule spanning the full width.

Content uses a two-column grid: main column plus a side column (269px; 330px when it holds the Coach trace; 231px under 1100px), 24px gap. Under 900px it stacks and the side column becomes two-up. Under 680px the rail disappears: the top bar turns navy with the mobile brand, a horizontally scrolling navy nav strip appears beneath it (faded at the right edge), the margin rule stays with a 10px inset, and the folio drops below the title, left-aligned.

Spacing rhythm is roughly 8 / 12 / 16 / 24 / 36px; entries pad 22px 24px. Touch targets hold at 44px (inputs, holding remove buttons, allocation rows) and 42px (buttons).

## Elevation & Depth

Flat. There are no drop shadows anywhere; depth is conveyed by ruling and binding instead. Entries are distinguished by feint-blue top and bottom rules on white against the cool page, the rail by a full navy field, and emphasis by heavier rules (3px double) rather than lift. The only `box-shadow` in the build is a 1px inset on the selected option tile, which doubles its navy border; it is a border weight, not elevation.

### Named Rules
**The Ruled Not Lifted Rule.** Separate things with rules and fields of colour. If a surface needs to stand out, give it a heavier rule, never a shadow or glow.

## Shapes

Square corners everywhere (0px radius on buttons, inputs, textareas, tags, notices, step markers, swatches). Borders are 1px solid in feint-rule or edge; heavier meaning is carried by line style, not radius: 3px double for closure, 1px dashed for awaiting, 1px dotted for pending agent steps and for unresolved citations. The mark is a navy square ruled with feint-blue lines, a red double margin and a white double closing rule: the system in miniature.

## Components

### State grammar (signature)
State is drawn by line form; colour only reinforces.
- **Closed / signed / approved:** a 3px double ink (or navy) rule. The Guardian row in the trace opens with a 3px double ink top rule; the approved notice carries a 3px double ink bottom rule; the "Paper trading" mark and approved tags carry a 3px double navy underline; the last row of every table closes with a 3px double ink rule; the toast closes with a 3px double white rule.
- **Awaiting:** a 1px dashed ink box ("Awaiting review" tag). Pending agent steps use a 1px dotted edge box around their number.
- **Veto / warning:** red ink inside a 1px red box on red wash (warning notice, "Safety veto" and "Actions paused" tags). Failed agent icons are red with a red box.
- **Rejected:** line-through in sub-ink. Struck figures (stats, allocation values) and the "Closed" tag are struck; the verdict title ("Proposal rejected") stays full ink and unstruck.
- **Neutral:** a plain 1px feint-rule box.

### Buttons
- **Shape:** square (0px), 42px minimum height, 10px 16px padding, 14px/650.
- **Primary:** navy buckram fill, white text; hover to buckram shade.
- **Secondary:** white with a 1px navy border and navy text; hover to pale blue.
- **Quiet:** borderless, underlined link-navy text, 13px/650.
- **Icon button:** 1px edge border, transparent, 16px icon.
- **Focus:** 2px link-navy outline, 3px offset (white on the rail). Disabled at 55% opacity.

### Tags
Square, 1px border, 12px/650, 3px 9px padding. Variants follow the state grammar: approved/paper (no box, 3px double navy underline), pending (dashed ink box), warning (red box on red wash), struck (line-through, sub-ink), neutral (feint-rule box). No dots, no rounded pills.

### Entries (cards)
- **Corner Style:** square.
- **Background:** sheet white on the cool page.
- **Shadow Strategy:** none (see Elevation).
- **Border:** feint-rule top and bottom only; no side borders.
- **Internal Padding:** 22px 24px (14px sides on mobile).

### Notices
1px feint-rule box on white, 11px 13px padding, title in bold navy. Warning: red box on red wash with a red title. Closed (approved): adds the 3px double ink bottom rule.

### Inputs / Fields
- **Style:** 1px edge border, white, square, 44px tall; units shown inside in sub-ink; values 600 weight, tabular.
- **Focus:** border to navy plus a 2px link-navy outline at 1px offset.
- **Option tiles:** 1px edge box; hover pale blue; selected gets navy border doubled by a 1px inset, pale-blue ground, and an underlined label.
- **Error:** red text above the form; never a red-tinted field.

### Navigation
Rail items are full-width square rows, 14px/550 in rail text with a 17px line icon. Hover fills with buckram shade. Active fills with buckram shade, turns white and 700, and underlines the label with a rail-label underline at 5px offset. Group labels are 11px uppercase rail-label. On mobile the same items become a compact scrolling strip on navy.

**Recorded deviation from the direction contract.** The contract's first viewport asked for the active item to be "marked by a white left rule". The build deliberately uses a buckram-shade fill plus underline instead, because the craft floor bans coloured side stripes above 1px on list items. This is the canonical active treatment; do not reintroduce a left stripe.

### Margin rule
**Recorded adaptation.** The contract's "one red margin rule" landed as a 3px double red left border on the work area (a ledger margin), not a single line. It is the only structural use of red.

### Citations and fact list
Figures in the Coach's prose carry red 11px/700 tabular superscript numbers linking to a collapsible numbered fact list; the list's markers are red and bold, each fact led by its id in mono, and the targeted fact is washed red. "You said" citations are link-navy with a dotted underline; unresolved citations are red with a dotted red underline.

### Agent trace
A ruled list: rows separated by feint lines, a 20px mono marker column (line icon, step number, or what-if id), bold title and 12px sub-ink detail. Tool names render in mono 13px/600. The Guardian row is opened by a 3px double ink rule. Pending markers sit in a dotted box; failed ones in a red box.

### Digest reference mark
The Guardian digest (and similar ids inside meta lines) shows as a boxed reference: mono 12px in ink inside a 1px feint-rule box, 1px 5px padding, never wrapping. It is the entry's reference number.

### Chat entries
The student's entry is a pale-blue block, right-aligned, with a feint-rule bottom line. The Coach's entry is full-width white between feint-rule top and bottom rules, flush left. Messages are 14px.

### Data display
Stat grids are three columns between feint-rule rules with feint-line dividers; figures 20px/700. Allocation is a 10px bar of square series segments separated by 2px white gaps inside an edge outline, followed by expandable rows with a square swatch, ticker, name and right-aligned tabular figures. Tables are 13px with feint-line rows, an edge-ruled header, and the closing 3px double ink rule on the last row.

### Motion
Minimal and only under `prefers-reduced-motion: no-preference`: background transitions of 0.14s ease on buttons, nav items and option tiles; the toast arrives with a 5px rise and fade over 0.2s (cubic-bezier(.16,1,.3,1)).

## Do's and Don'ts

### Do:
- **Do** close a signed or approved record with a 3px double ink (or navy) rule, and only then.
- **Do** mark awaiting with a 1px dashed box, veto with red ink in a 1px red box, and rejection with a sub-ink line-through while the verdict title stays full ink.
- **Do** cite every figure in prose with a red superscript that resolves to the numbered fact list.
- **Do** show digests as the boxed mono reference mark and tool names in mono.
- **Do** separate entries with feint-blue rules on white over the cool page.
- **Do** keep corners square and colour flat.
- **Do** place the frozen uppercase labels as a right-aligned folio on the title row or beneath the h2.

### Don't:
- **Don't** add shadows, glows, radius, rounded pills, status dots or tinted icon tiles.
- **Don't** use a cream or warm page, a serif or display face, or Georgia.
- **Don't** use red for anything but the margin rule, citations and veto/warning.
- **Don't** add new eyebrow or kicker labels above headings.
- **Don't** mark the active nav item with a coloured left stripe; use the fill plus underline.
- **Don't** let colour alone carry a state; draw it with the line form.
