-- Esquema de formularios en Lakebase (Postgres). Idempotente: la App lo ejecuta al arrancar.
-- El CHECK de dominio es la última barrera, detrás de la validación del navegador y de la API.
CREATE SCHEMA IF NOT EXISTS forms;

CREATE TABLE IF NOT EXISTS forms.registrations (
  email                 text PRIMARY KEY
                        CHECK (email = lower(email) AND email ~ '^[^\s@]+@(grupobimbo\.com|gbsupport\.net)$'),
  name                  text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
  country               text,
  area                  text,
  kickoff               boolean NOT NULL,
  kickoff_mode          text CHECK (kickoff_mode IN ('remote', 'onsite')),
  wave                  boolean NOT NULL,
  training_language     text NOT NULL CHECK (training_language IN ('es', 'en')),
  self_assessment_done  boolean,
  ui_language           text,
  source                text,
  -- Quién envió el formulario según Databricks Apps (nunca el campo email del formulario):
  sso_email             text,          -- X-Forwarded-Email, o el userName confirmado con el token OBO
  sso_user              text,          -- X-Forwarded-User
  sso_username          text,          -- X-Forwarded-Preferred-Username
  sso_verified          boolean NOT NULL DEFAULT false,  -- identidad confirmada con el token del usuario (/Me)
  client_submitted_at   timestamptz,
  submissions           integer NOT NULL DEFAULT 1,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  raw                   jsonb NOT NULL  -- payload completo, por si el HTML añade campos nuevos
);

CREATE TABLE IF NOT EXISTS forms.newsletter_subscriptions (
  email            text PRIMARY KEY
                   CHECK (email = lower(email) AND email ~ '^[^\s@]+@(grupobimbo\.com|gbsupport\.net)$'),
  lang             text,
  source           text,
  sso_email        text,
  sso_user         text,
  sso_username     text,
  sso_verified     boolean NOT NULL DEFAULT false,
  client_ts        timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  unsubscribed_at  timestamptz
);
