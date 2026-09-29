# Document Change Reviewer

Compare two editions of an announcement, methodology or product-terms document. The tool returns exact additions, deletions and replacements with line numbers. The model explains which changes deserve attention.

```bash
python3 -m agentkit document-reviewer --demo
python3 -m agentkit document-reviewer --workspace examples --model YOUR_INSTALLED_MODEL \
  --task "Compare terms-before.md and terms-after.md. Explain changed fees, retention, support and archiving rules. Quote the relevant lines from both versions."
```

The supplied example changes a fee from USD 20 to USD 25 and retention from 30 to 90 days. A line-level diff can also flag formatting changes and paragraph moves; it does not distinguish their significance automatically. This is not legal advice or verification of either document's claims. At most 100 changed blocks are returned, with an explicit truncation flag.

Tools: `list_files`, `read_excerpt`, `compare_documents`.
