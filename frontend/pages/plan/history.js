// frontend/pages/plan/history.js
import React, { useEffect, useState, useContext } from 'react';
import { SessionContext } from '../../contexts/SessionContext';
import MainLayout from '../../components/layouts/MainLayout';
import LiquidGlassCard from '../../components/ui/LiquidGlassCard';
import LiquidGlassButton from '../../components/ui/LiquidGlassButton';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import { useRouter } from 'next/router';
import HistoricalPlanCard from '../../components/displays/HistoricalPlanCard';
import LiquidGlassModal from "../../components/ui/LiquidGlassModal"; 

const MessageDisplay = ({ message, type }) => {
  if (!message) return null;
  const bgColor = type === 'error' ? 'bg-red-500/30' : 'bg-green-500/30';
  const textColor = type === 'error' ? 'text-red-300' : 'text-green-300';
  return (
    <div className={`p-4 rounded-lg shadow-md ${bgColor} ${textColor} text-center font-medium transition-all duration-300`}>
      {message}
    </div>
  );
};

const HistoryPage = () => {
  const { userId, authReady, fetchUserPlans, loadPlan, startNewPlan, deleteSession } = useContext(SessionContext);
  const [historicalPlans, setHistoricalPlans] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const router = useRouter();

  useEffect(() => {
    const getPlans = async () => {
      if (authReady && userId) {
        setIsLoading(true);
        try {
          const plans = await fetchUserPlans();
          setHistoricalPlans(plans || []);
        } catch {
          setMessage({ type: 'error', text: 'Failed to fetch historical plans.' });
        } finally {
          setIsLoading(false);
        }
      }
    };
    getPlans();
  }, [authReady, userId, fetchUserPlans]);

  const handleLoadPlan = async (planId) => {
    setIsLoading(true);
    const success = await loadPlan(planId, userId);
    setIsLoading(false);
    if (success) router.push('/plan');
    else {
      setMessage({ type: 'error', text: 'Failed to load plan. It might not exist or there was a network error.' });
      setTimeout(() => setMessage(null), 5000);
    }
  };

  const handleStartNewPlanClick = () => {
    startNewPlan();
    router.push('/plan');
  };

  const handleDeletePlan = (planId) => {
    setConfirmDelete(planId); 
  };

  const confirmDeletePlan = async () => {
    if (!confirmDelete) return;

    setIsLoading(true);
    const success = await deleteSession(confirmDelete);
    if (success) {
      setHistoricalPlans(historicalPlans.filter(p => p.id !== confirmDelete));
      setMessage({ type: "success", text: "Plan deleted successfully." });
    } else {
      setMessage({ type: "error", text: "Failed to delete plan." });
    }
    setIsLoading(false);
    setConfirmDelete(null); 
    setTimeout(() => setMessage(null), 4000);
  };

  if (!authReady || isLoading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center min-h-[50vh]">
          <LoadingSpinner message={!authReady ? "Authenticating..." : "Loading historical plans..."} />
        </div>
      </MainLayout>
    );
  }

  return (
    <LiquidGlassCard className="max-w-7xl mx-auto p-8 space-y-8">
      <h2 className="text-3xl font-bold text-primary-light text-center">My Past Plans</h2>
      <p className="text-gray-300 text-center mb-8">Browse and load your previously generated medical travel plans.</p>

      <MessageDisplay message={message?.text} type={message?.type} />

      {historicalPlans.length === 0 ? (
        <div className="text-center space-y-4">
          <p className="text-gray-300">You don&apos;t have any past plans yet.</p>
          <LiquidGlassButton onClick={handleStartNewPlanClick}>Start Your First Plan</LiquidGlassButton>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {historicalPlans.map(plan => (
            <HistoricalPlanCard 
              key={plan.id} 
              plan={plan} 
              onLoad={handleLoadPlan} 
              onDelete={handleDeletePlan} 
            />          
          ))}
        </div>
      )}

      {historicalPlans.length > 0 && (
        <div className="flex justify-center mt-10">
          <LiquidGlassButton onClick={handleStartNewPlanClick}>Start New Plan</LiquidGlassButton>
        </div>
      )}
    </LiquidGlassCard>
  );
};

export default HistoryPage;
