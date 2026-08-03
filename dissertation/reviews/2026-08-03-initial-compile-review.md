# Initial dissertation compile review

Review date: 2026-08-03

Authoritative editor: Overleaf

GitHub reference commit: `d05b6c86b8ced810ac47d9ed96bb73b6eba7db36`

Evidence: 56-page LuaTeX PDF, Overleaf source ZIP, GitHub submodule, and two
complete supplied log screenshots.

## Actionable findings

| Severity | Source | Finding | Proposed Overleaf correction |
|---|---|---|---|
| Provenance | `releases/2026-08-03-initial/source.zip`; `manuscript/chapter/ch7_limitations.tex:11` | The 19:49 source export says `Limitations and Conclusion`, while the 20:07 GitHub import says `Limitations and Future Work`. The release PDF/ZIP therefore cannot be assigned to commit `d05b6c8` exactly. | Keep the release manifest at `commit_unverified`. After the next Overleaf edit, compile and export the PDF/ZIP immediately before pushing the same state to GitHub, then verify an exact source match locally. |
| Error | `manuscript/main.tex:14-19`; `manuscript/chapter/ch2_literature_review_working.tex:32` | `\mathbb` is undefined because only `amsmath` is loaded. | Load `amssymb` once; remove duplicate `amsmath` and `graphicx` declarations. |
| Warning | `manuscript/main.tex:23-28` | `fancyhdr` reports that `\headheight` 12 pt is below 14.49998 pt. | Add `\setlength{\headheight}{14.5pt}` after configuring the header. |
| Layout | `manuscript/chapter/ch2_literature_review_working.tex:9` | The Chapter 2 title is wider than the heading line. | Prefer the shorter title `Literature Review`; alternatively change the global chapter-title layout only after checking every chapter opening. |
| Layout | `manuscript/chapter/ch2_literature_review_working.tex:82` | The section title produces an overfull box. | Shorten it to `Limits to Arbitrage`; retain the semantic-mismatch discussion in the section body. |
| Layout | `manuscript/chapter/ch2_literature_review_working.tex:97-111` | The four-column RQ table has overfull and severely underfull cells. | Load `tabularx`, replace the fixed paragraph widths with `@{}l X X p{0.17\textwidth}@{}`, and visually recheck the complete table. |
| Layout | `manuscript/chapter/ch4_data.tex:42-59` | `get_tradingview_chart_data` cannot break and overlaps adjacent table content. | Load `xurl`, render API method names with `\path{...}`, and visually recheck the complete table. |
| Layout | `manuscript/chapter/ch1_introduction.tex:73-85` | A low-severity 3.14323 pt overfull paragraph remains. | Recompile after the preamble and table fixes; if it remains, make a minimal prose line-break improvement without changing numerical content. |
| Style | `manuscript/main.tex:9` | Default `hyperref` coloured link borders are visible throughout the PDF. | Use `\usepackage[hidelinks]{hyperref}` unless UCL guidance requires another link style. |
| Content | `manuscript/main.tex:56-59` | The dissertation title remains a template placeholder. | Replace it with the approved final title. |
| Content | `manuscript/sections/abstract.tex`; `manuscript/sections/acknowledgements.tex`; `manuscript/main.tex:197-207` | Abstract, acknowledgements, appendix, and project summary remain placeholders. | Complete or intentionally remove each item before submission. |
| Copy | `manuscript/main.tex:77`; `manuscript/main.tex:87` | `Acadamic` is misspelled and the disclaimer omits spaces after full stops. | Change it to `Academic`; rewrite the disclaimer with correct sentence spacing while preserving the required UCL wording. |

## Review boundary

No dissertation source was edited locally. The review records changes to make
in Overleaf during the next authoritative editing cycle. A complete raw
`output.log` was not available, so compile-log evidence is limited to the two
supplied screenshots; both are preserved in the initial release directory.
