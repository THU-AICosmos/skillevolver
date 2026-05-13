You are assisting a graduate student who is finalizing a literature review. The student is worried that some references in their bibliography may have been fabricated or hallucinated by an AI assistant they used during drafting.

The bibliography file is located at `/root/references.bib` and contains a mixture of legitimate and potentially fabricated academic references. Your job is to determine which references are fabricated.

Write your results to `/root/verification_report.json` in the following format:

```json
{
  "suspicious_entries": [
    "Title of first fabricated paper",
    "Title of second fabricated paper",
    ...
  ]
}
```

Notes:
- Return only the **titles** of fabricated references in the `suspicious_entries` array
- Titles should be cleaned (remove BibTeX formatting like `{}` or `\`)
- Sort titles alphabetically for consistency
