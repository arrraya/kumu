-- Create database
CREATE DATABASE kumu_db;

-- Connect to database
\c kumu_db;

-- Create initial data
INSERT INTO teams (external_id, name, league, country, budget, formation) VALUES
('T001', 'FC Metropolitan', 'Premier League', 'England', 100000000, '4-3-3'),
('T002', 'Atletico Madrid', 'La Liga', 'Spain', 80000000, '4-4-2'),
('T003', 'Borussia Dortmund', 'Bundesliga', 'Germany', 75000000, '4-2-3-1');

-- Add sample players
INSERT INTO players (external_id, name, age, position, nationality, current_team, market_value) VALUES
('P001', 'Lucas Silva', 23, 'CAM', 'Brazil', 'Santos FC', 25000000),
('P002', 'Marco Rossi', 29, 'CB', 'Italy', 'Lazio', 15000000);