# 🤖 Pull Request Code Review - Agentic System - CrewAI

An agentic, multi-agent PR code review system powered by **CrewAI** and **Groq**.  
Automatically reviews every Pull Request across all your repos — classifies complexity, runs specialist AI agents, and posts a formal GitHub review (Approve / Request Changes / Escalate).

---

## How It Works

```
Pull Request opened / updated
           ↓
   Fetch PR diff (GitHub CLI)
           ↓
   Complexity classifier (LLM)
      ↙           ↘
  SIMPLE         COMPLEX
  (~15 sec)      (~90 sec)
     ↓               ↓
 Quick LLM     3-Agent Crew
  Review        · Senior Developer
                · Security Engineer
                · Tech Lead
      ↘           ↙
    Final Decision
  APPROVE / REQUEST CHANGES / ESCALATE
           ↓
   Posted as GitHub PR Review
```

---

## Project Structure

```
ai-review-central/
├── .github/
│   └── workflows/
│       └── reusable_ai_review.yml      # Reusable workflow (called by other repos)
├── setup/
│   └── ai_review.yml                   # Caller workflow — copy this into other repos
├── scripts/
│   └── github_review_runner.py         # Bridges GitHub diff → CrewAI flow → GitHub API
├── src/
│   └── code_review_flow/
│       ├── main.py                     # Flow definition & routing logic
│       ├── crews/
│       │   └── code_review_crew/
│       │       ├── crew.py             # Agent + task definitions
│       │       ├── guardrails/
│       │       │   └── guardrails.py   # Output validation
│       │       └── config/
│       │           ├── agents.yaml     # Agent roles & goals
│       │           └── tasks.yaml      # Task definitions
│       └── utils.py
├── app.py                              # Streamlit UI (local use)
└── pyproject.toml
```

---

## Agents

| Agent | Role | Responsibility |
|---|---|---|
| Senior Developer | Code Quality | Logic, architecture, maintainability |
| Security Engineer | Security Analysis | Vulnerabilities, injection risks, secrets |
| Tech Lead | Final Arbiter | Synthesises findings → final decision |

---

## Decision Logic

| Flow Output | GitHub Action | Merge Impact |
|---|---|---|
| `APPROVE` | ✅ Formal approval | PR can be merged |
| `REQUEST CHANGES` | 🔴 Changes requested | Blocks merge |
| `ESCALATE` | ⚠️ Comment only | Human reviewer notified |

---

## What Triggers SIMPLE vs COMPLEX

| Change Type | Path | Why |
|---|---|---|
| README / docs update | SIMPLE | No logic risk |
| Comment / formatting | SIMPLE | Trivial |
| Version bump | SIMPLE | Low risk |
| Auth / login logic | COMPLEX | Security sensitive |
| Database queries | COMPLEX | SQL risk |
| API endpoints | COMPLEX | Business logic |
| File uploads | COMPLEX | Security risk |
| Payment handling | COMPLEX | High stakes |

---

## Requirements

- Python `>=3.10, <3.14`
- [uv](https://docs.astral.sh/uv/) for dependency management
- A [Groq API key](https://console.groq.com)
- This repo must be **Public** (required for reusable workflows on personal GitHub accounts)

---

## Setting Up the Central Repo (First Time)

### 1. Clone and install dependencies

```bash
git clone https://github.com/ankithverma04/PR-review-agentic-system
cd PR-review-agentic-system
pip install uv
uv sync
```

### 2. Set your environment variables

Create a `.env` file in the root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

> ⚠️ Never hardcode API keys in source files. Add `.env` to `.gitignore`.

### 3. Add the secret to GitHub

Go to `PR-review-agentic-system` → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq API key |

### 4. Verify the reusable workflow

Open `.github/workflows/reusable_ai_review.yml` and confirm this line has your username:

```yaml
repository: ankithverma04/PR-review-agentic-system   # ← update this
```

---

## Adding the Review to Another Repo

For each repo you want reviewed, you only need to do **3 things**:

### Step 1 — Copy the caller workflow

Copy `setup/ai_review.yml` into the target repo at:

```
your-other-repo/
└── .github/
    └── workflows/
        └── ai_code_review.yml    ← paste here
```

The file contents: 
Copy the [ai_review.yml](setup/ai_review.yml) into your repo.
  
### Step 2 — Add the secret

In the target repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq API key |

### Step 3 — Commit and push

```bash
git add .github/workflows/ai_code_review.yml
git commit -m "feat: add AI code review"
git push
```

That's it. The next PR in that repo will be reviewed automatically. ✅

---

## Testing the Integration
→ See the full step-by-step [Testing Guide](TESTING.md)
---

## Tech Stack

| Component | Technology |
|---|---|
| Agent framework | [CrewAI](https://crewai.com) |
| LLM provider | [Groq](https://console.groq.com) |
| CI/CD | GitHub Actions (Reusable Workflows) |
| Local UI | Streamlit |
| Dependency management | uv |
| Language | Python 3.11 |


Happy Cooding <3
