// frontend/components/displays/ChatHistory.js
import React, { useRef, useEffect } from 'react';
import LiquidGlassCard from '../ui/LiquidGlassCard';
import LiquidGlassButton from '../ui/LiquidGlassButton';
import FinalizedPlanDisplay from './FinalizedPlanDisplay';

/**
 * ChatHistory Component
 * Displays the chronological history of the conversation between the user and the AI Agent.
 */
const ChatHistory = ({ messages = [] }) => {
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const renderMessageContent = (message) => {
    const content = message.content;

    if (message.sender === 'agent' && typeof content === 'object') {
      const { message_type, content: agentContent } = content;

      switch (message_type) {
        case 'question':
          return <p className="font-medium text-primary-light">{agentContent.prompt}</p>;

        case 'summary_cards':
          return (
            <div className="space-y-2">
              <p className="font-semibold text-primary-light">{agentContent.message}</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {Array.isArray(agentContent.cards) &&
                  agentContent.cards.slice(0, 3).map((card) => (
                    <div key={card.id} className="bg-gray-800 bg-opacity-50 p-2 rounded-md text-sm">
                      <h4 className="font-bold text-white">{card.title || card.clinic_name || card.accommodation_name}</h4>
                      <p className="text-gray-300 truncate">{card.brief_description || 'No description'}</p>
                    </div>
                  ))}
              </div>
            </div>
          );

        case 'final_plan':
          return <FinalizedPlanDisplay plan={agentContent} onReset={() => {}} />;

        case 'text':
        default:
          return <p>{agentContent.prompt || 'Unknown or unsupported message type.'}</p>;
      }
    } else {
      let displayContent = typeof content === 'object' ? JSON.stringify(content, null, 2) : content;
      try {
        const parsed = JSON.parse(displayContent);
        if (typeof parsed === 'object') displayContent = 'Your selections have been submitted.';
      } catch {}
      return <p>{displayContent}</p>;
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
      {messages.map((message) => (
        <LiquidGlassCard
          key={message.id}
          className={`
            p-4 max-w-[75%] rounded-lg shadow-lg
            ${message.sender === 'user' ? 'ml-auto rounded-br-none' : 'mr-auto rounded-bl-none'}
            ${message.sender === 'user' ? 'text-white' : 'text-gray-200'}
          `}
          style={{ alignSelf: message.sender === 'user' ? 'flex-end' : 'flex-start' }}
        >
          <div className="text-base mb-2">{renderMessageContent(message)}</div>
          <div className="flex justify-end gap-2 text-xs">
            {message.sender === 'user' && (
              <LiquidGlassButton className="px-2 py-1 text-xs bg-transparent border-none hover:text-primary-light">
                Edit
              </LiquidGlassButton>
            )}
            {message.sender === 'agent' && (
              <LiquidGlassButton className="px-2 py-1 text-xs bg-transparent border-none hover:text-primary-light">
                Copy
              </LiquidGlassButton>
            )}
          </div>
        </LiquidGlassCard>
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default ChatHistory;
