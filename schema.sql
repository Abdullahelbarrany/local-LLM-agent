-- ============================================================
--  Project Management Database
--  Run with: mysql -u root -p < schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS project_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE project_db;

-- ── Tables ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS team_members (
  id         INT           NOT NULL AUTO_INCREMENT,
  name       VARCHAR(100)  NOT NULL,
  role       VARCHAR(100)  NOT NULL,
  email      VARCHAR(150)  NOT NULL UNIQUE,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS projects (
  id           INT           NOT NULL AUTO_INCREMENT,
  name         VARCHAR(150)  NOT NULL,
  description  TEXT,
  team_members VARCHAR(500),          -- comma-separated names for quick display
  progress     TINYINT UNSIGNED NOT NULL DEFAULT 0,  -- 0-100 %
  status       ENUM('active','completed','on-hold')  NOT NULL DEFAULT 'active',
  created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS sprints (
  id          INT          NOT NULL AUTO_INCREMENT,
  project_id  INT          NOT NULL,
  name        VARCHAR(100) NOT NULL,
  goal        TEXT,
  start_date  DATE         NOT NULL,
  end_date    DATE         NOT NULL,
  status      ENUM('planned','active','completed') NOT NULL DEFAULT 'planned',
  PRIMARY KEY (id),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tasks (
  id           INT          NOT NULL AUTO_INCREMENT,
  sprint_id    INT,
  project_id   INT          NOT NULL,
  title        VARCHAR(200) NOT NULL,
  description  TEXT,
  assigned_to  VARCHAR(100),
  status       ENUM('todo','in-progress','review','done') NOT NULL DEFAULT 'todo',
  priority     ENUM('low','medium','high','critical')     NOT NULL DEFAULT 'medium',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  FOREIGN KEY (sprint_id)  REFERENCES sprints(id)  ON DELETE SET NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- ── Team Members ──────────────────────────────────────────

INSERT INTO team_members (name, role, email) VALUES
  ('Alice Johnson', 'Backend Developer',  'alice@company.com'),
  ('Bob Smith',     'Frontend Developer', 'bob@company.com'),
  ('Carol White',   'DevOps Engineer',    'carol@company.com'),
  ('David Lee',     'Product Manager',    'david@company.com'),
  ('Emma Davis',    'QA Engineer',        'emma@company.com');

-- ── Projects ─────────────────────────────────────────────

INSERT INTO projects (name, description, team_members, progress, status, created_at) VALUES
  (
    'E-Commerce Platform Redesign',
    'Full redesign of the customer-facing storefront and checkout flow. Focus on performance, mobile UX, and conversion rate.',
    'Alice Johnson, Bob Smith, Emma Davis',
    65,
    'active',
    '2026-01-10 09:00:00'
  ),
  (
    'Mobile App v2.0',
    'Native iOS and Android rewrite replacing the old hybrid app. Adds offline mode, push notifications, and a new design system.',
    'Bob Smith, Carol White, David Lee',
    30,
    'active',
    '2026-02-01 10:00:00'
  ),
  (
    'Internal Analytics Dashboard',
    'Business intelligence dashboard for the ops team. Replaced legacy spreadsheet reporting with live charts and scheduled exports.',
    'Alice Johnson, Carol White, David Lee, Emma Davis',
    100,
    'completed',
    '2025-10-05 08:30:00'
  );

-- ── Sprints ───────────────────────────────────────────────

-- Project 1 — E-Commerce Platform Redesign
INSERT INTO sprints (project_id, name, goal, start_date, end_date, status) VALUES
  (1, 'Sprint 1 — Foundation',
   'Set up monorepo, CI pipeline, and component library. Deliver static homepage.',
   '2026-01-13', '2026-01-24', 'completed'),

  (1, 'Sprint 2 — Product Catalogue',
   'Build product listing, search, filtering, and product detail pages.',
   '2026-01-27', '2026-02-07', 'completed'),

  (1, 'Sprint 3 — Checkout Flow',
   'Implement cart, address entry, payment integration, and order confirmation.',
   '2026-02-10', '2026-02-21', 'active'),

  (1, 'Sprint 4 — Polish & Launch',
   'Performance optimisation, accessibility audit, A/B test setup, and go-live.',
   '2026-02-24', '2026-03-07', 'planned');

-- Project 2 — Mobile App v2.0
INSERT INTO sprints (project_id, name, goal, start_date, end_date, status) VALUES
  (2, 'Sprint 1 — Core Architecture',
   'Scaffold React Native project, auth screens, navigation shell, and design tokens.',
   '2026-02-03', '2026-02-14', 'completed'),

  (2, 'Sprint 2 — Home & Feed',
   'Build home screen, activity feed, and offline caching layer.',
   '2026-02-17', '2026-02-28', 'active'),

  (2, 'Sprint 3 — Notifications & Settings',
   'Push notifications, user preferences, account management screens.',
   '2026-03-03', '2026-03-14', 'planned');

-- Project 3 — Internal Analytics Dashboard
INSERT INTO sprints (project_id, name, goal, start_date, end_date, status) VALUES
  (3, 'Sprint 1 — Data Pipeline',
   'Build ETL jobs, define data models, and deliver first set of KPI cards.',
   '2025-10-06', '2025-10-17', 'completed'),

  (3, 'Sprint 2 — Charts & Export',
   'Add time-series charts, cohort tables, CSV/PDF export, and user roles.',
   '2025-10-20', '2025-10-31', 'completed');

-- ── Tasks ─────────────────────────────────────────────────

-- Project 1 / Sprint 3 — Checkout Flow (active)
INSERT INTO tasks (sprint_id, project_id, title, description, assigned_to, status, priority, created_at) VALUES
  (3, 1, 'Build cart sidebar component',
   'Slide-out cart with quantity controls, remove item, and subtotal.',
   'Bob Smith', 'done', 'high', '2026-02-10 09:00:00'),

  (3, 1, 'Persist cart to localStorage',
   'Cart state must survive page refresh and be synced on login.',
   'Alice Johnson', 'done', 'high', '2026-02-10 09:05:00'),

  (3, 1, 'Address autocomplete (Google Places)',
   'Integrate Google Places API for shipping address entry.',
   'Bob Smith', 'in-progress', 'high', '2026-02-11 10:00:00'),

  (3, 1, 'Stripe payment integration',
   'Implement Stripe Elements for card entry. Handle 3DS redirects.',
   'Alice Johnson', 'in-progress', 'critical', '2026-02-11 10:30:00'),

  (3, 1, 'Order confirmation email',
   'Trigger transactional email via SendGrid on successful payment.',
   'Alice Johnson', 'todo', 'medium', '2026-02-12 08:00:00'),

  (3, 1, 'Write checkout E2E tests',
   'Cypress tests covering happy path, card decline, and address validation.',
   'Emma Davis', 'todo', 'high', '2026-02-12 08:30:00'),

  (3, 1, 'Mobile checkout layout fixes',
   'Fix overflow issues on small screens in the address and payment steps.',
   'Bob Smith', 'todo', 'medium', '2026-02-13 09:00:00');

-- Project 1 / Sprint 2 — Product Catalogue (completed)
INSERT INTO tasks (sprint_id, project_id, title, description, assigned_to, status, priority, created_at) VALUES
  (2, 1, 'Product listing page',        NULL, 'Bob Smith',     'done', 'high',   '2026-01-27 09:00:00'),
  (2, 1, 'Search & filter API',         NULL, 'Alice Johnson', 'done', 'high',   '2026-01-27 09:10:00'),
  (2, 1, 'Product detail page',         NULL, 'Bob Smith',     'done', 'high',   '2026-01-28 10:00:00'),
  (2, 1, 'Image CDN integration',       NULL, 'Carol White',   'done', 'medium', '2026-01-29 11:00:00'),
  (2, 1, 'Catalogue smoke tests',       NULL, 'Emma Davis',    'done', 'medium', '2026-01-30 09:00:00');

-- Project 2 / Sprint 2 — Home & Feed (active)
INSERT INTO tasks (sprint_id, project_id, title, description, assigned_to, status, priority, created_at) VALUES
  (6, 2, 'Home screen layout',
   'Implement header, hero banner, and horizontal category scroll.',
   'Bob Smith', 'done', 'high', '2026-02-17 09:00:00'),

  (6, 2, 'Activity feed API integration',
   'Connect to REST feed endpoint; infinite scroll with React Query.',
   'Bob Smith', 'in-progress', 'high', '2026-02-17 09:15:00'),

  (6, 2, 'Offline cache with MMKV',
   'Cache last 50 feed items using MMKV for offline viewing.',
   'Carol White', 'in-progress', 'medium', '2026-02-18 10:00:00'),

  (6, 2, 'Pull-to-refresh',
   'Implement pull-to-refresh gesture on the feed list.',
   'Bob Smith', 'todo', 'low', '2026-02-19 09:00:00'),

  (6, 2, 'Feed unit tests',
   'Jest tests for feed reducer and cache invalidation logic.',
   'Emma Davis', 'todo', 'medium', '2026-02-19 09:30:00');

-- Project 2 / Sprint 1 — Core Architecture (completed)
INSERT INTO tasks (sprint_id, project_id, title, description, assigned_to, status, priority, created_at) VALUES
  (5, 2, 'React Native scaffold',        NULL, 'Carol White',   'done', 'critical', '2026-02-03 09:00:00'),
  (5, 2, 'Auth screens (login/signup)',  NULL, 'Bob Smith',     'done', 'high',     '2026-02-03 09:10:00'),
  (5, 2, 'Navigation shell',            NULL, 'Bob Smith',     'done', 'high',     '2026-02-04 10:00:00'),
  (5, 2, 'Design token system',         NULL, 'Bob Smith',     'done', 'medium',   '2026-02-05 09:00:00'),
  (5, 2, 'CI/CD for mobile builds',     NULL, 'Carol White',   'done', 'high',     '2026-02-06 11:00:00');

-- Project 3 / Sprint 1 & 2 — Analytics Dashboard (completed)
INSERT INTO tasks (sprint_id, project_id, title, description, assigned_to, status, priority, created_at) VALUES
  (8, 3, 'ETL pipeline design',       NULL, 'Alice Johnson', 'done', 'critical', '2025-10-06 09:00:00'),
  (8, 3, 'KPI card components',       NULL, 'Bob Smith',     'done', 'high',     '2025-10-07 09:00:00'),
  (8, 3, 'Database schema migration', NULL, 'Carol White',   'done', 'high',     '2025-10-08 10:00:00'),
  (8, 3, 'Data validation tests',     NULL, 'Emma Davis',    'done', 'medium',   '2025-10-09 09:00:00'),
  (9, 3, 'Time-series chart module',  NULL, 'Bob Smith',     'done', 'high',     '2025-10-20 09:00:00'),
  (9, 3, 'Cohort table component',    NULL, 'Alice Johnson', 'done', 'medium',   '2025-10-21 09:00:00'),
  (9, 3, 'CSV/PDF export service',    NULL, 'Alice Johnson', 'done', 'medium',   '2025-10-22 10:00:00'),
  (9, 3, 'User role management',      NULL, 'Carol White',   'done', 'low',      '2025-10-23 09:00:00'),
  (9, 3, 'Dashboard QA sign-off',     NULL, 'Emma Davis',    'done', 'high',     '2025-10-30 14:00:00');
