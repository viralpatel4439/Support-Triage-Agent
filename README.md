# Support Triage Agent

An intelligent AI agent that automatically triages and responds to customer support tickets from multiple companies (Claude, HackerRank, and Visa) using semantic search and a two-stage agent pipeline.

## Features

- **Intelligent Triage** — Automatically classifies tickets by product area, request type, and urgency
- **Semantic Search** — Uses local embeddings to find relevant support documentation
- **Two-Agent Pipeline** — Classifier + Retriever agent followed by Responder agent
- **Parallel Processing** — Handles multiple tickets concurrently with configurable concurrency limits
- **Local-First** — No external API calls for document retrieval; works entirely with local support corpus
- **Escalation Support** — Intelligently escalates high-risk, sensitive, or unsupported cases

## Quick Start

```bash
# Clone the repository
git clone https://github.com/viralpatel4439/Support-Triage-Agent.git
cd Support-Triage-Agent

# Navigate to the code directory
cd code

# Install dependencies and set up
python3 embed_corpus.py  # First-time only

# Run the agent
python3 main.py
```

## Output

The agent processes tickets from `support_tickets/support_tickets.csv` and generates predictions in `support_tickets/output.csv` with:

- **status** — `replied` or `escalated`
- **product_area** — Relevant support category
- **response** — Grounded answer or escalation reason
- **request_type** — `product_issue`, `feature_request`, `bug`, or `invalid`
- **justification** — Explanation of routing/answering decision

## Architecture

The system uses a sophisticated two-agent architecture:

1. **Classifier + Retriever Agent** — Analyzes the ticket and searches for relevant support documentation using semantic similarity
2. **Responder Agent** — Generates a response based on retrieved documents or escalates if needed

Each ticket operates independently with per-ticket tool call limits to ensure controlled and reliable processing.

## Configuration

Control parallel processing with the `BATCH_CONCURRENCY` environment variable:

```bash
# Sequential processing (safest)
BATCH_CONCURRENCY=1 python3 main.py

# Parallel processing (faster, default is 2)
BATCH_CONCURRENCY=3 python3 main.py
```

## Project Structure

```
.
├── README.md                    # This file
├── code/                        # Main implementation
│   ├── main.py                  # Entry point
│   ├── embed_corpus.py          # Setup embeddings
│   ├── models/                  # Data models
│   ├── tools/                   # Tool implementations
│   ├── agents/                  # Agent implementations
│   ├── embeddings/              # Vector database
│   ├── observability/           # Logging & monitoring
│   └── README.md                # Detailed documentation
├── data/                        # Support corpus
│   ├── claude/                  # Claude help documentation
│   ├── hackerrank/              # HackerRank help documentation
│   └── visa/                    # Visa support documentation
└── support_tickets/             # Test data
    ├── support_tickets.csv      # Input tickets
    └── output.csv               # Agent predictions
```

## Documentation

For detailed setup instructions, configuration options, architecture details, and troubleshooting, see [`code/README.md`](./code/README.md).

## License

MIT
