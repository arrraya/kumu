'use client'
import React from 'react';
import { Eye } from 'lucide-react';
import { Match } from '@/types';

/**
 * One club's fit with a player, shaped for comparison against the cards
 * beside it.
 *
 * The four components used to sit in four differently coloured boxes — green,
 * blue, amber, violet. They are the same kind of figure on the same scale, so
 * four colours encoded nothing and simply competed; and a reader scanning six
 * clubs had to re-read each box to find the one component he cared about.
 * Aligned rows with a shared baseline let him run his eye down the column
 * instead.
 */

const COMPONENTS = [
  ['Tactical', 'tactical'],
  ['Performance', 'performance'],
  ['Financial', 'financial'],
  ['Growth', 'growth'],
] as const;

const MatchCard: React.FC<{
  match: Match;
  isSelected: boolean;
  onClick: () => void;
  onViewReport: () => void;
}> = ({ match, isSelected, onClick, onViewReport }) => {
  // The offer arrives in euros. It used to be multiplied by a million before
  // being divided by one, which printed "€25000000.0M".
  const money = (v: number) =>
    !v ? '—' : v >= 1e6 ? `€${(v / 1e6).toFixed(1)}M` : `€${(v / 1e3).toFixed(0)}K`;

  return (
    <div
      onClick={onClick}
      className={`bg-white border p-5 cursor-pointer transition-colors ${
        isSelected ? 'border-field' : 'border-rule hover:border-rule-strong'
      }`}
    >
      <div className="flex items-baseline justify-between gap-4">
        <div className="min-w-0">
          <h3 className="font-display text-xl text-ink leading-tight truncate">
            {match.team.name}
          </h3>
          <p className="text-sm text-ink-faint">{match.team.league}</p>
        </div>
        <div className="text-right shrink-0">
          <div className="font-display text-3xl text-ink tabular">
            {match.score.overall.toFixed(1)}
          </div>
          <div className="text-xs text-ink-faint">fit</div>
        </div>
      </div>

      <div className="mt-4 space-y-1.5">
        {COMPONENTS.map(([label, key]) => {
          const v = match.score[key] as number;
          return (
            <div key={key} className="flex items-center gap-3 text-xs">
              <span className="w-20 shrink-0 text-ink-faint">{label}</span>
              <span className="flex-1 h-1.5 bg-paper-sunk">
                <span
                  className="block h-full bg-field"
                  style={{ width: `${Math.max(0, Math.min(100, v))}%` }}
                />
              </span>
              <span className="w-8 text-right text-ink-soft tabular">
                {v.toFixed(0)}
              </span>
            </div>
          );
        })}
      </div>

      {isSelected && (
        <div className="mt-5 pt-4 border-t border-rule flex items-end justify-between gap-4">
          <div>
            <p className="text-xs text-ink-faint">Recommended offer</p>
            {/* Marked as an estimate: no observed fee enters this figure. */}
            <p className="font-display text-xl text-ink tabular is-estimated">
              {money(match.offer.recommended)}
            </p>
            <p className="text-xs text-ink-faint tabular">
              range {money(match.offer.min)} – {money(match.offer.max)}
            </p>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onClick(); onViewReport(); }}
            className="btn-primary flex items-center gap-2 shrink-0"
          >
            <Eye className="w-4 h-4" />
            View report
          </button>
        </div>
      )}
    </div>
  );
};

export default MatchCard;
