---
name: search
description: Web search and page reading
---

## Search

search.web(query, count=5)

Returns a list of search results. Each result contains:
- name — page title
- url — page URL
- snippet — short excerpt
- summary — full summary

Example:
results = search.web("Python asyncio tutorial", count=3)
for r in results:
    print(r["name"], r["url"])

## Read a Web Page

search.read(url, lite=True)

Reads a web page and returns its content as markdown text.
lite=True keeps only readable content (recommended).

Example:
content = search.read("https://docs.python.org/3/library/asyncio.html")
print(content[:500])

## Typical Workflow

1. search.web("keyword") to search
2. Select the most relevant URL from results
3. search.read(url) to fetch the full page
4. Extract the answer from the full text

## Notes

Requires the environment variable API_302AI_KEY. Calls will fail if it is not set.
