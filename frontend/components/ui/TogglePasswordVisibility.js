// frontend/components/ui/TogglePasswordVisibility.js
import React, { useState } from 'react';

/**
 * TogglePasswordVisibility Component
 * This component allows toggling the visibility of a password input field.
 * It ensures the child is an input-like element and correctly manages its type.
 */
const TogglePasswordVisibility = ({ children }) => {
  const [isVisible, setIsVisible] = useState(false);

  // We use React.cloneElement to pass the 'type' prop to the child
  const childWithNewType = React.Children.map(children, child => {
    if (React.isValidElement(child)) {
      const newType = isVisible ? 'text' : 'password';
      return React.cloneElement(child, {
        type: newType, // Set the new type
      });
    }
    return child;
  });

  const toggleVisibility = () => {
    setIsVisible(!isVisible);
  };

  return (
    <div className="relative w-full"> {/* Ensure the container is full width */}
      {childWithNewType}
      <button
        type="button"
        onClick={toggleVisibility}
        className="
          absolute inset-y-0 right-0 pr-3 flex items-center 
          text-gray-400
          focus:outline-none focus:ring-2 focus:ring-primary focus:ring-opacity-75
          transition-all duration-200
        "
        aria-label={isVisible ? "Hide password" : "Show password"}
      >
        {/* Eye and Slashed Eye Icons */}
        {isVisible ? (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
            <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057 .458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
            <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057 .458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
            <path d="M13.82 10.155a4 4 0 01-5.65 0L6.464 8.956l1.37-1.37a.5.5 0 00-.708-.708L5.756 8.24a.5.5 0 000 .707l1.414 1.414a6 6 0 008.485 0L15.932 9.42l-1.414 1.414a.5.5 0 00-.707-.707z" />
          </svg>
        )}
      </button>
    </div>
  );
};

export default TogglePasswordVisibility;