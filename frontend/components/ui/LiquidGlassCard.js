// frontend/components/ui/LiquidGlassCard.js
import React from 'react';

const LiquidGlassCard = ({ children, className = '', onClick, clickable = false }) => {
  // Conditionally apply hover effects based on 'clickable' prop
  const hoverClasses = clickable ? 'hover:scale-[1.01] hover:shadow-2xl' : ''; // Enhanced scale up and shadow for a more pronounced effect
  const cursorClass = clickable ? 'cursor-pointer' : '';

  return (
    <div
      className={`
        relative
        rounded-2xl
        shadow-lg
        transition-all duration-300 ease-in-out /* Smooth transitions for hover */
        overflow-hidden
        bg-white bg-opacity-10 
        border border-white border-opacity-40 
        backdrop-filter backdrop-blur-xl backdrop-saturate-150 
        ${hoverClasses} 
        ${cursorClass}
        animate-breathe-light /* Add the subtle breathing light effect */
        ${className} 
      `}
      onClick={onClick}
    >
      {children}
    </div>
  );
};

export default LiquidGlassCard;