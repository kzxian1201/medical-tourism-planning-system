// frontend/components/displays/HistoricalPlanCard.js
import React from 'react';
import LiquidGlassCard from '../ui/LiquidGlassCard';
import LiquidGlassButton from '../ui/LiquidGlassButton';

const HistoricalPlanCard = ({ plan, onLoad }) => {
  const purpose = plan.medical_purpose || 'N/A';
  const destination = Array.isArray(plan.destination_country) ? plan.destination_country.join(', ') : plan.destination_country || 'N/A';
  const date = plan.departure_date || 'N/A';
  const timestamp = plan.timestamp?.toDate ? plan.timestamp.toDate().toLocaleDateString() : 'Unknown Date';

  return (
    <LiquidGlassCard className="p-6 space-y-4 flex flex-col justify-between">
      <div>
        <h3 className="text-xl font-semibold text-primary-light mb-2">Plan ID: {plan.id?.substring(0, 8) || 'N/A'}...</h3>
        <p className="text-gray-300"><span className="font-semibold text-gray-200">Purpose:</span> {purpose}</p>
        <p className="text-gray-300"><span className="font-semibold text-gray-200">Destination:</span> {destination}</p>
        <p className="text-gray-300"><span className="font-semibold text-gray-200">Departure:</span> {date}</p>
        <p className="text-gray-300 text-sm mt-2"><span className="font-semibold text-gray-200">Saved On:</span> {timestamp}</p>
      </div>
      <div className="mt-4">
        <LiquidGlassButton onClick={() => onLoad(plan.id)} className="w-full">Load Plan</LiquidGlassButton>
      </div>
    </LiquidGlassCard>
  );
};

export default HistoricalPlanCard;
