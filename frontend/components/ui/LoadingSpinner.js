// frontend/components/ui/LoadingSpinner.js
import React, { useState, useEffect } from 'react';

/**
 * LoadingSpinner Component
 * Displays a spinning animation with a dynamic message, indicating processing status.
 * The message changes based on `messageType` for better user feedback.
 */
const LoadingSpinner = ({
  message = "Please wait, the AI is processing...",
  messageType = "thinking" // Can be "thinking", "searching", "generating", "finalizing", "processing"
}) => {
  const [displayedMessage, setDisplayedMessage] = useState(message);

  useEffect(() => {
    let prefix = '';
    switch (messageType) {
      case 'thinking':
        prefix = 'AI is contemplating... ';
        break;
      case 'searching':
        prefix = 'Retrieving information... ';
        break;
      case 'generating':
        prefix = 'Crafting your plan... ';
        break;
      case 'finalizing':
        prefix = 'Polishing the details... ';
        break;
      case 'processing':
        prefix = 'Processing your request... ';
        break;
      default:
        prefix = '';
    }
    // Update displayedMessage whenever `message` or `messageType` changes
    setDisplayedMessage(`${prefix}${message}`);
  }, [message, messageType]); // Corrected dependencies: only re-run if message or messageType changes

  return (
    <div className="flex flex-col items-center justify-center p-8">
      {/* Spinner with a "breathe-spin" animation for a more organic feel */}
      <div className="animate-breathe-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-primary mb-4"></div>

      {/* Dynamic message display with blinking dots */}
      <p className="text-xl text-gray-200 font-semibold text-center">
        {displayedMessage}
        {/* Staggered blinking dots */}
        <span className="inline-block animate-blink animation-delay-100">.</span>
        <span className="inline-block animate-blink animation-delay-200">.</span>
        <span className="inline-block animate-blink animation-delay-300">.</span>
      </p>
    </div>
  );
};

export default LoadingSpinner;