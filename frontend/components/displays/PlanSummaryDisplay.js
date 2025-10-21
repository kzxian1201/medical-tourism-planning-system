// frontend/components/displays/PlanSummaryDisplay.js
import React from 'react';
import LiquidGlassCard from '../ui/LiquidGlassCard';
import LiquidGlassButton from '../ui/LiquidGlassButton';

const PlanSummaryDisplay = ({ content }) => {
  const { planning_type, payload } = content;

  const title = {
    medical_plans: 'Medical Plan Options',
    travel_arrangements: 'Travel Arrangement Options',
    travel_logistics: 'Local Logistics Options',
  }[planning_type] || 'Summary Options';

  const cards = Array.isArray(payload.output) ? payload.output : [];
  const visaInfo = payload.visa_information;

  return (
    <div className="p-4 space-y-6">
      <h2 className="text-2xl font-bold text-white text-center mb-6">{title}</h2>
      
      {visaInfo && (
        <LiquidGlassCard className="p-4 bg-blue-900 bg-opacity-30 border border-blue-700">
          <h3 className="text-lg font-semibold text-blue-300">Visa Requirements:</h3>
          <p className="text-sm text-blue-200">{visaInfo.visa_notes || 'Please check local embassy for visa details.'}</p>
        </LiquidGlassCard>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {cards.map((card) => (
          <LiquidGlassCard key={card.id} className="p-6 space-y-4">
            <h3 className="text-xl font-bold text-primary">{card.name || card.title}</h3>
            <p className="text-gray-300 text-sm">{card.location || 'Unknown Location'}</p>
            {card.cost_usd && (
              <p className="text-2xl font-semibold text-white">
                <span className="text-lg text-gray-400">Est. </span>{card.cost_usd}
              </p>
            )}
            <p className="text-gray-200">{card.brief_description || 'No description provided'}</p>
            <div className="flex justify-end pt-4">
              <LiquidGlassButton onClick={() => console.log('TODO: Fetch full details for', card.id, 'of type', planning_type)}>
                View Details
              </LiquidGlassButton>
            </div>
          </LiquidGlassCard>
        ))}
      </div>
    </div>
  );
};

export default PlanSummaryDisplay;
