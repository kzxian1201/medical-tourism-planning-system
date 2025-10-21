// frontend/pages/plan/index.js
import React, { useState, useEffect, useContext, useRef } from 'react';
import AgentPlanningPageLayout from '../../components/layouts/AgentPlanningPageLayout';
import AgentQuestionDisplay from '../../components/displays/AgentQuestionDisplay';
import ChatHistory from '../../components/displays/ChatHistory';
import FinalizedPlanDisplay from '../../components/displays/FinalizedPlanDisplay';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import PlanSummaryDisplay from '../../components/displays/PlanSummaryDisplay';
import LiquidGlassButton from '../../components/ui/LiquidGlassButton';
import { SessionContext } from '../../contexts/SessionContext';

const PlanPage = () => {
  const {
    sessionState,
    startNewPlan,
    authReady,
    userId,
    handleAgentResponse,
    isLoading,
    isInitialLoad,
    profileData,
    isPlanLoadingFromHistory,
  } = useContext(SessionContext);

  const [userInputValue, setUserInputValue] = useState('');
  const messagesEndRef = useRef(null);

  // Auto-scroll to the bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [sessionState.chatHistory]);

  // Initialize new plan if no session
  useEffect(() => {
    if (authReady && userId && !isPlanLoadingFromHistory && !sessionState.sessionId) {
      startNewPlan(profileData);
    }
  }, [authReady, userId, startNewPlan, sessionState.sessionId, profileData, isPlanLoadingFromHistory]);

  const handleUserSubmit = async (e) => {
    e.preventDefault();
    if (!userInputValue.trim() || isLoading) return;
    const input = userInputValue.trim();
    setUserInputValue('');
    await handleAgentResponse(input);
  };

  const handleQuestionSubmit = async (answer) => {
    if (!answer || isLoading) return;
    await handleAgentResponse(JSON.stringify(answer));
  };

  const renderContent = () => {
    // Render loading state first
    if (isLoading || isInitialLoad) {
      return (
        <div className="flex justify-center items-center h-full">
          <LoadingSpinner message="Thinking..." />
        </div>
      );
    }

    // Check for the last message to render any special displays
    const lastMessage = sessionState.chatHistory?.[sessionState.chatHistory.length - 1];

    // If no chat history, render the welcome message
    if (!lastMessage) {
      return (
        <div className="flex items-center justify-center h-full">
          <div className="text-gray-300 text-2xl font-bold text-center">
            Welcome! Starting a new plan for you...
          </div>
        </div>
      );
    }
    // If the last message is from the agent, check its type
    const agentResponse = lastMessage.content || { message_type: 'text', prompt: '' };

    // Render different content based on the latest message type
    switch (agentResponse.message_type) {
      case 'question':
        return <AgentQuestionDisplay question={agentResponse.content} onSubmit={handleQuestionSubmit} />;
      case 'summary_cards':
        return <PlanSummaryDisplay content={agentResponse.content} />;
      case 'final_plan':
        return <FinalizedPlanDisplay plan={agentResponse.content} onReset={startNewPlan} />;
      case 'text':
      default:
        return null;
    }
  };

  return (
    <AgentPlanningPageLayout currentStage={sessionState.session_state?.current_stage || 'loading'}>
      <div className="flex flex-col h-screen w-full max-w-7xl mx-auto
                     shadow-2xl rounded-3xl overflow-hidden
                     bg-white/10 backdrop-blur-3xl border border-white/20">

        {/* Main chat area */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 sm:p-8">
          {sessionState.chatHistory && sessionState.chatHistory.length > 0 ? (
            <>
              <ChatHistory messages={sessionState.chatHistory} />
              {renderContent()}
            </>
          ) : (
            renderContent()
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Unified input area */}
        <div className="bg-white/10 backdrop-blur-xl border-t border-white/20 p-4">
          <form
            onSubmit={handleUserSubmit}
            className="flex flex-col sm:flex-row gap-4 items-stretch w-full"
          >
            <input
              type="text"
              value={userInputValue}
              onChange={(e) => setUserInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  handleUserSubmit(e);
                  e.preventDefault();
                }
              }}
              placeholder="Type your message..."
              className="flex-1 min-w-0 h-12 px-4 bg-transparent border border-white/20
                         rounded-2xl text-white placeholder-white/70
                         focus:outline-none focus:ring-2 focus:ring-blue-400"
              disabled={isLoading}
            />
            <LiquidGlassButton
              type="submit"
              disabled={!userInputValue.trim() || isLoading}
              className="h-12 px-6 bg-blue-600/50 hover:bg-blue-600/70
                         text-white rounded-2xl shadow-lg backdrop-blur-md
                         border border-blue-400/30 flex items-center justify-center"
            >
              Send
            </LiquidGlassButton>
          </form>
        </div>
      </div>
    </AgentPlanningPageLayout>
  );
};

export default PlanPage;