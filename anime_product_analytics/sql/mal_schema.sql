DROP TABLE IF EXISTS "MyAnimeList".details;

CREATE TABLE "MyAnimeList".details (
    mal_id INTEGER PRIMARY KEY,
    title TEXT,
    title_japanese TEXT,
    url TEXT,
    image_url TEXT,
    type VARCHAR(50),
    status VARCHAR(50),
    score REAL,
    scored_by REAL,
    start_date VARCHAR(50),
    end_date VARCHAR(50),
    synopsis TEXT,
    rank REAL,
    popularity INTEGER,
    members INTEGER,
    favorites INTEGER,
    genres TEXT,
    studios TEXT,
    themes TEXT,
    demographics VARCHAR(50),
    source VARCHAR(50),
    rating VARCHAR(50),
    episodes REAL,
    season VARCHAR(50),
    year REAL,
    producers TEXT,
    explicit_genres TEXT,
    licensors TEXT,
    streaming TEXT
);

DROP TABLE IF EXISTS "MyAnimeList".ratings;

CREATE TABLE "MyAnimeList".ratings (
    username VARCHAR(50),
    anime_id INTEGER,
    status VARCHAR(50),
    score INTEGER,
    is_rewatching REAL,
    num_watched_episodes INTEGER,
    CONSTRAINT uq_ratings_username_anime UNIQUE (username, anime_id),
    CONSTRAINT fk_ratings_anime_id FOREIGN KEY (anime_id) REFERENCES "MyAnimeList".details (mal_id)
);

DROP TABLE IF EXISTS "MyAnimeList".stats;

CREATE TABLE "MyAnimeList".stats (
    mal_id INTEGER PRIMARY KEY,
    watching INTEGER,
    completed INTEGER,
    on_hold INTEGER,
    dropped INTEGER,
    plan_to_watch INTEGER,
    total INTEGER,
    score_1_votes REAL,
    score_1_percentage REAL,
    score_2_votes REAL,
    score_2_percentage REAL,
    score_3_votes REAL,
    score_3_percentage REAL,
    score_4_votes REAL,
    score_4_percentage REAL,
    score_5_votes REAL,
    score_5_percentage REAL,
    score_6_votes REAL,
    score_6_percentage REAL,
    score_7_votes REAL,
    score_7_percentage REAL,
    score_8_votes REAL,
    score_8_percentage REAL,
    score_9_votes REAL,
    score_9_percentage REAL,
    score_10_votes REAL,
    score_10_percentage REAL,
    CONSTRAINT fk_stats_mal_id FOREIGN KEY (mal_id) REFERENCES "MyAnimeList".details (mal_id)
);
