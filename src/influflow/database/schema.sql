create table public.tweet_thread (
  id uuid not null default gen_random_uuid (),
  uid uuid not null default auth.uid (),
  topic character varying not null default ''::character varying,
  tweets jsonb not null,
  created_at timestamp with time zone not null default (now() AT TIME ZONE 'utc'::text),
  updated_at timestamp with time zone not null default (now() AT TIME ZONE 'utc'::text),
  constraint TweetThread_pkey primary key (id),
  constraint tweet_thread_uid_fkey foreign KEY (uid) references auth.users (id)
) TABLESPACE pg_default;