# Kümü Platform API Documentation

## Base URL
https://api.kumu.football/v1

For local development:
http://localhost:8000/api/v1

## Authentication
All API requests require authentication using Bearer tokens:
Authorization: Bearer YOUR_API_TOKEN

## Table of Contents
1. [Players](#players)
2. [Teams](#teams)
3. [Matches](#matches)
4. [Scouting Reports](#scouting-reports)
5. [Analytics](#analytics)
6. [Authentication](#authentication-endpoints)
7. [Webhooks](#webhooks)
8. [Error Handling](#error-handling)

---

## Players

### Get All Players
Retrieve a paginated list of players with optional filters.

```http
GET /players
Query Parameters:
ParameterTypeDescriptionDefaultpageintegerPage number1limitintegerResults per page20positionstringFilter by position (GK, CB, RB, LB, CDM, CM, CAM, RW, LW, ST)-min_ageintegerMinimum age-max_ageintegerMaximum age-min_valuefloatMinimum market value (in millions)-max_valuefloatMaximum market value (in millions)-nationalitystringFilter by nationality-searchstringSearch by player name-
Response:
json{
  "players": [
    {
      "id": "P001",
      "external_id": "SB123456",
      "name": "Lucas Silva",
      "age": 23,
      "position": "CAM",
      "nationality": "Brazil",
      "current_team": "Santos FC",
      "market_value": 25000000,
      "image": "https://api.dicebear.com/7.x/avataaars/svg?seed=Lucas",
      "performance_index": {
        "value": 78.5,
        "trend": 2.3,
        "volatility": 0.15,
        "confidence": 0.85
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1247,
    "pages": 63
  }
}
Get Player Details
Get detailed information about a specific player.
httpGET /players/{player_id}
Path Parameters:

player_id (string, required): The player's unique identifier

Response:
json{
  "id": "P001",
  "external_id": "SB123456",
  "name": "Lucas Silva",
  "age": 23,
  "position": "CAM",
  "nationality": "Brazil",
  "current_team": "Santos FC",
  "current_league": "Serie A Brazil",
  "market_value": 25000000,
  "contract_expires": "2025-06-30",
  "image": "https://api.dicebear.com/7.x/avataaars/svg?seed=Lucas",
  "performance_index": {
    "value": 78.5,
    "trend": 2.3,
    "volatility": 0.15,
    "confidence": 0.85
  },
  "metrics": {
    "passing": {
      "completion_rate": 0.82,
      "progressive_passes_per_90": 4.2,
      "key_passes_per_90": 2.8,
      "pass_difficulty_score": 0.72
    },
    "shooting": {
      "shots_per_90": 2.4,
      "xg_per_shot": 0.18,
      "conversion_rate": 0.15,
      "goals_per_90": 0.25,
      "assists_per_90": 0.35
    },
    "movement": {
      "distance_covered_per_90": 10.5,
      "high_intensity_runs": 28,
      "average_speed": 7.2,
      "top_speed": 32.4
    },
    "defensive": {
      "tackles_per_90": 1.5,
      "interceptions_per_90": 2.1,
      "aerial_duels_won": 0.45,
      "blocks_per_90": 0.8
    }
  },
  "recent_form": [
    {
      "match": 1,
      "date": "2025-06-20",
      "opponent": "Corinthians",
      "rating": 7.8,
      "goals": 1,
      "assists": 0,
      "minutes": 90
    }
  ],
  "injury_history": [
    {
      "date": "2024-03-15",
      "injury": "Hamstring strain",
      "days_missed": 21
    }
  ]
}
Get Player Analytics
Retrieve detailed analytics for a player over a specified period.
httpGET /players/{player_id}/analytics
Path Parameters:

player_id (string, required): The player's unique identifier

Query Parameters:
ParameterTypeDescriptionDefaultperiodstringTime period (last_5, last_10, season, all)last_10typestringAnalytics type (performance, heatmap, passing, defensive)performance
Response:
json{
  "player_id": "P001",
  "period": "last_10",
  "analytics": {
    "performance_trend": [
      {"match": 1, "rating": 7.2, "index": 72},
      {"match": 2, "rating": 7.8, "index": 78}
    ],
    "average_rating": 7.6,
    "trend_direction": "positive",
    "consistency_score": 0.85,
    "peak_performance": 8.3,
    "heatmap_data": [
      {"x": 65.3, "y": 42.1, "frequency": 0.8}
    ],
    "passing_network": {
      "most_connected_players": ["P023", "P014", "P007"],
      "avg_pass_length": 18.5,
      "pass_clusters": [
        {"zone": "middle_third", "percentage": 0.45}
      ]
    }
  }
}

Teams
Get All Teams
Retrieve a list of all teams.
httpGET /teams
Query Parameters:
ParameterTypeDescriptionDefaultleaguestringFilter by league-countrystringFilter by country-min_budgetfloatMinimum budget (in millions)-max_budgetfloatMaximum budget (in millions)-
Response:
json{
  "teams": [
    {
      "id": "T001",
      "external_id": "SB789012",
      "name": "FC Metropolitan",
      "league": "Premier League",
      "country": "England",
      "logo": "🏆",
      "budget": 100000000,
      "formation": "4-3-3",
      "playing_style": {
        "possession": 0.65,
        "pressing_intensity": 0.78,
        "defensive_line": "high",
        "attacking": true,
        "high_press": true
      }
    }
  ],
  "total": 89
}
Get Team Details
Get detailed information about a specific team.
httpGET /teams/{team_id}
Path Parameters:

team_id (string, required): The team's unique identifier

Response:
json{
  "id": "T001",
  "external_id": "SB789012",
  "name": "FC Metropolitan",
  "league": "Premier League",
  "country": "England",
  "stadium": "Metropolitan Stadium",
  "capacity": 62500,
  "budget": 100000000,
  "wage_budget": 2500000,
  "formation": "4-3-3",
  "manager": "John Smith",
  "playing_style": {
    "possession": 0.65,
    "pressing_intensity": 0.78,
    "defensive_line": "high",
    "attacking": true,
    "high_press": true,
    "build_up": "short",
    "chance_creation": "through_middle"
  },
  "current_squad_size": 25,
  "average_age": 26.3
}
Get Team Requirements
Get the current requirements and needs of a team.
httpGET /teams/{team_id}/requirements
Response:
json{
  "team_id": "T001",
  "requirements": {
    "positions_needed": ["CAM", "RW", "CB"],
    "priority_positions": ["CAM"],
    "performance_thresholds": {
      "min_pass_completion": 0.80,
      "min_defensive_actions": 3.0,
      "preferred_age_range": [20, 28],
      "min_match_fitness": 0.85
    },
    "tactical_preferences": {
      "formation": "4-3-3",
      "playing_style": "attacking",
      "key_attributes": ["pace", "creativity", "pressing"],
      "preferred_foot": "either"
    },
    "financial_constraints": {
      "max_transfer_fee": 40000000,
      "max_weekly_wage": 150000,
      "available_budget": 85000000,
      "wage_budget_remaining": 1800000
    }
  }
}

Matches
Calculate Player-Team Matches
Calculate compatibility matches between a player and multiple teams.
httpPOST /matches/calculate
Request Body:
json{
  "player_id": "P001",
  "team_ids": ["T001", "T002", "T003"],
  "min_score": 70.0,
  "include_report": false
}
Response:
json{
  "player_id": "P001",
  "matches": [
    {
      "team": {
        "id": "T001",
        "name": "FC Metropolitan",
        "league": "Premier League",
        "logo": "🏆"
      },
      "score": {
        "overall": 87.5,
        "breakdown": {
          "tactical_fit": 92.0,
          "performance_match": 85.0,
          "financial_fit": 82.0,
          "growth_potential": 88.0
        }
      },
      "recommendation": "Excellent match - Player shows high compatibility",
      "offer": {
        "minimum": 20000000,
        "maximum": 28000000,
        "recommended": 24000000
      }
    }
  ],
  "calculation_time": 1.23
}
Get Match Details
Get detailed information about a specific match calculation.
httpGET /matches/{match_id}
Response:
json{
  "id": "M123456",
  "player_id": "P001",
  "team_id": "T001",
  "calculated_at": "2025-01-15T14:30:00Z",
  "score": {
    "overall": 87.5,
    "breakdown": {
      "tactical_fit": 92.0,
      "performance_match": 85.0,
      "financial_fit": 82.0,
      "growth_potential": 88.0
    }
  },
  "detailed_analysis": {
    "tactical_compatibility": {
      "formation_fit": "Perfect fit for 4-3-3",
      "role_suitability": "Ideal as creative playmaker",
      "style_match": "Excellent for possession-based system"
    },
    "performance_analysis": {
      "vs_current_squad": "+18.5% improvement",
      "league_percentile": 82,
      "key_strengths": ["Passing", "Creativity", "Work rate"]
    }
  }
}

Scouting Reports
Generate Scouting Report
Generate a comprehensive scouting report for a player-team match.
httpPOST /reports/generate
Request Body:
json{
  "player_id": "P001",
  "team_id": "T001",
  "match_id": "M123456",
  "sections": ["all"],
  "format": "json"
}
Response:
json{
  "report_id": "R789012",
  "generated_at": "2025-01-15T14:45:00Z",
  "report_metadata": {
    "player_name": "Lucas Silva",
    "team_name": "FC Metropolitan",
    "match_score": 87.5
  },
  "executive_summary": {
    "recommendation": "STRONGLY RECOMMENDED",
    "action": "Proceed immediately with negotiations",
    "key_findings": [
      "Player ranks in the 82nd percentile overall",
      "Match compatibility score: 87.5%",
      "Age profile: 23 years - Optimal",
      "Financial fit: Within budget"
    ]
  },
  "negotiation_strategy": {
    "position_strength": "Strong",
    "offer_strategy": {
      "opening_offer": 21250000,
      "maximum_offer": 26562500,
      "walk_away_price": 28656250
    },
    "timeline": {
      "initial_contact": "Immediately",
      "first_offer": "Within 48 hours",
      "negotiation_window": "1-2 weeks"
    },
    "key_tactics": [
      "Start with aggressive opening offer",
      "Set firm deadlines",
      "Emphasize alternative options"
    ]
  }
}
Get Report
Retrieve an existing scouting report.
httpGET /reports/{report_id}
Query Parameters:
ParameterTypeDescriptionDefaultformatstringResponse format (json, pdf)json

Analytics
Run Advanced Analysis
Run advanced analytics on players or teams.
httpPOST /analytics/advanced
Request Body:
json{
  "type": "playing_style_clustering",
  "player_ids": ["P001", "P002"],
  "parameters": {
    "n_clusters": 5,
    "features": ["passing", "movement", "defensive"],
    "normalize": true
  }
}
Response:
json{
  "analysis_id": "A456789",
  "type": "playing_style_clustering",
  "results": {
    "clusters": [
      {
        "cluster_id": 0,
        "label": "Creative Playmakers",
        "players": ["P001", "P045", "P078"],
        "characteristics": {
          "key_passes_per_90": 3.2,
          "progressive_passes_per_90": 5.8
        }
      }
    ],
    "player_assignments": {
      "P001": 0,
      "P002": 2
    }
  }
}
Get Performance Predictions
Get performance predictions for a player.
httpPOST /analytics/predict
Request Body:
json{
  "player_id": "P001",
  "team_id": "T001",
  "horizon": "next_season",
  "factors": ["age", "form", "team_fit"]
}

Authentication Endpoints
Login
Authenticate and receive access token.
httpPOST /auth/login
Request Body:
json{
  "email": "user@example.com",
  "password": "secure_password"
}
Response:
json{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "U123",
    "email": "user@example.com",
    "role": "analyst"
  }
}
Refresh Token
Refresh an expired access token.
httpPOST /auth/refresh

Webhooks
Subscribe to Events
Subscribe to real-time events.
httpPOST /webhooks/subscribe
Request Body:
json{
  "url": "https://your-domain.com/webhook",
  "events": [
    "match.calculated",
    "report.generated",
    "player.updated"
  ],
  "secret": "your_webhook_secret"
}
Webhook Event Format
json{
  "event": "match.calculated",
  "timestamp": "2025-01-15T14:30:00Z",
  "data": {
    "match_id": "M123456",
    "player_id": "P001",
    "team_id": "T001",
    "score": 87.5
  },
  "signature": "sha256=..."
}

Error Handling
Error Response Format
json{
  "error": {
    "code": "PLAYER_NOT_FOUND",
    "message": "Player with ID P999 not found",
    "details": {
      "player_id": "P999",
      "timestamp": "2025-01-15T14:30:00Z"
    }
  }
}
Common Error Codes
CodeHTTP StatusDescriptionPLAYER_NOT_FOUND404Player ID does not existTEAM_NOT_FOUND404Team ID does not existINVALID_PARAMETERS400Invalid request parametersUNAUTHORIZED401Missing or invalid authenticationRATE_LIMIT_EXCEEDED429Too many requestsINTERNAL_ERROR500Server error

Rate Limits
TierRequests/HourConcurrent RequestsBasic1002Pro1,00010EnterpriseUnlimited50
Rate limit information is included in response headers:
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642255200

SDK Examples
Python
pythonfrom kumu import KumuClient

client = KumuClient(api_key="YOUR_API_KEY")

# Find matches for a player
matches = client.matches.calculate(
    player_id="P001",
    team_ids=["T001", "T002", "T003"],
    min_score=75.0
)

# Generate scouting report
report = client.reports.generate(
    player_id="P001",
    team_id="T001"
)
JavaScript/TypeScript
typescriptimport { KumuAPI } from '@kumu/sdk';

const api = new KumuAPI({ apiKey: 'YOUR_API_KEY' });

// Get player details
const player = await api.players.get('P001');

// Calculate matches
const matches = await api.matches.calculate({
  playerId: 'P001',
  teamIds: ['T001', 'T002'],
  minScore: 75
});
cURL
bash# Get player details
curl -X GET "https://api.kumu.football/v1/players/P001" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Calculate matches
curl -X POST "https://api.kumu.football/v1/matches/calculate" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "P001",
    "team_ids": ["T001", "T002"],
    "min_score": 75.0
  }'

Changelog
v1.0.0 (2025-01-15)

Initial API release
Player, Team, and Match endpoints
Scouting report generation
Basic analytics features

Coming Soon

WebSocket support for real-time updates
Batch operations for multiple players
Historical data access
Advanced ML predictions