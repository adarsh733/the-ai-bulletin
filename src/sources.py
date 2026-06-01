import hashlib
from datetime import datetime as dt

# Define all RSS sources (Cleaned & Upgraded for v2)
FEEDS = {
    # Official AI Lab Blogs (Primary Sources — highest signal)
    "OpenAI Blog": "https://openai.com/blog/rss.xml",
    "Google DeepMind Blog": "https://deepmind.google/blog/rss.xml",
    "Anthropic Blog": "https://www.anthropic.com/rss.xml",
    "Meta AI Blog": "https://ai.meta.com/blog/rss/",
    "Microsoft AI Blog": "https://blogs.microsoft.com/ai/feed/",
    "NVIDIA AI Blog": "https://blogs.nvidia.com/feed/",
    
    # Community (Pre-filtered by upvotes — much better than raw feeds)
    "Hacker News AI": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+Gemini&points=50",
    "Reddit r/LocalLLaMA": "https://www.reddit.com/r/LocalLLaMA/.rss",
    "Reddit r/MachineLearning": "https://www.reddit.com/r/MachineLearning/.rss",
    "Reddit r/artificial": "https://www.reddit.com/r/artificial/.rss",
    
    # Newsletters & Curated (Already editorially filtered)
    "Import AI (Jack Clark)": "https://importai.substack.com/feed",
    "The Batch (Andrew Ng)": "https://www.deeplearning.ai/the-batch/feed/",
    "TLDR AI": "https://tldr.tech/ai/rss",
    "The Rundown AI": "https://www.therundown.ai/feed",
    
    # Research Aggregators
    "Papers With Code": "https://paperswithcode.com/latest/rss",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "Hugging Face Daily Papers": "https://huggingface.co/papers/rss",
    
    # Tech Press (Secondary Reporting)
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "AI News": "https://www.artificialintelligence-news.com/feed/",
    "The Verge AI": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "Ben's Bites": "https://bensbites.beehiiv.com/feed",
    "Reddit r/ChatGPT": "https://www.reddit.com/r/ChatGPT/.rss",
    "Reddit r/singularity": "https://www.reddit.com/r/singularity/.rss"
}

SOURCE_WEIGHTS = {
    # Tier 1: Primary AI Lab Sources (these ARE the news)
    "OpenAI Blog": 3.0,
    "Google DeepMind Blog": 3.0,
    "Anthropic Blog": 3.0,
    "Meta AI Blog": 2.8,
    "Microsoft AI Blog": 2.5,
    "NVIDIA AI Blog": 2.5,
    
    # Tier 2: Research & Academic
    "ArXiv cs.LG (Machine Learning)": 2.5,
    "ArXiv cs.AI (Artificial Intelligence)": 2.5,
    "Papers With Code": 2.5,
    "Hugging Face Blog": 2.3,
    "Hugging Face Daily Papers": 2.3,
    
    # Tier 3: Developer Community (high signal when upvoted)
    "Reddit r/LocalLLaMA": 2.0,
    "Reddit r/MachineLearning": 2.0,
    "Reddit r/artificial": 1.8,
    "Hacker News AI": 2.2,
    
    # Tier 4: Curated Newsletters (already editorially filtered)
    "Import AI (Jack Clark)": 2.0,
    "The Batch (Andrew Ng)": 2.0,
    "TLDR AI": 1.8,
    "The Rundown AI": 1.8,
    
    # Tier 5: Tech Press (secondary reporting)
    "TechCrunch AI": 1.5,
    "Wired AI": 1.3,
    "Ars Technica": 1.3,
    "MIT Technology Review": 1.5,
    "AI News": 1.5,
    "The Verge AI": 1.5,
    "Ben's Bites": 1.8,
    "Reddit r/ChatGPT": 1.3,
    "Reddit r/singularity": 1.3
}

# Walled network mock fallback tweet / LinkedIn list (X/LinkedIn Radar Feed)
FALLBACK_RADAR_POSTS = [
    {
        'id': hashlib.md5('x_karpathy_1'.encode('utf-8')).hexdigest(),
        'author_handle': '@karpathy',
        'author_name': 'Andrej Karpathy',
        'platform': 'twitter',
        'post_url': 'https://x.com/karpathy/status/1780000000000000000',
        'post_text': 'Building LLMs from scratch is the absolute best way to gain intuition. Do not just import PyTorch and call train, actually write the backprop loops! Understanding standard matrix multiplications deconstructs model scaling laws.',
        'likes': 14200,
        'reposts': 2890,
        'published_at': dt.now().isoformat(),
        'topic_tag': 'LLM Intuition',
        'is_viral': True,
        'linked_article_url': ''
    },
    {
        'id': hashlib.md5('x_sama_1'.encode('utf-8')).hexdigest(),
        'author_handle': '@sama',
        'author_name': 'Sam Altman',
        'platform': 'twitter',
        'post_url': 'https://x.com/sama/status/1780000000000000001',
        'post_text': 'We are scaling compute structures to push frontier agent reasoning benchmarks. The next wave of agentic tools will transition from pure conversational vibe-coding to rigorous sandbox code execution environments.',
        'likes': 9800,
        'reposts': 1240,
        'published_at': dt.now().isoformat(),
        'topic_tag': 'Agent Reasoning',
        'is_viral': True,
        'linked_article_url': ''
    },
    {
        'id': hashlib.md5('linkedin_varun_1'.encode('utf-8')).hexdigest(),
        'author_handle': 'varun-mayya',
        'author_name': 'Varun Mayya',
        'platform': 'linkedin',
        'post_url': 'https://linkedin.com/in/varunmayya',
        'post_text': 'Developers in India are increasingly automating legacy enterprise workflows using n8n and LangGraph multi-agent orchestrations. The developer bottleneck isn\'t syntax writing anymore, it\'s modular system architecture, prompt engineering, and context window routing.',
        'likes': 3450,
        'reposts': 580,
        'published_at': dt.now().isoformat(),
        'topic_tag': 'Workflow Automation',
        'is_viral': True,
        'linked_article_url': ''
    }
]
