-- Hybrid Search Setup
-- Run this file to create the extensions, table, sample data, and indexes
-- needed for the Hybrid Search cookbook.
--
-- Sample data: episodes from the Conduit podcast by Jay Miller & Kathy Campbell
-- Source: https://github.com/kjaymiller/conduit-transcripts (MIT License)
--
-- Usage:
--   psql -h localhost -U postgres -f setup.sql

-- 1. Extensions
CREATE EXTENSION IF NOT EXISTS pg_textsearch;
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;

-- 2. Table
CREATE TABLE IF NOT EXISTS episodes (
  id bigserial PRIMARY KEY,
  title text,
  description text,
  pub_date date,
  url text,
  embedding vector(1536)
);

-- 3. Sample data
INSERT INTO episodes (title, description, pub_date, url) VALUES
  ('1: Our Systems: The Unicorn & Silk Sonic Methods',
   'For most people, productivity starts with their system. Jay and Kathy talk about their own brand of productivity and what their personal systems look like.',
   '2021-07-15', 'https://www.relay.fm/conduit/1'),
  ('5: Sustained Progress: Over Being Overwhelmed',
   'Millennial Falcon wants to know how to make SUSTAINED progress on projects that feel more like a marathon, not a sprint. Kathy just made a big move and gives us some of the tips that she used to make this challenge a bit more manageable.',
   '2021-09-09', 'https://www.relay.fm/conduit/5'),
  ('13: Happiness First, Productivity Second',
   'Kathy has lots to be thankful for, Jay is unfortunately unwell, but Rosemary was on standby! Time to review the end of the year and how you finish things or let them go, before getting started on the next new adventure.',
   '2021-12-30', 'https://www.relay.fm/conduit/13'),
  ('19: Eating the Devil''s Spaghetti: Combating Imposter Syndrome',
   'How do we learn to shut up and take the compliment? How about with a fresh bowl of imp-pasta!',
   '2022-03-24', 'https://www.relay.fm/conduit/19'),
  ('48: Long Projects: Remove the Concept of Time',
   'We''ve got a longer than usual period between our next live recording so we''re taking the time to think about some longer connections. Tune in to hear how we''re going about it and longer projects in general.',
   '2023-05-04', 'https://www.relay.fm/conduit/48'),
  ('57: I Need Help to Get the Help',
   'Kathy and Jay need help to meet the demands of those around them. They need help getting help!',
   '2023-09-07', 'https://www.relay.fm/conduit/57'),
  ('61: The Conduit Burnout Candle',
   'Kathy and Jay are feeling the burn(out) well maybe the steps before the burnout. We''ve taken blowtorches to our candles and now we''re telling you the warning signs we see that this next season might be a little tough.',
   '2023-11-02', 'https://www.relay.fm/conduit/61'),
  ('81: Brett''s Mental Health (and Tech) Corner',
   'Kathy is still on a secret mission so Jay is joined by Brett Terpstra the Internet''s mad scientist to talk mental health''s link to productivity.',
   '2024-08-08', 'https://www.relay.fm/conduit/81'),
  ('100: It''s Episode 100!!',
   'Grab your tissues, it''s our most guest filled episode ever. We also discuss what Conduit is, what it means to us, and how it has affected our lives.',
   '2025-05-01', 'https://www.relay.fm/conduit/100'),
  ('107: Bored as a Benefit',
   'Jay and Kathy explore the idea that boredom isn''t the enemy of productivity — it might actually be the secret ingredient.',
   '2025-08-07', 'https://www.relay.fm/conduit/107'),
  ('115: Productivity Inside Systems You Don''t Control',
   'Kathy is joined by the Nameless of the Show, Nameless, to talk about how to be productive when the system is one you don''t control.',
   '2025-11-21', 'https://www.relay.fm/conduit/115'),
  ('117: The Year to be Selfish',
   'Kathy and Jay discuss end-of-year planning. Kathy''s 2026 theme: "The Year to Be Selfish." Jay commits to boundaries and self-preservation. They cover nonprofit transitions and preparing for the annual systems check.',
   '2025-12-18', 'https://www.relay.fm/conduit/117');

-- 4. Indexes
CREATE INDEX episodes_bm25_idx ON episodes
  USING bm25(description) WITH (text_config = 'english');

CREATE INDEX episodes_embedding_idx ON episodes
  USING diskann (embedding vector_cosine_ops);
