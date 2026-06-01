import sys
import os
import re
import json
import hashlib
import urllib.request
import ssl
import certifi
import datetime
from datetime import datetime as dt
import feedparser
import duckdb

from sources import FEEDS, FALLBACK_RADAR_POSTS
from scoring import *

def parse_date(entry):
    """Parse date from feed entry fallback gracefully."""
    published_parsed = getattr(entry, 'published_parsed', None)
    if published_parsed:
        try:
            return dt(*published_parsed[:6])
        except:
            pass
    
    for field in ['published', 'updated', 'created']:
        val = getattr(entry, field, None)
        if val:
            try:
                for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return dt.strptime(val, fmt)
                    except ValueError:
                        continue
            except:
                pass
                
    return dt.now()

def fetch_feed(name, url, limit=10):
    """Fetch feed content with parallel execution and stream results."""
    import time
    start_time = time.time()
    print(json.dumps({"status_update": {"source": name, "status": "fetching"}}), file=sys.stderr)
    sys.stderr.flush()
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                'Accept-Language': 'en-US,en;q=0.9'
            }
        )
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            feed_data = feedparser.parse(response.read())
        
        if not feed_data.entries:
            elapsed = time.time() - start_time
            print(json.dumps({"status_update": {"source": name, "status": "success", "duration": round(elapsed, 2), "count": 0}}), file=sys.stderr)
            sys.stderr.flush()
            return []
        
        articles = []
        for entry in feed_data.entries[:limit]:
            title = getattr(entry, 'title', 'No Title')
            link = getattr(entry, 'link', '')
            if not link:
                continue
            
            if len(title.strip()) < 10:
                continue
            
            summary_html = getattr(entry, 'summary', '')
            if not summary_html and hasattr(entry, 'description'):
                summary_html = entry.description
            summary = clean_html(summary_html)
            
            if not summary or len(summary.strip()) < 20:
                summary = title  
            
            summary = clean_reddit_summary(summary)
            
            image_url = extract_image(entry, summary_html)
            published_at = parse_date(entry)
            
            # Re-write and clean RSS title attributions
            clean_title = clean_headline(title)
            
            final_score, hype_penalty, section, industry = score_article(clean_title, summary, name)
            
            if final_score <= 0.5:
                continue
            
            story_type = classify_story_type(clean_title, summary, section)
            story_type_label = STORY_TYPE_LABELS.get(story_type, '📰 News')
            
            art_dict = {
                'id': generate_id(link),
                'source': name,
                'title': clean_title,
                'url': link,
                'published_at': published_at.isoformat(),
                'summary': summary,
                'content': '',
                'final_score': final_score,
                'hype_penalty': hype_penalty,
                'section': section,
                'section_display_name': SECTION_DISPLAY_NAMES.get(section, 'The Shift'),
                'industry': industry,
                'image_url': image_url,
                'hook': '',
                'story_type': story_type,
                'story_type_label': story_type_label
            }
            art_dict['hook'] = generate_hook(art_dict)
            
            # Incremental load stream - print to stderr to avoid stdout pollution
            print(json.dumps({"article": art_dict}), file=sys.stderr)
            sys.stderr.flush()
            
            articles.append(art_dict)
        
        elapsed = time.time() - start_time
        print(json.dumps({"status_update": {"source": name, "status": "success", "duration": round(elapsed, 2), "count": len(articles)}}), file=sys.stderr)
        sys.stderr.flush()
        return articles
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(json.dumps({"status_update": {"source": name, "status": "error", "duration": round(elapsed, 2), "error": str(e)}}), file=sys.stderr)
        sys.stderr.flush()
        return []

def fetch_single_subreddit(sub):
    """Fetch top posts from a single subreddit and emit status."""
    import time
    start_time = time.time()
    name = f"Reddit r/{sub}"
    print(json.dumps({"status_update": {"source": name, "status": "fetching"}}))
    sys.stdout.flush()
    
    posts = []
    headers = {'User-Agent': 'AIBulletin/1.0 (news aggregator)'}
    try:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=5"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        for child in data.get('data', {}).get('children', []):
            post = child.get('data', {})
            
            # Skip stickied mod posts
            if post.get('stickied'):
                continue
            
            ups = post.get('ups', 0)
            # Skip low-engagement posts
            if ups < 20:
                continue
            
            selftext = (post.get('selftext') or '')[:300]
            title = post.get('title', '')
            
            permalink = post.get('permalink', '')
            if not permalink.startswith('/'):
                permalink = '/' + permalink

            post_url = f"https://www.reddit.com{permalink}"

            # Separate the external article link (for link posts, not self posts)
            external_url = post.get('url', '')
            if external_url.startswith('https://www.reddit.com') or external_url.startswith('https://reddit.com'):
                linked_article_url = ''  # It's a self post — no external link
            else:
                linked_article_url = external_url

            post_obj = {
                'id': f"reddit_{post.get('id', '')}",
                'author_handle': f"r/{sub}",
                'author_name': post.get('author', 'Anonymous'),
                'platform': 'reddit',
                'post_url': post_url,
                'post_text': title + (' — ' + selftext if selftext else ''),
                'likes': ups,
                'reposts': post.get('num_comments', 0),
                'published_at': datetime.datetime.fromtimestamp(
                    post.get('created_utc', 0), tz=datetime.timezone.utc
                ).isoformat(),
                'topic_tag': sub,
                'is_viral': ups > 100,
                'linked_article_url': linked_article_url,
                'thumbnail': '',
                'url_is_profile': False
            }

            # URL Validation Gate
            if not is_valid_post_url(post_obj['post_url']):
                post_obj['post_url'] = f"https://www.reddit.com/r/{sub}"
                post_obj['url_is_profile'] = True

            # Emit live individual radar post to stderr
            print(json.dumps({"radar_post": post_obj}), file=sys.stderr)
            sys.stderr.flush()

            posts.append(post_obj)
            
        elapsed = time.time() - start_time
        print(json.dumps({"status_update": {"source": name, "status": "success", "duration": round(elapsed, 2), "count": len(posts)}}), file=sys.stderr)
        sys.stderr.flush()
        return posts
    except Exception as e:
        elapsed = time.time() - start_time
        print(json.dumps({"status_update": {"source": name, "status": "error", "duration": round(elapsed, 2), "error": str(e)}}), file=sys.stderr)
        sys.stderr.flush()
        return []

def fetch_single_youtube(name, channel_id):
    """Fetch latest AI videos from a single YouTube channel via public RSS."""
    import time
    start_time = time.time()
    source_name = f"YouTube {name}"
    print(json.dumps({"status_update": {"source": source_name, "status": "fetching"}}), file=sys.stderr)
    sys.stderr.flush()
    
    posts = []
    try:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        req = urllib.request.Request(url, headers={'User-Agent': 'AIBulletin/1.0'})
        with urllib.request.urlopen(req, timeout=4) as response:
            feed = feedparser.parse(response.read())
        
        for entry in feed.entries[:2]:  # Latest 2 per channel
            video_id = entry.get('yt_videoid', '')
            
            # Build canonical URL from video ID
            if video_id:
                post_url = f"https://www.youtube.com/watch?v={video_id}"
                thumbnail = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
            else:
                post_url = entry.get('link', '')
                thumbnail = ''
            
            post_obj = {
                'id': f"yt_{video_id}",
                'author_handle': f"@{name.replace(' ', '')}",
                'author_name': name,
                'platform': 'youtube',
                'post_url': post_url,
                'post_text': entry.get('title', ''),
                'likes': 0,
                'reposts': 0,
                'published_at': entry.get('published', datetime.datetime.now(datetime.timezone.utc).isoformat()),
                'topic_tag': 'YouTube',
                'is_viral': False,
                'linked_article_url': post_url,
                'thumbnail': thumbnail,
                'url_is_profile': False
            }
            
            # Emit live individual radar post to stderr
            print(json.dumps({"radar_post": post_obj}), file=sys.stderr)
            sys.stderr.flush()
            
            posts.append(post_obj)
            
        elapsed = time.time() - start_time
        print(json.dumps({"status_update": {"source": source_name, "status": "success", "duration": round(elapsed, 2), "count": len(posts)}}), file=sys.stderr)
        sys.stderr.flush()
        return posts
    except Exception as e:
        elapsed = time.time() - start_time
        print(json.dumps({"status_update": {"source": source_name, "status": "error", "duration": round(elapsed, 2), "error": str(e)}}), file=sys.stderr)
        sys.stderr.flush()
        return []

def fetch_single_influencer(person):
    """Fetch latest posts from a single AI influencer via RSSHub Twitter bridge."""
    import time
    start_time = time.time()
    source_name = f"Influencer {person['name']}"
    print(json.dumps({"status_update": {"source": source_name, "status": "fetching"}}), file=sys.stderr)
    sys.stderr.flush()
    
    # RSSHub instances
    RSSHUB_INSTANCES = [
        'rsshub.app',
    ]
    
    posts = []
    fetched = False
    
    for instance in RSSHUB_INSTANCES:
        try:
            url = f"https://{instance}/twitter/user/{person['handle']}"
            req = urllib.request.Request(url, headers={'User-Agent': 'AIBulletin/1.0'})
            with urllib.request.urlopen(req, timeout=4) as response:
                feed = feedparser.parse(response.read())
            
            if not feed.entries:
                continue
            
            for entry in feed.entries[:2]:  # Latest 2 per person
                post_text = entry.get('title', '') or entry.get('summary', '')
                # Strip HTML tags
                post_text = re.sub(r'<[^>]+>', '', post_text).strip()
                
                # Skip retweets
                if post_text.startswith('RT @'):
                    continue
                
                # Skip very short posts (likely just links)
                if len(post_text) < 30:
                    continue
                
                raw_url = entry.get('link', '')
                post_url = normalize_twitter_url(raw_url, person['handle'])
                has_specific_post = '/status/' in post_url
                
                post_obj = {
                    'id': f"tw_{person['handle']}_{hash(entry.get('id', '')) % 100000}",
                    'author_handle': f"@{person['handle']}",
                    'author_name': person['name'],
                    'platform': 'twitter',
                    'post_url': post_url,
                    'post_text': post_text[:400],
                    'likes': 0,
                    'reposts': 0,
                    'published_at': entry.get('published', datetime.datetime.now(datetime.timezone.utc).isoformat()),
                    'topic_tag': person['focus'],
                    'is_viral': False,
                    'linked_article_url': '',
                    'thumbnail': '',
                    'url_is_profile': not has_specific_post
                }
                
                # URL Validation Gate
                if not is_valid_post_url(post_obj['post_url']):
                    post_obj['post_url'] = f"https://x.com/{person['handle']}"
                    post_obj['url_is_profile'] = True
                    
                # Emit live individual radar post to stderr
                print(json.dumps({"radar_post": post_obj}), file=sys.stderr)
                sys.stderr.flush()
                
                posts.append(post_obj)
            
            fetched = True
            break  # Stop trying other instances once one works
            
        except Exception:
            continue
    
    if not fetched:
        # Fallback: create a static card with their profile link
        post_obj = {
            'id': f"tw_{person['handle']}_static",
            'author_handle': f"@{person['handle']}",
            'author_name': person['name'],
            'platform': 'twitter',
            'post_url': f"https://x.com/{person['handle']}",
            'post_text': f"Follow {person['name']} for insights on {person['focus']}. RSSHub feed currently unavailable — visit their profile directly.",
            'likes': 0,
            'reposts': 0,
            'published_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'topic_tag': person['focus'],
            'is_viral': False,
            'linked_article_url': '',
            'thumbnail': '',
            'url_is_profile': True
        }
        # Emit live individual fallback radar post to stderr
        print(json.dumps({"radar_post": post_obj}), file=sys.stderr)
        sys.stderr.flush()
        posts.append(post_obj)
    
    elapsed = time.time() - start_time
    status_label = "success" if fetched else "warning"
    print(json.dumps({
        "status_update": {
            "source": source_name,
            "status": status_label,
            "duration": round(elapsed, 2),
            "count": len(posts),
            "info": "Served static profile card" if not fetched else ""
        }
    }), file=sys.stderr)
    sys.stderr.flush()
    return posts

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch and ingest AI news RSS feeds.")
    parser.add_argument('--test', action='store_true', help="Run in test mode without DB.")
    parser.add_argument('--limit', type=int, default=8, help="Articles per feed.")
    parser.add_argument('--force', action='store_true', help="Force fresh feeds scrape regardless of cache age.")
    args = parser.parse_args()
    
    # 1. Test Mode (Sequential/parallel in-memory test)
    if args.test:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        all_articles = []
        failed_feeds = 0
        lim = 3
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_feed = {
                executor.submit(fetch_feed, name, url, lim): name 
                for name, url in FEEDS.items()
            }
            
            for future in as_completed(future_to_feed):
                name = future_to_feed[future]
                try:
                    result = future.result()
                    if not result:
                        failed_feeds += 1
                    all_articles.extend(result)
                except Exception as e:
                    print(f"  ✗ Thread error for {name}: {e}", file=sys.stderr)
                    failed_feeds += 1
        
        top = sorted(all_articles, key=lambda x: x['final_score'], reverse=True)[:10]
        print(json.dumps({"articles": top}, indent=2))
        return
    
    # 2. Standard Mode: Connect to DuckDB First
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    db_path = os.path.join(data_dir, "cache.duckdb")
    schema_path = os.path.join(project_root, "src", "schema.sql")
    last_scrape_path = os.path.join(data_dir, "last_scrape.txt")
    
    import time
    
    # 1. Enhanced DuckDB connection retry
    def connect_with_retry(db_path, read_only=False, max_attempts=30, delay=0.2):
        for attempt in range(max_attempts):
            try:
                return duckdb.connect(db_path, read_only=read_only)
            except Exception as e:
                if attempt < max_attempts - 1:
                    print(f"Database connection failed, retrying in {delay}s... (Attempt {attempt+1}/{max_attempts}): {e}", file=sys.stderr)
                    time.sleep(delay)
                    continue
                raise e

    def output_backup_cache(age_minutes=9999):
        try:
            backup_path = os.path.join(data_dir, "last_dispatches.json")
            if os.path.exists(backup_path):
                with open(backup_path, 'r', encoding='utf-8') as bf:
                    backup_payload = json.load(bf)
                # update cache age
                backup_payload["cache_age_minutes"] = int(age_minutes)
                print(json.dumps(backup_payload))
                sys.stdout.flush()
                print("Served dispatches from backup JSON cache successfully.", file=sys.stderr)
                return True
        except Exception as e:
            print(f"Error serving backup cache: {e}", file=sys.stderr)
        
        # Hardcoded critical fallback
        print(json.dumps({
            "articles": [
                {
                    "id": "critical_fallback_1",
                    "source": "System Briefing",
                    "title": "Database locked — serving critical signal payload",
                    "url": "#",
                    "published_at": dt.now().isoformat(),
                    "summary": "The news database is currently locked by a background ingestion job. The newspaper is serving this critical offline signal. Hit refresh in a few seconds once the ingest process finishes.",
                    "final_score": 9.0,
                    "hype_penalty": 0.0,
                    "section": "signals",
                    "industry_tag": "General AI",
                    "image_url": "",
                    "read_status": False,
                    "bookmarked": False,
                    "hook": "Critical System Alert"
                }
            ],
            "radar_posts": [],
            "is_cached": True,
            "cache_age_minutes": 0
        }))
        sys.stdout.flush()
        return True

    # 2. Wrap all database operations in exception handling to serve backup JSON cache on failure
    try:
        # Try read-only mode first to enable parallel readers (no lock collision on cached loads)
        conn = connect_with_retry(db_path, read_only=True)
        
        # CREATE Schema table ONLY if it doesn't already exist and matches v4
        table_exists = False
        schema_valid = False
        try:
            conn.execute("SELECT hook FROM ai_news_feed LIMIT 1")
            table_exists = True
            schema_valid = True
        except:
            try:
                conn.execute("SELECT 1 FROM ai_news_feed LIMIT 1")
                table_exists = True
            except:
                pass

        if not schema_valid:
            print("Database schema out of date or missing. Reinitializing tables in read-write mode...", file=sys.stderr)
            conn.close()
            conn = connect_with_retry(db_path, read_only=False)
            if os.path.exists(schema_path):
                with open(schema_path, 'r') as sf:
                    queries = sf.read().split(';')
                    for q in queries:
                        if q.strip():
                            try:
                                conn.execute(q)
                            except Exception as e:
                                print(f"Schema compile warning: {e}", file=sys.stderr)
        
        # === CACHE-FIRST CHECK ===
        try:
            cached_count = conn.execute("SELECT COUNT(*) FROM ai_news_feed").fetchone()[0]
        except:
            cached_count = 0

        # Rate limiting: check last scrape timestamp
        cache_fresh = False
        age_minutes = 9999
        if os.path.exists(last_scrape_path):
            try:
                with open(last_scrape_path, 'r') as f:
                    last_time_str = f.read().strip()
                    last_time = dt.fromisoformat(last_time_str)
                    age_minutes = (dt.now() - last_time).total_seconds() / 60
                    # Cache stays fresh if successfully scraped in the last 15 minutes
                    if age_minutes < 15:
                        cache_fresh = True
            except:
                pass

        # Helper function to serve the current DuckDB articles and radar posts to stdout immediately
        def output_cached_data(is_cached=False, age_minutes=0):
            try:
                # Query standard articles (top 50)
                top_articles = conn.execute("""
                    SELECT id, source, title, url, published_at, summary, 
                           final_score, hype_penalty, section, industry_tag, 
                           image_url, read_status, bookmarked, hook, story_type, story_type_label
                    FROM ai_news_feed
                    WHERE final_score >= 1.0
                    ORDER BY published_at DESC, final_score DESC
                    LIMIT 50
                """).fetchall()
                
                output_list = []
                for art in top_articles:
                    output_list.append({
                        'id': art[0],
                        'source': art[1],
                        'title': art[2],
                        'url': art[3],
                        'published_at': art[4].isoformat() if isinstance(art[4], datetime.datetime) else str(art[4]),
                        'summary': art[5],
                        'final_score': art[6],
                        'hype_penalty': art[7],
                        'section': art[8],
                        'section_display_name': SECTION_DISPLAY_NAMES.get(art[8], 'The Shift'),
                        'industry_tag': art[9] or "General AI",
                        'image_url': art[10] or "",
                        'read_status': art[11],
                        'bookmarked': art[12],
                        'hook': art[13] or "",
                        'story_type': art[14] or "news",
                        'story_type_label': art[15] or "📰 News"
                    })
                
                # Apply quality filters and hard cap to article list
                output_list = select_final_articles(output_list)
                
                radar_posts = []
                try:
                    top_radar = conn.execute("""
                        SELECT id, author_handle, author_name, platform, post_url, post_text,
                               likes, reposts, published_at, topic_tag, is_viral, linked_article_url,
                               thumbnail, url_is_profile
                        FROM radar_posts
                        ORDER BY published_at DESC, likes DESC
                        LIMIT 30
                    """).fetchall()
                    for post in top_radar:
                        radar_posts.append({
                            'id': post[0],
                            'author_handle': post[1],
                            'author_name': post[2],
                            'platform': post[3],
                            'post_url': post[4],
                            'post_text': post[5],
                            'likes': post[6],
                            'reposts': post[7],
                            'published_at': post[8].isoformat() if isinstance(post[8], datetime.datetime) else str(post[8]),
                            'topic_tag': post[9] or "General AI",
                            'is_viral': bool(post[10]),
                            'linked_article_url': post[11] or "",
                            'thumbnail': post[12] or "",
                            'url_is_profile': bool(post[13]) if post[13] is not None else False
                        })
                except:
                    pass
                
                # Print payload to stdout
                payload = {
                    "articles": output_list,
                    "radar_posts": radar_posts,
                    "is_cached": is_cached,
                    "cache_age_minutes": int(age_minutes)
                }
                print(json.dumps(payload))
                sys.stdout.flush()

                # Save successful cache output to backup JSON
                try:
                    backup_path = os.path.join(data_dir, "last_dispatches.json")
                    with open(backup_path, 'w', encoding='utf-8') as bf:
                        json.dump(payload, bf, indent=2)
                except Exception as backup_err:
                    print(f"Failed to write backup cache file: {backup_err}", file=sys.stderr)

                return len(output_list) > 0
            except Exception as e:
                print(f"Error serving cached data: {e}", file=sys.stderr)
                return False

        # Serve cache instantly for immediate visual feedback
        has_served_cache = False
        if cached_count > 0:
            has_served_cache = output_cached_data(is_cached=True, age_minutes=age_minutes)

        # Serve cache instantly and exit in <50ms if cache is fresh
        if cache_fresh and has_served_cache and not args.force:
            print("Serving instant cached dispatches (cache is fresh).", file=sys.stderr)
            conn.close()
            return

        # Cache is stale or force scraping requested. Reconnect in read-write mode.
        print("Cache empty or stale. Reconnecting database in read-write mode and launching fresh parallel aggregation...", file=sys.stderr)
        conn.close()
        try:
            conn = connect_with_retry(db_path, read_only=False)
        except Exception as db_err:
            print(f"Database write lock failed: {db_err}. Falling back to read-only cache dispatch.", file=sys.stderr)
            conn = connect_with_retry(db_path, read_only=True)
            output_cached_data(is_cached=True, age_minutes=age_minutes)
            conn.close()
            return
        try:
            with open(last_scrape_path, 'w') as f:
                f.write(dt.now().isoformat())
        except:
            pass

        # Collect articles in parallel using ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        all_articles = []
        all_radar_posts = []
        failed_feeds = 0
        lim = args.limit
        
        # Run ALL scraping concurrently — RSS feeds + Reddit + YouTube + Influencers
        with ThreadPoolExecutor(max_workers=35) as executor:
            future_to_task = {}
            
            # 1. Standard RSS feeds
            for name, url in FEEDS.items():
                future_to_task[executor.submit(fetch_feed, name, url, lim)] = ('feed', name)
            
            # 2. Reddit subreddits
            subreddits = ['LocalLLaMA', 'MachineLearning', 'artificial', 'ChatGPT', 'singularity']
            for sub in subreddits:
                future_to_task[executor.submit(fetch_single_subreddit, sub)] = ('radar_reddit', f"Reddit r/{sub}")
                
            # 3. YouTube channels
            youtube_channels = {
                'Fireship': 'UCsBjURrPoezykLs9EqgamOA',
                'Matt Wolfe': 'UCKlhhLxkoMNjBcNc5kBTj7w',
                'Two Minute Papers': 'UCbfYPyITQ-7l4upoX8nvctg',
                'AI Explained': 'UCNJ1Ymd5yFuUPtn21xtRbbw',
            }
            for name, channel_id in youtube_channels.items():
                future_to_task[executor.submit(fetch_single_youtube, name, channel_id)] = ('radar_youtube', f"YouTube {name}")
                
            # 4. Influencer feeds
            influencers = [
                {'handle': 'VaibhavSisinty', 'name': 'Vaibhav Sisinty', 'focus': 'AI Automation'},
                {'handle': 'waitin4agi_', 'name': 'Varun Mayya', 'focus': 'AI Products'},
                {'handle': '_akhaliq', 'name': 'AK', 'focus': 'Paper Drops'},
                {'handle': 'karpathy', 'name': 'Andrej Karpathy', 'focus': 'LLM Intuition'},
                {'handle': 'DrJimFan', 'name': 'Jim Fan', 'focus': 'Embodied AI'},
                {'handle': 'ylecun', 'name': 'Yann LeCun', 'focus': 'AI Research'},
                {'handle': 'sama', 'name': 'Sam Altman', 'focus': 'OpenAI'},
                {'handle': 'ClementDelworker', 'name': 'Clement Delangue', 'focus': 'Hugging Face'},
            ]
            for person in influencers:
                future_to_task[executor.submit(fetch_single_influencer, person)] = ('radar_influencer', f"Influencer {person['name']}")
                
            # Collect results as they arrive
            for future in as_completed(future_to_task):
                category, name = future_to_task[future]
                try:
                    result = future.result()
                    if category == 'feed':
                        if not result:
                            failed_feeds += 1
                        all_articles.extend(result)
                    elif category.startswith('radar_'):
                        all_radar_posts.extend(result)
                except Exception as e:
                    print(f"  ✗ Thread error for {category} {name}: {e}", file=sys.stderr)
                    if category == 'feed':
                        failed_feeds += 1
        
        print(f"  ✓ Total: {len(all_radar_posts)} radar posts collected", file=sys.stderr)
        
        # Append hand-curated mock posts for Twitter/LinkedIn to guarantee high-signal coverage
        all_radar_posts.extend(FALLBACK_RADAR_POSTS)
        
        total_feeds = len(FEEDS)
        print(f"\nFeed Results: {total_feeds - failed_feeds}/{total_feeds} feeds OK, "
              f"{len(all_articles)} articles parsed.", file=sys.stderr)
        
        # === OFFLINE JACCARD TOKEN-OVERLAP DEDUPLICATION ===
        deduplicated_articles = []
        seen_titles = []
        for art in all_articles:
            is_dup = False
            for existing_title in seen_titles:
                # Match titles at a 70% Jaccard token overlap threshold
                if calculate_jaccard_similarity(art['title'], existing_title) > 0.70:
                    is_dup = True
                    break
            if not is_dup:
                deduplicated_articles.append(art)
                seen_titles.append(art['title'])
                
        removed_duplicates_count = len(all_articles) - len(deduplicated_articles)
        print(f"Deduplication: Filtered out {removed_duplicates_count} near-duplicate news circulars.", file=sys.stderr)
        
        # Ingest standard articles safely using INSERT OR IGNORE
        inserted = 0
        for art in deduplicated_articles:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO ai_news_feed 
                    (id, source, title, url, published_at, summary, content,
                     section, final_score, hype_penalty, industry_tag, image_url, hook, story_type, story_type_label)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    art['id'], art['source'], art['title'], art['url'],
                    art['published_at'], art['summary'], art['content'],
                    art['section'], art['final_score'], art['hype_penalty'],
                    art['industry'], art['image_url'], art['hook'],
                    art.get('story_type', 'news'), art.get('story_type_label', '📰 News')
                ))
                inserted += 1
            except Exception as e:
                print(f"DB insert error: {e}", file=sys.stderr)
        
        print(f"Inserted {inserted} new articles.", file=sys.stderr)
        
        # Ingest radar posts safely using INSERT OR IGNORE
        radar_inserted = 0
        for post in all_radar_posts:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO radar_posts
                    (id, author_handle, author_name, platform, post_url, post_text,
                     likes, reposts, published_at, topic_tag, is_viral, linked_article_url,
                     thumbnail, url_is_profile)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    post['id'], post['author_handle'], post['author_name'], post['platform'],
                    post['post_url'], post['post_text'], post['likes'], post['reposts'],
                    post['published_at'], post['topic_tag'], post['is_viral'], post['linked_article_url'],
                    post.get('thumbnail', ''), post.get('url_is_profile', False)
                ))
                radar_inserted += 1
            except Exception as e:
                print(f"Radar DB insert error: {e}", file=sys.stderr)
                
        print(f"Inserted {radar_inserted} new Radar viral posts.", file=sys.stderr)
        
        # Trigger final complete print out
        output_cached_data(is_cached=False, age_minutes=0)
        conn.close()

    except Exception as exc:
        print(f"CRITICAL LOCK/DATABASE EXCEPTION IN MAIN PIPELINE: {exc}", file=sys.stderr)
        # Fall back completely to backup JSON dispatches
        output_backup_cache(age_minutes=9999)

if __name__ == "__main__":
    main()
