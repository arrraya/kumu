import axios from 'axios';
import { Player, Team, Match } from '@/types';

const API_URL = 'https://kumu-production.up.railway.app';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export const apiService = {
  players: {
    getAll: async (filters?: any): Promise<Player[]> => {
      const response = await api.get('/api/v1/players', { params: filters });
      return response.data;
    },
    
    getById: async (id: string): Promise<Player> => {
      const response = await api.get(`/api/v1/players/${id}`);
      return response.data;
    },
    
    getAnalytics: async (id: string, period: string = 'last_10') => {
      const response = await api.get(`/api/v1/players/${id}/analytics`, {
        params: { period }
      });
      return response.data;
    }
  },
  
  teams: {
    getAll: async (): Promise<Team[]> => {
      const response = await api.get('/api/v1/teams');
      return response.data;
    },
    
    getById: async (id: string): Promise<Team> => {
      const response = await api.get(`/api/v1/teams/${id}`);
      return response.data;
    }
  },
  
  matches: {
    calculate: async (playerId: string, teamIds: string[]): Promise<Match[]> => {
      const response = await api.post('/api/v1/matches/calculate', {
        player_id: playerId,
        team_ids: teamIds,
        min_score: 60.0
      });
      // Normalize offer field names: backend sends minimum/maximum, frontend expects min/max
      return response.data.map((match: any) => ({
        ...match,
        offer: {
          min: match.offer?.minimum ?? match.offer?.min ?? 0,
          max: match.offer?.maximum ?? match.offer?.max ?? 0,
          recommended: match.offer?.recommended ?? 0,
        },
      }));
    }
  },
  
  reports: {
    generate: async (playerId: string, teamId: string) => {
      const response = await api.post(`/api/v1/reports/generate`, {
        player_id: playerId,
        team_id: teamId
      });
      return response.data;
    }
  }
};

export { apiService as api };
