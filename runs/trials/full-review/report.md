# Full overlapping-window KM review

## Outcome

All 10 KM panels are accepted with result-signature-bound scan evidence. Each source was reviewed left-to-right in overlapping windows, with a source-only board plus one focused overlay per curve. All visible number-at-risk cells were checked against their source tables.

| Panel | Windows | Decision | Material action |
| --- | ---: | --- | --- |
| study01/os | 7 | accepted base | none |
| study01/pfs | 7 | reverified accepted result | prior early-curve repair retained |
| study02/os | 7 | accepted base | none |
| study02/pfs | 7 | accepted base | none |
| study03/os | 5 | accepted base | none |
| study03/pfs | 5 | accepted revision `r0002` | both coarse curves rebuilt from visible pixel breakpoints |
| study04/os | 5 | accepted revision `r0002` | Nivolumab segments rebuilt through crossings and annotation interference |
| study04/pfs | 6 | accepted revision `r0001` | unsupported Nivolumab extension from x=363-385 removed |
| study05/os | 7 | accepted base | none |
| study05/pfs | 7 | accepted base | none |

## Evidence

- [All 10 accepted overlays](accepted-overlays-contact-sheet.png)
- [Machine-readable summary](../../summary.json)
- [study03/pfs difficult-panel report](../study03-pfs-scan/report.md)
- [study04/os difficult-panel report](../study04-os-scan/report.md)
- [study04/pfs before/after terminal comparison](study04-pfs/comparison/w006_curve_1_comparison.png)
- [study04/pfs accepted overlay](study04-pfs/accepted/overlay.png)
- [study01/os accepted decision](study01-os/accepted/review_decision.json)
- [study01/pfs reverified decision](study01-pfs/accepted/review_decision.json)
- [study02/os accepted decision](study02-os/accepted/review_decision.json)
- [study02/pfs accepted decision](study02-pfs/accepted/review_decision.json)
- [study03/os accepted decision](study03-os/accepted/review_decision.json)
- [study05/os accepted decision](study05-os/accepted/review_decision.json)
- [study05/pfs accepted decision](study05-pfs/accepted/review_decision.json)

## Review notes

- `study01/pfs` ends earlier for Sorafenib in the source itself; the shorter x coverage is not an extraction defect.
- `study04/pfs` produces curve-proximity diagnostics near the origin and around 21-25 months. Source-only overlapping windows show continuous dark and light identities, so these are documented false positives rather than forced edits.
- No score was used as an acceptance threshold. Every acceptance came from visual agreement recorded per window and per curve.
