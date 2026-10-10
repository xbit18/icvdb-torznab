--
-- PostgreSQL database dump
--

\restrict XYfg5eQWLrGIolID3nPqQ6Nk6YYhM3WPwzYjXBAmm4TyLHoe9jdk3DCad66NVtd

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg12+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: trg_delete_related_files(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_delete_related_files() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Cancella dai files
    DELETE FROM files
    WHERE info_hash = OLD.info_hash;

    -- Cancella dai pack_files
    DELETE FROM pack_files
    WHERE pack_hash = OLD.info_hash;

    RETURN OLD;
END;
$$;


--
-- Name: trg_filter_non_video_files(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_filter_non_video_files() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
    non_video_pattern text := '\.(exe|msi|bat|cmd|sh|apk|dmg|pkg|iso|zip|rar|7z|tar|gz|bz2|xz|srt|vtt|idx|sup|cue|sfv|pdf|epub|mobi|cbr|cbz|doc|docx|xls|xlsx|ppt|pptx|nfo|txt|html|htm|url|lnk|torrent|jpg|jpeg|png|gif|bmp|webp)$';
BEGIN
    IF NEW.title IS NOT NULL AND NEW.title ~* non_video_pattern THEN
        RETURN NULL;
    END IF;
    RETURN NEW;
END;
$_$;


--
-- Name: trg_filter_non_video_pack_files(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_filter_non_video_pack_files() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
    non_video_pattern text := '\.(exe|msi|bat|cmd|sh|apk|dmg|pkg|iso|zip|rar|7z|tar|gz|bz2|xz|srt|vtt|idx|sup|cue|sfv|pdf|epub|mobi|cbr|cbz|doc|docx|xls|xlsx|ppt|pptx|nfo|txt|html|htm|url|lnk|torrent|jpg|jpeg|png|gif|bmp|webp)$';
BEGIN
    IF NEW.file_path IS NOT NULL AND NEW.file_path ~* non_video_pattern THEN
        RETURN NULL;
    END IF;
    RETURN NEW;
END;
$_$;


--
-- Name: trg_filter_non_video_torrents(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_filter_non_video_torrents() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
    non_video_pattern text := '\.(exe|msi|bat|cmd|sh|apk|dmg|pkg|iso|zip|rar|7z|tar|gz|bz2|xz|srt|vtt|idx|sup|cue|sfv|pdf|epub|mobi|cbr|cbz|doc|docx|xls|xlsx|ppt|pptx|nfo|txt|html|htm|url|lnk|torrent|jpg|jpeg|png|gif|bmp|webp)$';
BEGIN
    IF (NEW.title IS NOT NULL AND NEW.title ~* non_video_pattern) OR 
       (NEW.file_title IS NOT NULL AND NEW.file_title ~* non_video_pattern) THEN
        RETURN NULL;
    END IF;
    RETURN NEW;
END;
$_$;


--
-- Name: trg_propagate_imdb_to_files(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_propagate_imdb_to_files() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare
  v_has_more_than_one boolean;

begin
-- Solo UPDATE
  IF TG_OP <> 'UPDATE' THEN
    RETURN NEW;
  END IF;

  -- =========================
  -- GESTIONE MOVIE
  -- =========================
  IF NEW.type = 'movie' THEN

    -- true se esistono almeno 2 file per lo stesso info_hash
    SELECT EXISTS (
      SELECT 1
      FROM public.pack_files
      WHERE pack_hash = NEW.info_hash
      OFFSET 1
    )
    INTO v_has_more_than_one;

    -- Propaga SOLO se c’è un solo file
    IF NOT v_has_more_than_one THEN
      UPDATE public.pack_files
      SET
        imdb_id = CASE
                    WHEN NEW.imdb_id IS NOT NULL
                         AND NEW.imdb_id IS DISTINCT FROM imdb_id
                    THEN NEW.imdb_id
                    ELSE imdb_id
                  END
      WHERE pack_hash = NEW.info_hash
        AND (
          (NEW.imdb_id IS NOT NULL AND imdb_id IS DISTINCT FROM NEW.imdb_id)
        );
    END IF;

    RETURN NEW;
  END IF;

  -- =========================
  -- SERIE / ANIME
  -- =========================
  IF NEW.type NOT IN ('series', 'anime') THEN
    RETURN NEW;
  END IF;

  UPDATE public.files
  SET
    imdb_id = CASE
                WHEN NEW.imdb_id IS NOT NULL
                     AND NEW.imdb_id IS DISTINCT FROM imdb_id
                THEN NEW.imdb_id
                ELSE imdb_id
              END,
    to_check_id = CASE
                    WHEN NEW.to_check_id = 2 THEN 2
                    ELSE to_check_id
                  END
  WHERE info_hash = NEW.info_hash
    AND (
      (NEW.imdb_id IS NOT NULL AND imdb_id IS DISTINCT FROM NEW.imdb_id)
      OR
      (NEW.to_check_id = 2 AND to_check_id IS DISTINCT FROM 2)
    );

  RETURN NEW;
END;
$$;


--
-- Name: trg_set_to_check_id(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_set_to_check_id() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_imdb_id varchar;
BEGIN
  -- =========================
  -- INSERT
  -- =========================
  IF TG_OP = 'INSERT' THEN

    -- Caso FILES
    IF TG_TABLE_NAME = 'files' THEN
      -- Se esiste un torrent già validato (2), eredita stato e imdb
      SELECT t.imdb_id
      INTO v_imdb_id
      FROM public.torrents t
      WHERE t.info_hash = NEW.info_hash
        AND t.to_check_id = 2
      LIMIT 1;

      IF FOUND THEN
        NEW.to_check_id := 2;
        NEW.imdb_id    := v_imdb_id;
      END IF;

      RETURN NEW;
    END IF;

    -- Caso TORRENTS
    RETURN NEW;
  END IF;

  -- =========================
  -- UPDATE
  -- =========================
  IF TG_OP = 'UPDATE' THEN

    -- Se l'app promuove esplicitamente a 2 → NON intervenire
    IF NEW.to_check_id = 2 THEN
      RETURN NEW;
    END IF;

    -- LAZY NORMALIZATION:
    -- vecchi record a 0 → diventano 1 alla prima update
    IF OLD.to_check_id = 0 AND NEW.to_check_id = 0 THEN
      NEW.to_check_id := 1;
    END IF;

    RETURN NEW;
  END IF;

  RETURN NEW;
END;
$$;


--
-- Name: trg_skip_files_for_movies(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_skip_files_for_movies() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    torrent_type text;
BEGIN
    SELECT t.type
    INTO torrent_type
    FROM torrents t
    WHERE t.info_hash = NEW.info_hash;

    -- Se il torrent non esiste → skip
    IF torrent_type IS NULL THEN
        RETURN NULL;
    END IF;

    -- Se è un movie → skip
    IF torrent_type = 'movie' THEN
        RETURN NULL;
    END IF;

    -- Altrimenti procedi normalmente
    RETURN NEW;
END;
$$;


--
-- Name: trg_skip_pack_files_for_non_movies(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_skip_pack_files_for_non_movies() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    torrent_type text;
BEGIN
    SELECT t.type
    INTO torrent_type
    FROM torrents t
    WHERE t.info_hash = NEW.pack_hash;

    -- Se il torrent non esiste → skip
    IF torrent_type IS NULL THEN
        RETURN NULL;
    END IF;

    -- Se NON è movie → skip
    IF torrent_type <> 'movie' THEN
        RETURN NULL;
    END IF;

    -- Solo movie passa
    RETURN NEW;
END;
$$;


--
-- Name: trg_sync_files_on_torrent_type_change(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_sync_files_on_torrent_type_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Questo trigger HA SENSO solo su UPDATE
    -- (su INSERT non esiste il concetto di "cambio")
    IF NEW.type IS NOT DISTINCT FROM OLD.type THEN
        RETURN NEW;
    END IF;

    -- Da NON-movie → movie
    IF NEW.type = 'movie'
       AND OLD.type <> 'movie' THEN

        DELETE FROM public.files
        WHERE info_hash = NEW.info_hash;

    -- Da movie → NON-movie
    ELSIF OLD.type = 'movie'
          AND NEW.type <> 'movie' THEN

        DELETE FROM public.pack_files
        WHERE pack_hash = NEW.info_hash;
    END IF;

    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.files (
    id bigint NOT NULL,
    info_hash character varying(64) NOT NULL,
    file_index integer,
    title character varying(256) NOT NULL,
    size bigint,
    imdb_id character varying(32),
    imdb_season integer,
    imdb_episode integer,
    rd_link_index integer,
    to_check_id integer DEFAULT 1 NOT NULL
);


--
-- Name: TABLE files; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.files IS 'Series Files Table';


--
-- Name: files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.files_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.files_id_seq OWNED BY public.files.id;


--
-- Name: pack_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pack_files (
    id integer NOT NULL,
    pack_hash character varying(64) NOT NULL,
    imdb_id text,
    file_index integer NOT NULL,
    file_path text NOT NULL,
    file_size bigint,
    created_at timestamp without time zone DEFAULT now(),
    rd_link_index integer
);


--
-- Name: TABLE pack_files; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.pack_files IS 'Maps individual films within movie packs (trilogies, collections) to their IMDb IDs and file indices';


--
-- Name: COLUMN pack_files.pack_hash; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.pack_files.pack_hash IS 'InfoHash of the pack torrent';


--
-- Name: COLUMN pack_files.imdb_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.pack_files.imdb_id IS 'IMDb ID of the film within the pack';


--
-- Name: COLUMN pack_files.file_index; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.pack_files.file_index IS 'File position in the torrent (0-based, used for streaming)';


--
-- Name: COLUMN pack_files.file_path; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.pack_files.file_path IS 'Full filename as appears in torrent';


--
-- Name: COLUMN pack_files.file_size; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.pack_files.file_size IS 'File size in bytes';


--
-- Name: pack_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pack_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pack_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pack_files_id_seq OWNED BY public.pack_files.id;


--
-- Name: pending_actions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pending_actions (
    id integer NOT NULL,
    action_type character varying(64) NOT NULL,
    target_hashes text[] NOT NULL,
    summary text NOT NULL,
    payload jsonb NOT NULL,
    requested_by character varying(64) DEFAULT 'ModificaControllata'::character varying,
    status character varying(32) DEFAULT 'pending'::character varying,
    created_at timestamp with time zone DEFAULT now(),
    decided_at timestamp with time zone,
    decided_by bigint,
    rejection_reason text
);


--
-- Name: pending_actions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pending_actions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pending_actions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pending_actions_id_seq OWNED BY public.pending_actions.id;


--
-- Name: torrent_search_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.torrent_search_cache (
    cache_key text NOT NULL,
    filtered_results jsonb NOT NULL,
    media_details jsonb,
    season integer,
    episode integer,
    imdb_id text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: TABLE torrent_search_cache; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.torrent_search_cache IS 'Cache globale per ricerche torrent - condivisa tra tutti gli utenti';


--
-- Name: torrents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.torrents (
    info_hash character varying(64) NOT NULL,
    provider character varying(64) NOT NULL,
    title text NOT NULL,
    size bigint,
    type character varying(16) NOT NULL,
    upload_date timestamp without time zone NOT NULL,
    seeders smallint,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    imdb_id character varying(20),
    cached_rd boolean DEFAULT false,
    last_cached_check timestamp without time zone,
    tmdb_id integer,
    file_title text,
    file_index integer,
    cached_tb boolean,
    last_cached_check_tb timestamp without time zone,
    title_vector tsvector GENERATED ALWAYS AS (to_tsvector('italian'::regconfig, COALESCE(title, ''::text))) STORED,
    to_check_id integer DEFAULT 1 NOT NULL,
    is_torrent_pack boolean,
    contributor text,
    imdb_season integer,
    imdb_episode integer,
    lang_checked boolean DEFAULT false
);


--
-- Name: TABLE torrents; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.torrents IS 'Torrent Files';


--
-- Name: files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files ALTER COLUMN id SET DEFAULT nextval('public.files_id_seq'::regclass);


--
-- Name: pack_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pack_files ALTER COLUMN id SET DEFAULT nextval('public.pack_files_id_seq'::regclass);


--
-- Name: pending_actions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_actions ALTER COLUMN id SET DEFAULT nextval('public.pending_actions_id_seq'::regclass);


--
-- Name: files files_info_hash_file_index_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_info_hash_file_index_unique UNIQUE (info_hash, file_index);


--
-- Name: files files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (id);


--
-- Name: pack_files pack_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pack_files
    ADD CONSTRAINT pack_files_pkey PRIMARY KEY (id);


--
-- Name: pending_actions pending_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_actions
    ADD CONSTRAINT pending_actions_pkey PRIMARY KEY (id);


--
-- Name: torrent_search_cache torrent_search_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.torrent_search_cache
    ADD CONSTRAINT torrent_search_cache_pkey PRIMARY KEY (cache_key);


--
-- Name: torrents torrents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.torrents
    ADD CONSTRAINT torrents_pkey PRIMARY KEY (info_hash);


--
-- Name: idx_files_episode; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_files_episode ON public.files USING btree (imdb_id, imdb_season, imdb_episode);


--
-- Name: idx_files_imdb; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_files_imdb ON public.files USING btree (imdb_id);


--
-- Name: idx_files_info_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_files_info_hash ON public.files USING btree (info_hash);


--
-- Name: idx_files_title_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_files_title_trgm ON public.files USING gin (title public.gin_trgm_ops);


--
-- Name: idx_pack_files_filepath_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pack_files_filepath_trgm ON public.pack_files USING gin (file_path public.gin_trgm_ops);


--
-- Name: idx_pack_files_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pack_files_hash ON public.pack_files USING btree (pack_hash);


--
-- Name: idx_pack_files_imdb; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pack_files_imdb ON public.pack_files USING btree (imdb_id);


--
-- Name: idx_pending_actions_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pending_actions_created_at ON public.pending_actions USING btree (created_at);


--
-- Name: idx_pending_actions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pending_actions_status ON public.pending_actions USING btree (status);


--
-- Name: idx_torrent_cache_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrent_cache_created ON public.torrent_search_cache USING btree (created_at);


--
-- Name: idx_torrents_cached_rd; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_cached_rd ON public.torrents USING btree (cached_rd) WHERE (cached_rd = true);


--
-- Name: idx_torrents_cached_tb; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_cached_tb ON public.torrents USING btree (cached_tb) WHERE (cached_tb = true);


--
-- Name: idx_torrents_cached_tb_unchecked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_cached_tb_unchecked ON public.torrents USING btree (updated_at DESC) WHERE ((cached_tb IS TRUE) AND (lang_checked IS NOT TRUE));


--
-- Name: idx_torrents_imdb_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_imdb_id ON public.torrents USING btree (imdb_id);


--
-- Name: idx_torrents_movie_search; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_movie_search ON public.torrents USING btree (imdb_id, type, cached_rd, seeders DESC) WHERE ((type)::text = 'movie'::text);


--
-- Name: idx_torrents_multi_unchecked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_multi_unchecked ON public.torrents USING btree (info_hash) WHERE ((lang_checked IS NOT TRUE) AND (cached_tb IS TRUE));


--
-- Name: idx_torrents_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_provider ON public.torrents USING btree (provider);


--
-- Name: idx_torrents_se; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_se ON public.torrents USING btree (imdb_id, imdb_season, imdb_episode);


--
-- Name: idx_torrents_seeders; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_seeders ON public.torrents USING btree (seeders DESC);


--
-- Name: idx_torrents_title_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_title_trgm ON public.torrents USING gin (title public.gin_trgm_ops);


--
-- Name: idx_torrents_tmdb_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_tmdb_id ON public.torrents USING btree (tmdb_id);


--
-- Name: idx_torrents_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_torrents_type ON public.torrents USING btree (type);


--
-- Name: pack_files_hash_fileindex_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX pack_files_hash_fileindex_idx ON public.pack_files USING btree (pack_hash, file_index);


--
-- Name: torrents_updated_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX torrents_updated_at_idx ON public.torrents USING btree (updated_at);


--
-- Name: torrents delete_related_files_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER delete_related_files_trigger AFTER DELETE ON public.torrents FOR EACH ROW EXECUTE FUNCTION public.trg_delete_related_files();


--
-- Name: torrents propagate_imdb_to_files_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER propagate_imdb_to_files_trigger AFTER UPDATE OF imdb_id, to_check_id ON public.torrents FOR EACH ROW EXECUTE FUNCTION public.trg_propagate_imdb_to_files();


--
-- Name: files set_to_check_id_trigger_files; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER set_to_check_id_trigger_files BEFORE INSERT OR UPDATE ON public.files FOR EACH ROW EXECUTE FUNCTION public.trg_set_to_check_id();


--
-- Name: torrents set_to_check_id_trigger_torrents; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER set_to_check_id_trigger_torrents BEFORE INSERT OR UPDATE ON public.torrents FOR EACH ROW EXECUTE FUNCTION public.trg_set_to_check_id();


--
-- Name: files skip_files_for_movies_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER skip_files_for_movies_trigger BEFORE INSERT OR UPDATE ON public.files FOR EACH ROW EXECUTE FUNCTION public.trg_skip_files_for_movies();


--
-- Name: pack_files skip_pack_files_for_non_movies_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER skip_pack_files_for_non_movies_trigger BEFORE INSERT OR UPDATE ON public.pack_files FOR EACH ROW EXECUTE FUNCTION public.trg_skip_pack_files_for_non_movies();


--
-- Name: torrents sync_files_on_torrent_type_change_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER sync_files_on_torrent_type_change_trigger AFTER UPDATE OF type ON public.torrents FOR EACH ROW EXECUTE FUNCTION public.trg_sync_files_on_torrent_type_change();


--
-- Name: files trg_filter_non_video_files_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_filter_non_video_files_trigger BEFORE INSERT ON public.files FOR EACH ROW EXECUTE FUNCTION public.trg_filter_non_video_files();


--
-- Name: pack_files trg_filter_non_video_pack_files_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_filter_non_video_pack_files_trigger BEFORE INSERT ON public.pack_files FOR EACH ROW EXECUTE FUNCTION public.trg_filter_non_video_pack_files();


--
-- Name: torrents trg_filter_non_video_torrents_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_filter_non_video_torrents_trigger BEFORE INSERT ON public.torrents FOR EACH ROW EXECUTE FUNCTION public.trg_filter_non_video_torrents();


--
-- PostgreSQL database dump complete
--

\unrestrict XYfg5eQWLrGIolID3nPqQ6Nk6YYhM3WPwzYjXBAmm4TyLHoe9jdk3DCad66NVtd

