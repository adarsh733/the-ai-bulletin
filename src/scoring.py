import html
import re
import hashlib
from urllib.parse import urlparse
import random
from sources import SOURCE_WEIGHTS

def normalize_twitter_url(raw_url, handle):
    """
    Normalize any Twitter/X URL to canonical x.com format.
    Returns profile URL as fallback if specific post URL can't be extracted.
    """
    if not raw_url:
        return f"https://x.com/{handle.lstrip('@')}"
    
    # Extract status ID if present anywhere in the URL
    status_match = re.search(r'/status/(\d+)', raw_url)
    if status_match:
        status_id = status_match.group(1)
        clean_handle = handle.lstrip('@')
        return f"https://x.com/{clean_handle}/status/{status_id}"
    
    # Fallback to profile
    return f"https://x.com/{handle.lstrip('@')}"

def is_valid_post_url(url):
    """Check if a URL points to a specific post (not just a homepage or profile root)."""
    if not url or len(url) < 20:
        return False
    
    parsed = urlparse(url)
    
    # Reject bare domain URLs
    if not parsed.path or parsed.path in ('', '/', '/feed'):
        return False
    
    return True

def clean_reddit_summary(text):
    """
    Strip Reddit RSS metadata artifacts from article summaries.
    Safe to run on ALL sources — only removes patterns that shouldn't exist in clean text.
    """
    if not text:
        return text
    
    # Decode HTML entities (&#32; → space, &amp; → &, etc.)
    text = html.unescape(text)
    
    # Strip "submitted by /u/username [link] [comments]"
    text = re.sub(r'\s*submitted by\s+/u/\S+\s*\[link\]\s*\[comments?\]\s*', '', text, flags=re.IGNORECASE)
    
    # Strip standalone "[link]" and "[comments]" leftovers
    text = re.sub(r'\s*\[link\]\s*', ' ', text)
    text = re.sub(r'\s*\[comments?\]\s*', '', text)
    
    # Strip Reddit-style score lines: "· X points · Y comments"
    text = re.sub(r'·\s*\d+\s*points?\s*·?\s*\d*\s*comments?', '', text, flags=re.IGNORECASE)
    
    # Strip residual HTML tags that survived feedparser
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up extra whitespace
    text = re.sub(r'\s{2,}', ' ', text).strip()
    
    return text

def clean_html(raw_html):
    """Clean up HTML tags to return plain text summary."""
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    # Remove excessive whitespaces
    cleantext = re.sub(r'\s+', ' ', cleantext).strip()
    return cleantext[:600] + ("..." if len(cleantext) > 600 else "")

def extract_image(entry, raw_html):
    """Robustly extract image URL from feed entry tags or description HTML."""
    media_content = getattr(entry, 'media_content', [])
    if media_content and isinstance(media_content, list):
        for mc in media_content:
            if isinstance(mc, dict) and mc.get('url'):
                return mc['url']
                
    enclosures = getattr(entry, 'enclosures', [])
    if enclosures and isinstance(enclosures, list):
        for enc in enclosures:
            if isinstance(enc, dict) and enc.get('type', '').startswith('image/') and enc.get('href'):
                return enc['href']
                
    if raw_html:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html)
        if match:
            url = match.group(1)
            if "feedburner" not in url and "analytics" not in url and "tracker" not in url:
                return url
                
    return ""

def generate_id(url):
    """Generate MD5 hash of URL as primary key."""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def clean_headline(title):
    """Strip RSS bloat from article titles. No LLM needed."""
    if not title:
        return title
    
    # Remove trailing source attributions: "| VentureBeat", "— by MIT", "- TechCrunch"
    # Only strip if the part after the separator is 10+ chars (to avoid cutting real content)
    title = re.sub(r'\s*[|—–]\s+[\w][\w\s,\.]{9,}$', '', title).strip()
    
    # Remove paper-style prefix brackets: "[D]", "[P]", "[N]", "[R]"
    title = re.sub(r'^\[[A-Z]\]\s*', '', title).strip()
    
    # Remove ellipsis artifacts from truncated RSS titles
    title = re.sub(r'\s*\.{3}\s*', ' ', title).strip()
    title = re.sub(r'\s*…\s*', ' ', title).strip()
    
    # Remove clickbait lead prefixes
    title = re.sub(r'^(Exclusive:|Breaking:|Report:|Just In:|Update:)\s*', '', title, flags=re.IGNORECASE).strip()
    
    # Collapse multiple spaces
    title = re.sub(r'\s{2,}', ' ', title).strip()
    
    return title

import random

def generate_hook(article):
    """Generate a specific 4-8 word editorial hook for this article."""
    title = (article.get('title') or '').lower()
    summary = (article.get('summary') or '').lower()
    text = f"{title} {summary}"
    
    # === TIER 1: Extract specific facts (highest priority) ===
    
    # Funding / valuation amount
    funding = re.search(r'\$(\d+(?:\.\d+)?)\s*(billion|million|b|m|bn|mn)\b', text, re.IGNORECASE)
    if funding:
        amt = funding.group(1)
        unit = 'B' if funding.group(2).lower() in ['billion', 'b', 'bn'] else 'M'
        # Determine if it's a spending/cost story vs funding story
        if any(w in text for w in ['cost', 'bill', 'spent', 'burn', 'accidentally', 'forgot', 'mistake']):
            return f"Accidental ${amt}{unit} bill"
        elif any(w in text for w in ['valuation', 'valued', 'worth', 'overtake', 'surpass']):
            return f"Valuation upset"
        elif any(w in text for w in ['acquisition', 'acquire', 'acqui-hire', 'not-acquisition']):
            return f"${amt}{unit} acquisition play"
        else:
            return f"${amt}{unit} bet placed on this"
    
    # Percentage / benchmark result
    pct = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(faster|better|improvement|increase|reduction|accuracy|below|above|of)', text, re.IGNORECASE)
    if pct:
        return f"{pct.group(1)}% {pct.group(2)} — benchmark shift"
    
    # User/scale numbers
    users = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(users|customers|developers|companies|patients|hospitals|schools|cases|diseases)', text, re.IGNORECASE)
    if users:
        return f"{users.group(1)} {users.group(2)} affected"
    
    # === TIER 2: Domain-specific hooks (high priority) ===
    
    # Valuation / market cap shifts
    if re.search(r'\b(valuation|most valuable|overtake|surpass|market cap|billion.dollar)\b', text):
        return "Valuation upset"
    
    # Healthcare / medical deployment
    if re.search(r'\b(hospital|patient|diagnosis|clinical|healthcare|medical|disease|rare disease)\b', text):
        return "Real-world deployment"
    
    # Robotics crossing thresholds
    if re.search(r'\b(robot|autonomous|humanoid|simulation.to.real|sim.to.real|embodied)\b', text):
        return "Robotics crosses a threshold"
    
    # Infrastructure / web changing
    if re.search(r'\b(infrastructure|cloud|aws|azure|gcp|cloudflare|cdn|api.layer|machine.readable)\b', text):
        return "The web is changing shape"
    
    # Enterprise adoption / all-in moves
    if re.search(r'\b(entire (bank|company|org)|rebuild|rewriting|all.in on|enterprise.wide)\b', text):
        return "Enterprise all-in"
    
    # Governance / policy / safety
    if re.search(r'\b(regulation|governance|safety|blueprint|scaling.*safe|policy|compliance|eu act|executive order)\b', text):
        return "Governance gets serious"
    
    # Open source / weights released
    if re.search(r'\b(open.source|open.weights|weights.released|publicly available|apache|mit license)\b', text):
        return "Open weights"
    
    # Cost / billing / spending accidents
    if re.search(r'\b(cost|bill|billing|spending|burn rate|accidentally|forgot|guardrail|limit)\b', text):
        return "Cost guardrails matter"
    
    # Acquisition / power moves
    if re.search(r'\b(acqui|merger|bought|takeover|not.acquisition|acqui.hire)\b', text):
        return "Consolidation move"
    
    # Chip / hardware power shifts
    if re.search(r'\b(chip|gpu|tpu|nvidia|amd|intel|silicon|semiconductor|hardware)\b', text):
        return "Chip power shift"
    
    # Agent / autonomous systems
    if re.search(r'\b(autonomous|agentic|agent|multi.agent|swarm|orchestrat)\b', text):
        return "Agents stepping into real work"
    
    # Speed / performance
    if re.search(r'\b(faster|speed|latency|real.time|edge|lightweight|efficient|small model|fits on)\b', text):
        return "Smaller, faster, local"
    
    # Music / creative
    if re.search(r'\b(music|song|audio|creative|art|image|video|diffusion|generation)\b', text):
        return "Creative AI frontier"
    
    # === TIER 3: Section-based fallback with rotation ===
    section = article.get('section', 'signals')
    fallbacks = {
        'money_moves': [
            "Follow the money",
            "Capital is moving",
            "Power shift underway",
            "Strategic bet",
            "Market signal",
        ],
        'signals': [
            "Worth watching",
            "Signal emerging",
            "Pattern forming",
            "Shift underway",
            "Developing story",
        ],
        'from_the_lab': [
            "Fresh from the lab",
            "Research that matters",
            "Lab to production pipeline",
            "New capability unlocked",
            "Science meets engineering",
        ],
        'builders_bench': [
            "Builders are shipping",
            "Community momentum",
            "Open source energy",
            "Dev tooling evolves",
            "Shipped and usable",
        ],
        'deployed': [
            "Real-world deployment",
            "In production now",
            "Adoption milestone",
            "Live in the field",
            "Beyond the prototype",
        ],
    }
    options = fallbacks.get(section, ["Notable development"])
    return random.choice(options)

def select_final_articles(articles):
    """Apply quality filters and hard cap to article list."""
    
    # Filter: Require summary to be at least 80 chars (skip link-only previews)
    articles = [a for a in articles if len(a.get('summary') or '') >= 80]
    
    # Deduplicate: Same story from multiple sources — keep highest scored
    seen = {}
    deduped = []
    for art in sorted(articles, key=lambda x: x.get('final_score', 0), reverse=True):
        fingerprint = ' '.join((art.get('title') or '').lower().split()[:6])
        if fingerprint not in seen:
            seen[fingerprint] = True
            deduped.append(art)
    articles = deduped
    
    # Hard cap: Top 20 by score
    articles = sorted(articles, key=lambda x: x.get('final_score', 0), reverse=True)[:20]
    
    return articles

def calculate_jaccard_similarity(title1, title2):
    """Calculate Jaccard similarity of two titles based on words sets."""
    words1 = set(re.findall(r'\w+', title1.lower()))
    words2 = set(re.findall(r'\w+', title2.lower()))
    if not words1 or not words2:
        return 0.0
    return len(words1.intersection(words2)) / len(words1.union(words2))

def is_wild_use_case(title, summary, source):
    """
    Detect articles about creative, real-world, unexpected AI use cases.
    These are stories about HOW people/orgs are using AI — not product launches or papers.
    """
    text = f"{title} {summary}".lower()
    
    # Must describe someone USING AI (not building or selling it)
    usage_signals = [
        'using ai', 'uses ai', 'used ai', 'using chatgpt', 'using claude',
        'using gpt', 'using llm', 'built with ai', 'powered by ai',
        'ai-powered', 'ai helped', 'ai to help', 'ai to detect',
        'ai to diagnose', 'ai to predict', 'ai to automate',
        'automated with', 'replaced with ai', 'saved hours',
        'saves time', 'reduced cost', 'how i use', 'how we use',
        'my experience with', 'workflow with ai', 'ai workflow',
        'real-world', 'in practice', 'case study', 'use case',
        'deployed ai', 'implemented ai', 'adopted ai',
    ]
    
    # Must involve a real actor/domain (not just a tech company)
    domain_signals = [
        'hospital', 'clinic', 'patient', 'doctor', 'nurse',
        'school', 'teacher', 'student', 'university', 'classroom',
        'restaurant', 'chef', 'kitchen', 'farm', 'farmer',
        'factory', 'manufacturing', 'warehouse', 'logistics',
        'law firm', 'lawyer', 'legal', 'attorney',
        'bank', 'insurance', 'finance', 'accounting',
        'retail', 'store', 'e-commerce', 'shopping',
        'government', 'city', 'police', 'military',
        'freelancer', 'solopreneur', 'small business', 'startup',
        'artist', 'musician', 'filmmaker', 'designer', 'writer',
        'children', 'parents', 'family', 'elderly',
    ]
    
    # Must NOT be primarily a product launch or funding news
    exclude_signals = [
        'raises $', 'funding round', 'series a', 'series b', 'series c',
        'valuation', 'ipo', 'acquisition',
    ]
    
    has_usage = any(s in text for s in usage_signals)
    has_domain = any(s in text for s in domain_signals)
    is_excluded = any(s in text for s in exclude_signals)
    
    # Also flag posts from r/ChatGPT that describe personal usage
    is_reddit_usage = ('reddit' in source.lower() and 
                       any(s in text for s in ['i use', 'i built', 'my workflow', 'how i', 'my experience']))
    
    return (has_usage and has_domain and not is_excluded) or is_reddit_usage

def classify_story_type(title, summary, section):
    """Classify what TYPE of story this is."""
    text = f"{title} {summary}".lower()
    
    if re.search(r'\braises?\s+\$|\bfunding\b|\bseries [a-d]\b|\bvaluation\b', text):
        return 'funding'
    if re.search(r'\breleases?\b|\blaunches?\b|\bships?\b|\bannounces?\b|\bavailable\b', text):
        return 'release'
    if re.search(r'\bpaper\b|\bstudy\b|\bbenchmark\b|\bresearch\b|\barxiv\b', text):
        return 'paper'
    if re.search(r'\bhow to\b|\btutorial\b|\bguide\b|\bwalkthrough\b|\bstep.by.step\b', text):
        return 'howto'
    if re.search(r'\buse[sd]?\s+ai\b|\bdeployed?\b|\badopt\b|\bin production\b', text):
        return 'usecase'
    if re.search(r'\bregulat\b|\bpolicy\b|\bban\b|\blaw\b|\bgovernment\b', text):
        return 'policy'
    if re.search(r'\b\d+%\b|\b\d+x\b|\bmetric\b|\bbenchmark\b|\bstat\b', text):
        return 'data'
    
    return 'news'

STORY_TYPE_LABELS = {
    'funding': '💰 Funding',
    'release': '🚀 New Release',
    'paper': '📄 Research',
    'howto': '⚙️ How To',
    'usecase': '🌱 Use Case',
    'policy': '⚖️ Policy',
    'data': '📈 Data',
    'news': '📰 News',
}

# Editorial column display names — mapped from internal section codes
# The front page has 3 columns: The Big Picture, Built & Shipped, The Shift
SECTION_DISPLAY_NAMES = {
    'money_moves':    'The Big Picture',
    'signals':        'The Big Picture',
    'from_the_lab':   'Built & Shipped',
    'builders_bench': 'Built & Shipped',
    'deployed':       'Built & Shipped',
    'wild':           'AI In The Wild',
}
# Default fallback for any unmapped section: 'The Shift'

def assign_section(title, summary, source):
    """Assign article to a newspaper section."""
    text = f"{title} {summary}".lower()
    src = source.lower()
    
    # Rule 0: Wild use case check (highest priority)
    if is_wild_use_case(title, summary, source):
        return "wild"
    
    if any(s in src for s in ['arxiv', 'papers with code', 'hugging face daily']):
        return "from_the_lab"
    
    if any(s in src for s in ['reddit', 'hacker news']):
        if any(w in text for w in ['built', 'shipped', 'released', 'my experience',
                                    'tutorial', 'how i', 'open-source', 'github',
                                    'fine-tun', 'quantiz', 'deploy', 'self-host']):
            return "builders_bench"
        return "signals"
    
    if any(w in text for w in ['raises', 'funding', 'valuation', 'series a', 'series b',
                                'series c', 'series d', 'acquisition', 'acquires', 'ipo',
                                'investment', 'investors', 'venture capital', 'market cap']):
        return "money_moves"
    
    if any(w in text for w in ['deploys', 'deployed', 'production', 'enterprise', 
                                'hospital', 'patients', 'customers', 'revenue',
                                'saves hours', 'reduces cost', 'automates',
                                'case study', 'implementation']):
        return "deployed"
    
    if any(w in text for w in ['paper', 'benchmark', 'evaluation', 'architecture',
                                'pre-train', 'dataset', 'ablation', 'parameters',
                                'weights', 'attention mechanism', 'scaling law']):
        return "from_the_lab"
    
    if any(w in text for w in ['open-source', 'github', 'released', 'framework',
                                'library', 'tool', 'sdk', 'api', 'developer']):
        return "builders_bench"
    
    return "signals"

def assign_industry(text):
    """Tag article with industry vertical."""
    if any(k in text for k in ['health', 'medical', 'clinical', 'patient', 'drug',
                                'biotech', 'hospital', 'physician', 'diagnosis']):
        return "Healthcare"
    if any(k in text for k in ['legal', 'lawyer', 'contract', 'compliance', 'court']):
        return "Legal"
    if any(k in text for k in ['finance', 'trading', 'banking', 'fintech', 'portfolio']):
        return "Finance"
    if any(k in text for k in ['code', 'developer', 'ide', 'programming', 'software',
                                'coding', 'engineering', 'devops']):
        return "Developer Tools"
    if any(k in text for k in ['education', 'student', 'learning', 'school', 'university']):
        return "Education"
    if any(k in text for k in ['security', 'cyber', 'threat', 'vulnerability', 'privacy']):
        return "Security"
    if any(k in text for k in ['robot', 'autonomous', 'self-driving', 'drone', 'hardware']):
        return "Robotics & Hardware"
    if any(k in text for k in ['creative', 'art', 'music', 'video', 'image generation',
                                'diffusion', 'midjourney', 'dall-e', 'sora']):
        return "Creative AI"
    return "General AI"

def score_article(title, summary, source):
    """Calculate relevance score with hype penalty, and assign section."""
    text = f"{title} {summary}".lower()
    
    ai_core_terms = [
        'ai', 'artificial intelligence', 'machine learning', 'deep learning',
        'llm', 'large language model', 'neural network', 'transformer',
        'gpt', 'claude', 'gemini', 'llama', 'mistral', 'diffusion',
        'training', 'inference', 'fine-tun', 'prompt', 'rag', 'agent',
        'reasoning', 'benchmark', 'model', 'parameter', 'token',
        'embedding', 'attention', 'reinforcement learning', 'robotics'
    ]
    
    primary_sources = [
        'ArXiv', 'OpenAI', 'DeepMind', 'Anthropic', 'Hugging Face', 
        'Meta AI', 'NVIDIA AI', 'Microsoft AI', 'Papers With Code',
        'Import AI', 'The Batch', 'TLDR AI', 'The Rundown AI', 'AI News'
    ]
    is_primary = any(s.lower() in source.lower() for s in primary_sources)
    ai_signal_count = sum(1 for t in ai_core_terms if t in text)
    
    if not is_primary and ai_signal_count < 2:
        return 0.5, 0.0, "ticker", "General"
    
    base = SOURCE_WEIGHTS.get(source, 1.0)
    
    if re.search(r'\$[\d,.]+\s*[BMKbmk]', text):
        base += 0.8  
    if re.search(r'\d+%', text):
        base += 0.5  
    if re.search(r'\d+x\b', text):
        base += 0.5  
    
    novelty_signals = ['launches', 'introduces', 'announces', 'releases', 'unveils',
                       'open-source', 'now available', 'breaking', 'just released']
    if any(s in text for s in novelty_signals):
        base += 1.0
    
    impact_signals = ['breakthrough', 'state-of-the-art', 'sota', 'outperforms',
                      'surpasses', 'first-ever', 'record', 'billion', 'million users']
    impact_count = sum(1 for s in impact_signals if s in text)
    base += min(impact_count * 0.5, 1.5)  
    
    hype_words = [
        'revolutionary', 'game.changer', 'mind.blowing', 'shocking', 'insane',
        'unbelievable', 'destroy', 'killer', 'magic', 'infinite', 'unprecedented',
        'world.changing', '🚀', '🔥', 'you won.t believe', 'everything changes',
        'next.gen', 'paradigm shift'
    ]
    hype_hits = sum(1 for h in hype_words if re.search(h, text))
    hype_penalty = min(hype_hits * 0.8, 3.0)  
    
    final_score = max(round(base - hype_penalty, 2), 0.5)
    final_score = min(final_score, 10.0)  
    
    section = assign_section(title, summary, source)
    industry = assign_industry(text)
    
    return final_score, round(hype_penalty, 2), section, industry

