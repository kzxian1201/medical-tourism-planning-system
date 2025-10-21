// frontend/components/displays/FinalizedPlanDisplay.js
import React from 'react';
import LiquidGlassCard from '../ui/LiquidGlassCard';
import LiquidGlassButton from '../ui/LiquidGlassButton';

const FinalizedPlanDisplay = ({ plan, onReset, onAddToFavorites, onEditPlan, onSharePlan }) => {
  const renderArray = (arr) => (!arr || arr.length === 0 ? 'N/A' : arr.join(', '));

  return (
    <LiquidGlassCard className="max-w-4xl mx-auto p-8 space-y-8 my-8">
      <h2 className="text-4xl font-extrabold text-primary text-center">Your Finalized Travel Plan</h2>
      <p className="text-gray-300 text-center text-lg">Congratulations! Your personalized medical travel plan is ready.</p>

      {/* Total Budget */}
      {plan.total_estimated_budget_usd !== undefined && (
        <div className="text-center bg-gray-800/50 p-4 rounded-lg shadow-inner">
          <h3 className="text-2xl font-bold text-accent">Total Estimated Budget</h3>
          <p className="text-4xl font-extrabold text-white mt-2">
            ${Number(plan.total_estimated_budget_usd).toLocaleString()} USD
          </p>
        </div>
      )}

      {/* Medical Details */}
      <section className="space-y-4">
        <h3 className="text-2xl font-bold text-white border-b border-gray-600 pb-2">Medical Details</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-400">
          <div><span className="font-semibold text-gray-200">Purpose:</span> {plan.medicalDetails?.purpose || 'N/A'}</div>
          <div><span className="font-semibold text-gray-200">Destination:</span> {renderArray(plan.medicalDetails?.destination)}</div>
          <div><span className="font-semibold text-gray-200">Chosen Hospital:</span> {plan.medicalDetails?.hospital || 'N/A'}</div>
          <div><span className="font-semibold text-gray-200">Budget:</span> ${plan.medicalDetails?.budget?.min || 0} - ${plan.medicalDetails?.budget?.max || 0}</div>
        </div>
      </section>

      {/* Travel Arrangements */}
      <section className="space-y-4">
        <h3 className="text-2xl font-bold text-white border-b border-gray-600 pb-2">Travel Arrangements</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-400">
          <div><span className="font-semibold text-gray-200">Departure City:</span> {plan.travelArrangements?.departureCity || 'N/A'}</div>
          <div><span className="font-semibold text-gray-200">Departure Date:</span> {plan.travelArrangements?.departureDate || 'N/A'}</div>
          <div><span className="font-semibold text-gray-200">Chosen Flight:</span> {plan.travelArrangements?.flight || 'N/A'}</div>
          <div><span className="font-semibold text-gray-200">Chosen Accommodation:</span> {plan.travelArrangements?.accommodation || 'N/A'}</div>
        </div>
      </section>

      {/* Local Logistics */}
      <section className="space-y-4">
        <h3 className="text-2xl font-bold text-white border-b border-gray-600 pb-2">Local Logistics</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-400">
          <div><span className="font-semibold text-gray-200">Airport Pickup:</span> {plan.localLogistics?.airportPickupService === 'yes' ? 'Yes' : 'No'}</div>
          <div><span className="font-semibold text-gray-200">Local Transport:</span> {renderArray(plan.localLogistics?.localTransportationNeeds)}</div>
          <div><span className="font-semibold text-gray-200">Dietary Needs:</span> {renderArray(plan.localLogistics?.specificDietaryPreferences)}</div>
          <div><span className="font-semibold text-gray-200">SIM Card:</span> {plan.localLogistics?.localSimCardAssistance === 'yes' ? 'Yes' : 'No'}</div>
          <div><span className="font-semibold text-gray-200">Leisure Activities:</span> {renderArray(plan.localLogistics?.leisureActivityInterest)}</div>
        </div>
      </section>

      {/* Action Buttons */}
      <div className="flex flex-wrap justify-center gap-4 mt-10">
        {onAddToFavorites && <LiquidGlassButton onClick={onAddToFavorites} className="px-6 py-3 text-md">Add to My Favorite Plan</LiquidGlassButton>}
        {onEditPlan && <LiquidGlassButton onClick={onEditPlan} className="px-6 py-3 text-md bg-transparent border border-gray-600 text-gray-200 hover:bg-gray-700 hover:text-white">Edit Plan</LiquidGlassButton>}
        <LiquidGlassButton onClick={onReset} className="px-6 py-3 text-md bg-transparent border border-gray-600 text-gray-200 hover:bg-gray-700 hover:text-white">Start New Plan</LiquidGlassButton>
      </div>
    </LiquidGlassCard>
  );
};

export default FinalizedPlanDisplay;
