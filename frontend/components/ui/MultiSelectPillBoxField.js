// frontend/components/ui/MultiSelectPillBoxField.js
import React, { useState, useEffect } from 'react';

/**
 * MultiSelectPillBoxField Component
 * This component renders a group of options as clickable pills/boxes, allowing multiple selections.
 * It now includes subtle hover effects and an optional pulse animation on selection/deselection
 * for enhanced "breathing" feel.
 *
 * @param {object} props - Component props.
 * @param {string} props.label - The label for the selection group.
 * @param {Array<{value: string | number, label: string}>} props.options - An array of objects, each representing an option.
 * @param {Array<string | number>} props.values - An array of currently selected option values.
 * @param {(newValues: Array<string | number>) => void} props.onChange - Callback function triggered when options are selected/deselected.
 * @param {string} [props.className=''] - Additional CSS classes for the container div.
 * @param {boolean} [props.required=false] - Indicates if at least one selection is required.
 */
const MultiSelectPillBoxField = ({ label, options, values, onChange, className = '', required = false }) => {
  // State to track which pill should animate. Can be a single value or an array if multiple animate concurrently
  // For multi-select, it's usually best to animate only the specific pill clicked.
  const [animatePulseFor, setAnimatePulseFor] = useState(null); // Stores the value of the pill to animate

  const handleOptionClick = (optionValue) => {
    const isSelected = values.includes(optionValue);
    let newValues;

    if (isSelected) {
      // If already selected, remove it from the array
      newValues = values.filter((val) => val !== optionValue);
    } else {
      // If not selected, add it to the array
      newValues = [...values, optionValue];
    }
    onChange(newValues);

    // Trigger the pulse animation for the clicked pill
    setAnimatePulseFor(optionValue);
  };

  // Reset animatePulseFor state after animation completes
  useEffect(() => {
    if (animatePulseFor !== null) {
      const timer = setTimeout(() => {
        setAnimatePulseFor(null);
      }, 300); // Duration of 'pulse-select' animation
      return () => clearTimeout(timer);
    }
  }, [animatePulseFor]); // Only re-run if animatePulseFor changes

  return (
    <div className={`mb-4 ${className}`}>
      <label className="block text-gray-200 text-sm font-bold mb-2">
        {label}
        {required && <span className="text-red-600 ml-1">*</span>}
      </label>
      <div className="flex flex-wrap gap-3"> {/* Flex container for the options with spacing */}
        {options.map((option) => {
          const isSelected = values.includes(option.value);
          const shouldAnimate = animatePulseFor === option.value; // Check if this specific pill should animate

          return (
            <div
              key={option.value}
              // Applying Tailwind classes directly here
              className={`
                inline-flex items-center justify-center px-6 py-3 rounded-xl cursor-pointer
                bg-gray-700 text-gray-200 border border-gray-600 
                transition-all duration-200 ease-in-out /* Unified transition for smooth changes */
                hover:bg-gray-600 hover:border-gray-500 hover:scale-[1.01] /* Subtle scale on hover */
                min-w-[120px] text-center select-none
                ${isSelected 
                  ? 'bg-palette-purple-light border-palette-purple-dark text-white shadow-md transform scale-100' // Selected state
                  : ''
                }
                ${isSelected 
                  ? 'hover:bg-palette-purple-lighten hover:border-palette-purple-darker hover:scale-[1.02]' // Slightly more scale for selected hover
                  : ''
                }
                ${shouldAnimate ? 'animate-pulse-select' : ''} /* Apply pulse animation only when triggered */
              `}
              onClick={() => handleOptionClick(option.value)}
              role="checkbox" // ARIA role for multi-select group
              aria-checked={isSelected}
              tabIndex={0} // Make div focusable
              onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault(); // Prevent default scroll behavior for space key
                      handleOptionClick(option.value);
                  }
              }}
            >
              {option.label}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MultiSelectPillBoxField;