# Open Paper Finder

Find an openly available version of a paper through scholarly metadata. It searches OpenAlex and returns the title, year, DOI, open URL, version, license and retraction flag. It does not fetch full text or bypass a publisher's access controls.

```bash
python3 -m agentkit paper-finder --demo
python3 -m agentkit paper-finder --workspace examples --model YOUR_INSTALLED_MODEL --network \
  --task "Find five open-access papers about evaluating tool-using language model agents. Flag retractions and missing licenses."
```

OpenAlex currently permits limited anonymous use and offers a larger free allowance with an account. Optional `OPENALEX_API_KEY` is read from the environment and sent in an authorization header. Requests are fixed to the OpenAlex works endpoint, limited to 10 results each, and timeout after 25 seconds. No paid plan or key is provisioned automatically.

The agent may refine its query after looking at results. A metadata match is a lead, not a literature review. A missing license means unknown reuse rights; an open link is not blanket permission to republish content. Check relevance, publication status and licensing at the source.

Tools: `list_files`, `search_open_papers`, `inspect_paper_snapshot`.
