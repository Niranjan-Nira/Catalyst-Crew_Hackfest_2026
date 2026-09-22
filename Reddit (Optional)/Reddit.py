import os
import re
import praw
from typing import List, Dict, Optional

# Reddit API Configuration
CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "G-R1_Sr79lRukV7ZZQnMkw")
CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "Xsu_jUWecrLzy8IVK3Mnmzh3I3MHVw")
USER_AGENT = os.getenv("REDDIT_USER_AGENT", "reddit-qa-bot/1.0")

_reddit_client: Optional[praw.Reddit] = None


def get_reddit_client() -> Optional[praw.Reddit]:
    """Initializes and caches the PRAW Reddit client instance."""
    global _reddit_client
    if _reddit_client is None:
        try:
            _reddit_client = praw.Reddit(
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                user_agent=USER_AGENT
            )
            # Read-only verification
            _reddit_client.read_only = True
        except Exception as e:
            print(f"[!] Warning: Could not initialize Reddit client: {e}")
            return None
    return _reddit_client


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by", "can",
    "could", "did", "do", "does", "for", "from", "how", "i", "if", "in", "is",
    "it", "its", "me", "my", "of", "on", "or", "our", "should", "so", "the",
    "their", "them", "there", "they", "this", "to", "up", "us", "we", "what",
    "when", "where", "which", "who", "why", "with", "would", "you", "your", "about"
}

# Targeted tech, sysadmin, and developer subreddits for high-quality solutions
TARGET_SUBREDDITS = "techsupport+sysadmin+windows+PowerShell+learnprogramming+programming+dotnet"


def _normalize_text(text: str) -> List[str]:
    return re.sub(r"[^a-zA-Z0-9_\-\.\s]", " ", text.lower()).split()


def _keyword_tokens(question: str) -> set:
    tokens = set()
    for token in _normalize_text(question):
        token = token.strip(".-_")
        if token and token not in STOPWORDS and len(token) > 1:
            tokens.add(token)
    return tokens


def _question_relevance(question_tokens: set, text: str) -> float:
    if not question_tokens:
        return 0.5

    text_tokens = set(_normalize_text(text))
    if not text_tokens:
        return 0.0

    overlap = len(question_tokens & text_tokens)
    score = overlap / max(len(question_tokens), 1)

    lower_text = text.lower()
    # Bonus for common resolution keywords
    if any(k in lower_text for k in ["fixed", "solved", "solution", "resolution", "workaround", "steps to fix"]):
        score += 0.25

    # Bonus for matching technical tokens like hex codes (0x...) or Event IDs
    for token in question_tokens:
        if token.startswith("0x") or token.isdigit() or len(token) > 6:
            if token in lower_text:
                score += 0.35

    return min(score, 2.0)


def _build_search_queries(question: str) -> List[str]:
    """Generates clean, targeted search queries from the raw question."""
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\.\s]", " ", question).strip()
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return []

    queries = [cleaned]

    # If question starts with 'how to solve' or 'how to fix', create a stripped keyword query
    stripped = re.sub(r"^(how\s+to\s+(solve|fix|repair|resolve)|how\s+do\s+i\s+fix)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    if stripped and stripped.lower() != cleaned.lower():
        queries.append(stripped)

    # Extract high-value keywords (e.g. error codes like 0xC0000005, Event IDs, specific names)
    hex_matches = re.findall(r"0x[0-9a-fA-F]+", cleaned)
    if hex_matches:
        queries.append(f"{hex_matches[0]} fix")
        queries.append(f"{hex_matches[0]} crash solution")

    # Deduplicate while preserving order
    unique_queries = []
    seen = set()
    for q in queries:
        normalized = q.lower().strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_queries.append(q)

    return unique_queries


def search_reddit_qa(question: str, limit: int = 5) -> List[Dict]:
    """
    Search Reddit for troubleshooting threads and verified community solutions
    matching the given technical question or error symptom.
    """
    cleaned_question = question.strip()
    if not cleaned_question:
        return []

    reddit = get_reddit_client()
    if not reddit:
        return []

    q_tokens = _keyword_tokens(cleaned_question)
    search_queries = _build_search_queries(cleaned_question)
    results = []
    seen_urls = set()

    try:
        # 1. Primary search: Targeted technical subreddits
        for query in search_queries:
            if len(results) >= limit * 2:
                break
            try:
                posts = reddit.subreddit(TARGET_SUBREDDITS).search(
                    query,
                    sort="relevance",
                    time_filter="all",
                    limit=max(limit * 2, 8)
                )

                for post in posts:
                    url = f"https://reddit.com{post.permalink}"
                    if url in seen_urls:
                        continue

                    title = post.title or ""
                    body = post.selftext or ""
                    full_text = f"{title} {body}"
                    relevance = _question_relevance(q_tokens, full_text)

                    # Filter out purely zero relevance posts
                    if relevance < 0.1 and len(q_tokens) > 1:
                        continue

                    # Retrieve best community answer
                    best_answer = "No comments available."
                    try:
                        post.comments.replace_more(limit=0)
                        comment_candidates = [
                            c for c in post.comments.list()
                            if hasattr(c, "body") and c.body and len(c.body.strip()) > 10 and not c.body.startswith("[removed]") and not c.body.startswith("[deleted]")
                        ]
                        if comment_candidates:
                            # Prioritize comments with positive score and descriptive text
                            best_comment = max(comment_candidates, key=lambda c: getattr(c, "score", 0))
                            best_answer = best_comment.body.strip()
                    except Exception:
                        pass

                    seen_urls.add(url)
                    results.append({
                        "title": title,
                        "subreddit": f"r/{post.subreddit}",
                        "score": post.score,
                        "url": url,
                        "selftext": body[:600] if body else "",
                        "best_answer": best_answer[:1500],
                        "relevance": round(relevance, 3),
                        "num_comments": post.num_comments if hasattr(post, "num_comments") else 0
                    })
            except Exception as search_err:
                print(f"[!] Subreddit search error for '{query}': {search_err}")

        # 2. Fallback search on r/all if targeted returned insufficient results
        if len(results) < 2 and search_queries:
            try:
                fallback_posts = reddit.subreddit("all").search(
                    search_queries[0],
                    sort="relevance",
                    time_filter="all",
                    limit=limit
                )
                for post in fallback_posts:
                    url = f"https://reddit.com{post.permalink}"
                    if url in seen_urls:
                        continue

                    title = post.title or ""
                    body = post.selftext or ""
                    relevance = _question_relevance(q_tokens, f"{title} {body}")

                    best_answer = "No comments available."
                    try:
                        post.comments.replace_more(limit=0)
                        comment_candidates = [
                            c for c in post.comments.list()
                            if hasattr(c, "body") and c.body and len(c.body.strip()) > 10
                        ]
                        if comment_candidates:
                            best_comment = max(comment_candidates, key=lambda c: getattr(c, "score", 0))
                            best_answer = best_comment.body.strip()
                    except Exception:
                        pass

                    seen_urls.add(url)
                    results.append({
                        "title": title,
                        "subreddit": f"r/{post.subreddit}",
                        "score": post.score,
                        "url": url,
                        "selftext": body[:600] if body else "",
                        "best_answer": best_answer[:1500],
                        "relevance": round(relevance, 3),
                        "num_comments": post.num_comments if hasattr(post, "num_comments") else 0
                    })
                    if len(results) >= limit:
                        break
            except Exception:
                pass

        # Sort results: prioritized by relevance and upvote score
        results.sort(key=lambda item: (-item["relevance"], -item["score"]))
        return results[:limit]

    except Exception as e:
        print(f"[!] Error in search_reddit_qa: {e}")
        return []


def ask_reddit(question: str):
    """CLI tester for search_reddit_qa."""
    print(f"\nQuestion: {question}\n")
    print("=" * 80)

    answers = search_reddit_qa(question, limit=5)

    if not answers:
        print("No matching Reddit discussions found.")
        return

    for i, item in enumerate(answers, start=1):
        print(f"\nResult #{i} (Score: {item['score']}, Relevance: {item['relevance']})")
        print("-" * 80)
        print("Title:", item["title"])
        print("Subreddit:", item["subreddit"])
        print("Post URL:", item["url"])
        print("\nTop Answer / Community Solution:")
        print(item["best_answer"])
        print()


if __name__ == "__main__":
    while True:
        try:
            q = input("\nAsk a troubleshooting question (or 'exit'): ")
            if not q or q.lower() == "exit":
                break
            ask_reddit(q)
        except (KeyboardInterrupt, EOFError):
            break