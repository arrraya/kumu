import axios from 'axios';
import { Player, Team, Match } from '@/types';

const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_URL = RAW_API_URL.includes('localhost') ? RAW_API_URL : RAW_API_URL.replace('http://', 'https://');

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
      return response.data;
    }
  },
  
  reports: {
    generate: async (matchId: number) => {
      const response = await api.post(`/api/v1/reports/${matchId}`);
      return response.data;
    }
  }
};

export { apiService as api };
