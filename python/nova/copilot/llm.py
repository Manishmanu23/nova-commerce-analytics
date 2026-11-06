"""LLM providers. The LLM only WRITES prose over retrieved evidence - it never queries data itself."""
import json
import os


def complete(system: str, user: str) -> str | None:
    provider = os.getenv("COPILOT_PROVIDER", "offline").lower()
    try:
        if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
            import anthropic
            client = anthropic.Anthropic()
            msg = client.messages.create(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"), max_tokens=900,
                                         temperature=0, system=system, messages=[{"role": "user", "content": user}])
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        if provider == "ollama":
            import requests
            r = requests.post(os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat"), timeout=120, json=dict(
                model=os.getenv("OLLAMA_MODEL", "llama3.1"), stream=False, options={"temperature": 0},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]))
            return r.json()["message"]["content"]
    except Exception as e:  # provider failure must never break the product - fall back to template
        print(f"[copilot] LLM provider error, falling back to template: {e}")
    return None


def evidence_json(evidence) -> str:
    return json.dumps([dict(id=e.id, tool=e.tool, args=e.args, display=e.display, data=e.data) for e in evidence],
                      default=str, indent=1)[:12000]
