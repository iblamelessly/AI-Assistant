import re
from typing import Tuple, List, Dict, Any

class SuperAIRouter:
    """
    Intelligent Model Router & Mixture of Models Orchestrator.
    Analyzes prompt intent, complexity, and domain to automatically route queries
    to the optimal AI model, with seamless cascade fallback on rate limits.
    """

    # Model specifications and specialist roles
    MODELS = {
        "gpt-oss-120b": {
            "id": "openai/gpt-oss-120b",
            "name": "OpenAI GPT-OSS 120B",
            "role": "Deep Reasoning & Architecture",
            "description": "Massive 120B frontier model for complex logic, multi-step planning, creative writing, and deep analysis."
        },
        "qwen-coder": {
            "id": "qwen/qwen3.8-27b",
            "name": "Qwen 3.8 27B",
            "role": "Code & Technical Specialist",
            "description": "27B high-precision coder for software engineering, algorithms, terminal commands, and debugging."
        },
        "gpt-oss-20b": {
            "id": "openai/gpt-oss-20b",
            "name": "OpenAI GPT-OSS 20B",
            "role": "Ultra-Fast Conversational",
            "description": "Low-latency 20B model for rapid chit-chat, quick Q&A, and everyday interaction."
        },
        "allam": {
            "id": "allam-2-7b",
            "name": "Allam 2 7B",
            "role": "Multilingual Specialist",
            "description": "Specialized Arabic & cultural knowledge model."
        }
    }

    # Code and technical keywords
    CODE_KEYWORDS = [
        "code", "python", "javascript", "typescript", "html", "css", "c++", "java", "rust", "golang",
        "powershell", "bash", "terminal", "script", "function", "class", "def ", "async ", "import ",
        "regex", "algorithm", "debug", "refactor", "bug", "syntax", "sql", "query", "database",
        "api", "json", "git ", "github", "docker", "pip ", "npm ", "node", "react", "vue",
        "fix error", "stack trace", "exception", "compile", "execute", "unit test", "pptx", "docx"
    ]

    # Deep reasoning and analysis keywords
    REASONING_KEYWORDS = [
        "explain in detail", "analyze", "compare", "contrast", "why does", "how does", "philosophy",
        "architecture", "tradeoffs", "pros and cons", "evaluate", "synthesize", "essay", "critique",
        "derive", "mathematical proof", "solve step by step", "complex", "strategy", "roadmap",
        "business plan", "research paper", "comprehensive guide", "breakdown"
    ]

    # Fast conversational indicators (greetings, quick confirmation, voice checks)
    FAST_CONVERSATIONAL_KEYWORDS = [
        "hi", "hello", "hey", "good morning", "good evening", "good afternoon", "how are you",
        "who are you", "what is your name", "what time is it", "tell me a joke", "thanks", "thank you",
        "bye", "goodbye", "cool", "awesome", "yes", "no", "ok", "okay", "sure", "can you hear me"
    ]

    @classmethod
    def classify_prompt(cls, prompt: str, attachments: list = None) -> Tuple[str, str]:
        """
        Classifies prompt intent and returns (model_id, reason).
        """
        if not prompt:
            return cls.MODELS["gpt-oss-20b"]["id"], "Default conversational"

        text = prompt.strip()
        lower = text.lower()
        word_count = len(text.split())

        # Check for explicit code markers (fenced code blocks, indentation, file extensions)
        if "```" in text or "`" in text or "{" in text and "}" in text or "<html" in lower or "<script" in lower:
            return cls.MODELS["qwen-coder"]["id"], "Code syntax detected"

        # Check for coding keywords
        if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in cls.CODE_KEYWORDS):
            return cls.MODELS["qwen-coder"]["id"], "Software engineering query"

        # Check for short chit-chat / quick questions (< 10 words and conversational match)
        if word_count <= 8 and any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in cls.FAST_CONVERSATIONAL_KEYWORDS):
            return cls.MODELS["gpt-oss-20b"]["id"], "Fast conversational"

        # Check for deep reasoning / analysis
        if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in cls.REASONING_KEYWORDS):
            return cls.MODELS["gpt-oss-120b"]["id"], "Deep reasoning & analysis"

        # If length is long (> 35 words) or multi-paragraph -> 120B model for deep synthesis
        if word_count > 35 or "\n\n" in text:
            return cls.MODELS["gpt-oss-120b"]["id"], "Complex multi-step instruction"

        # Medium length general questions default to 120B for superior intellectual responses
        return cls.MODELS["gpt-oss-120b"]["id"], "Intellectual reasoning engine"

    @classmethod
    def get_fallback_chain(cls, primary_model_id: str) -> List[str]:
        """
        Returns an ordered cascade list of models to try if the primary encounters rate limits (429) or errors.
        """
        all_ids = [
            cls.MODELS["gpt-oss-120b"]["id"],
            cls.MODELS["qwen-coder"]["id"],
            cls.MODELS["gpt-oss-20b"]["id"],
            cls.MODELS["allam"]["id"]
        ]

        chain = [primary_model_id]
        for m in all_ids:
            if m not in chain:
                chain.append(m)
        return chain

    @classmethod
    def get_friendly_name(cls, model_id: str) -> str:
        for m in cls.MODELS.values():
            if m["id"] == model_id:
                return f"{m['name']} ({m['role']})"
        return model_id
