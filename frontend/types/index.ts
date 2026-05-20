export interface PerformanceIndex {
    value: number;
    trend: number;
    volatility: number;
    confidence: number;
  }
  
  export interface PlayerMetrics {
    passing: {
      completion: number;
      progressive: number;
      keyPasses: number;
      difficulty: number;
    };
    shooting: {
      shotsP90: number;
      xgPerShot: number;
      conversion: number;
    };
    movement: {
      distance: number;
      sprints: number;
      avgSpeed: number;
    };
    defensive: {
      tacklesP90: number;
      interceptionsP90: number;
      aerialWon: number;
    };
  }
  
  export interface Player {
    id: string;
    name: string;
    age: number;
    position: string;
    nationality: string;
    currentTeam: string;
    marketValue: number;
    performanceIndex: PerformanceIndex;
    metrics: PlayerMetrics;
    recentForm: Array<{
      match: number;
      rating: number;
      value: number;
    }>;
  }
  
  export interface Team {
    id: string;
    name: string;
    league: string;
    country: string;
    logo: string;
    budget: number;
    formation: string;
    playingStyle: any;
  }
  
  export interface MatchScore {
    overall: number;
    tactical: number;
    performance: number;
    financial: number;
    growth: number;
  }
  
  export interface Match {
    id?: number;
    team: Team;
    score: MatchScore;
    offer: {
      min: number;
      max: number;
      recommended: number;
    };
  }