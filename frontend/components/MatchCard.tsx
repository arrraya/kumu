'use client'
import React from 'react';
import { Eye } from 'lucide-react';
import { Match } from '@/types';

interface MatchCardProps {
  match: Match;
  isSelected: boolean;
  onClick: () => void;
  onViewReport: () => void;
}

const MatchCard: React.FC<MatchCardProps> = ({ match, isSelected, onClick, onViewReport }) => {
  const formatCurrency = (value: number) => `€${(value / 1000000).toFixed(1)}M`;

  return (
    <div
      onClick={onClick}
      className={`bg-white p-6 rounded-lg shadow-md cursor-pointer transition-all hover:shadow-lg ${
        isSelected ? 'ring-2 ring-green-600' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <div className="text-3xl">{match.team.logo}</div>
          <div>
            <h3 className="text-lg font-semibold">{match.team.name}</h3>
            <p className="text-sm text-gray-600">{match.team.league}</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-green-600">
            {match.score.overall.toFixed(1)}%
          </div>
          <div className="text-sm text-gray-500">Match Score</div>
        </div>
      </div>
      
      <div className="grid grid-cols-4 gap-2 text-center mb-4">
        <div className="bg-green-50 p-2 rounded">
          <div className="text-xs text-gray-600">Tactical</div>
          <div className="font-semibold text-green-600">{match.score.tactical}%</div>
        </div>
        <div className="bg-blue-50 p-2 rounded">
          <div className="text-xs text-gray-600">Performance</div>
          <div className="font-semibold text-blue-600">{match.score.performance}%</div>
        </div>
        <div className="bg-yellow-50 p-2 rounded">
          <div className="text-xs text-gray-600">Financial</div>
          <div className="font-semibold text-yellow-600">{match.score.financial}%</div>
        </div>
        <div className="bg-purple-50 p-2 rounded">
          <div className="text-xs text-gray-600">Growth</div>
          <div className="font-semibold text-purple-600">{match.score.growth}%</div>
        </div>
      </div>

      {isSelected && (
        <div className="border-t pt-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Recommended Offer</p>
              <p className="text-lg font-semibold text-green-600">
                {formatCurrency(match.offer.recommended * 1000000)}
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClick();
                onViewReport();
              }}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
            >
              <Eye className="w-4 h-4" />
              View Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default MatchCard;
