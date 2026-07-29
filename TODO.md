# Patent Copilot - TODO & Roadmap

## 📌 Near-term Tasks (v0.2 Goals)

- [ ] **1. Live LLM Integration for Evidence Mapping**
  - Extend `src/patent_copilot/core/mapping.py` beyond `PromptOnlyMappingModel`.
  - Implement LLM adapters (Gemini, Anthropic, OpenAI) to perform live claim decomposition and evidence evaluation.

- [ ] **2. Full MCP Client Validation & Integration**
  - Validate setup with Claude Desktop and Cursor.
  - Add explicit integration test suite for stdio MCP transport.

- [ ] **3. Patent Data Source Expansion**
  - Integrate KIPRIS API for Korean patent coverage.
  - Enhance Google Patents scraper fallback resilience and caching.
  - Add EPO / Espacenet connector.

## 🚀 Long-term Roadmap (v1.0 Goals)

- [ ] **4. Multi-Reference Claim Charts**
  - Support combining multiple prior art references (102 vs 103 obviousness mapping).
  - Add confidence scoring for combinations.

- [ ] **5. Interactive Practitioner UX & Export**
  - Support DOCX export for formal patent office filings / office action responses.
  - Web UI for interactive claim chart review and manual evidence editing.

- [ ] **6. CI/CD & Package Distribution**
  - Set up PyPI publishing workflow via GitHub Actions on tagged releases.
