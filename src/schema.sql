-- DuckDB Schema for AI Newspaper (v4.0 Bento & Radar Edition)
-- Drop legacy tables to rebuild clean schemas
DROP TABLE IF EXISTS ai_news_feed;
CREATE TABLE IF NOT EXISTS ai_news_feed (
    id VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    url VARCHAR NOT NULL,
    published_at TIMESTAMP,
    summary VARCHAR,
    content VARCHAR,
    
    -- Section-based layout
    section VARCHAR DEFAULT 'signals',
    
    -- Scoring
    final_score DOUBLE DEFAULT 0.0,
    hype_penalty DOUBLE DEFAULT 0.0,
    
    -- Industry vertical tag
    industry_tag VARCHAR DEFAULT 'General AI',
    
    -- Editorial "Why it matters" catch-tag
    hook VARCHAR DEFAULT '',
    
    -- Media
    image_url VARCHAR,
    
    -- Phase B story classifications
    story_type VARCHAR DEFAULT 'news',
    story_type_label VARCHAR DEFAULT '📰 News',
    
    -- User interaction
    read_status BOOLEAN DEFAULT FALSE,
    bookmarked BOOLEAN DEFAULT FALSE
);

-- Table for tracking actual viral posts/videos in the live Radar feed
DROP TABLE IF EXISTS radar_posts;
CREATE TABLE IF NOT EXISTS radar_posts (
    id VARCHAR PRIMARY KEY,
    author_handle VARCHAR,
    author_name VARCHAR,
    platform VARCHAR,            -- 'twitter', 'linkedin', 'reddit', 'youtube'
    post_url VARCHAR,
    post_text VARCHAR,
    likes INTEGER DEFAULT 0,
    reposts INTEGER DEFAULT 0,
    published_at TIMESTAMP,
    topic_tag VARCHAR DEFAULT 'General AI',
    is_viral BOOLEAN DEFAULT FALSE,
    linked_article_url VARCHAR DEFAULT '',
    thumbnail VARCHAR DEFAULT '',
    url_is_profile BOOLEAN DEFAULT FALSE
);
