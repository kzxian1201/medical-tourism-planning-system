// frontend/components/ui/LiquidGlassButton.js
import React, { forwardRef } from 'react';

/**
 * LiquidGlassButton Component
 * A styled button with a liquid glass effect, hover animations, and pulse effect.
 * Now includes an explicit `type` prop for better form semantics.
 */
const LiquidGlassButton = forwardRef(({
  children,
  onClick,
  className = '',
  disabled = false,
  type = 'button', // Added type prop with default 'button'
  ...props
}, ref) => {
  return (
    <button
      ref={ref}
      onClick={onClick}
      disabled={disabled}
      type={type} // Pass type prop to button
      className={`
        relative
        bg-primary bg-opacity-50
        border border-opacity-50 border-primary-light
        text-white font-semibold
        py-3 px-6
        rounded-xl
        shadow-lg
        transition-all duration-300
        hover:bg-opacity-90 hover:shadow-xl
        active:scale-95
        focus:outline-none focus:ring-2 focus:ring-primary-dark focus:ring-opacity-75
        animate-pulse-subtle /* Add subtle pulse effect here */
        ${className}
        ${disabled ? 'opacity-50 cursor-not-allowed animate-none' : ''} /* Disable pulse when disabled */
      `}
      {...props}
    >
      {children}
    </button>
  );
});

LiquidGlassButton.displayName = 'LiquidGlassButton';
export default LiquidGlassButton;