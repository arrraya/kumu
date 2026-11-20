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
    // The id the player carries in whatever source he came from, hashed
    // with his tenant. The API returns it and `normalizePlayer` passes it
    // through; anything joining a player to material held outside the
    // database - his pose clip, for one - has to join on this rather than
    // on a name two players can share.
    external_id?: string | null;
    name: string;
    // Both nullable, and the type said otherwise for as long as both were
    // always present. A feed that carries no birth date and no valuation is
    // the ordinary case now, and while these read `number` the compiler
    // agreed with every component that treated an absence as a figure.
    age: number | null;
    position: string;
    nationality: string;
    currentTeam: string;
    marketValue: number | null;
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