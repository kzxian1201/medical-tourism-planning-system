// frontend/components/ui/SingleSelectPillBoxField.js
import React from 'react';

/**
 * SingleSelectPillBoxField Component
 * This component renders a group of options as clickable pills/boxes, allowing only one selection at a time.
 * It now includes subtle hover effects and an optional pulse animation on selection for enhanced "breathing" feel.
 *
 * @param {object} props - Component props.
 * @param {string} props.label - The label for the selection group.
 * @param {Array<{value: string | number, label: string}>} props.options - An array of objects, each representing an option.
 * @param {string | number | null} props.value - The currently selected option's value. Null if no option is selected.
 * @param {(newValue: string | number) => void} props.onChange - Callback function triggered when an option is selected.
 * @param {string} [props.className=''] - Additional CSS classes for the container div.
 * @param {boolean} [props.required=false] - Indicates if a selection is required.
 */
const SingleSelectPillBoxField = ({ label, options, value, onChange, className = '', required = false }) => {
  // State to trigger the pulse animation only when a new item is selected
  const [animatePulse, setAnimatePulse] = React.useState(null);

  const handleOptionClick = (optionValue) => {
    // Only trigger onChange if a new value is selected to prevent unnecessary re-renders
    if (value !== optionValue) {
      onChange(optionValue);
      setAnimatePulse(optionValue); // Set the value to trigger animation for this specific pill
    }
  };

  // Reset animatePulse state after animation completes to allow re-triggering
  React.useEffect(() => {
    if (animatePulse) {
      const timer = setTimeout(() => {
        setAnimatePulse(null);
      }, 300); // Duration of 'pulse-select' animation
      return () => clearTimeout(timer);
    }
  }, [animatePulse]);

  return (
    <div className={`mb-4 ${className}`}>
      <label className="block text-gray-200 text-sm font-bold mb-2">
        {label}
        {required && <span className="text-red-600 ml-1">*</span>}
      </label>
      <div className="flex flex-wrap gap-3"> {/* Flex container for the options with spacing */}
        {options.map((option, index) => {
          const isSelected = value === option.value;
          const shouldAnimate = animatePulse === option.value;

          return (
            <div
              key={`${option.value}-${index}`}
              // Applying Tailwind classes directly here
              className={`
                inline-flex items-center justify-center px-6 py-3 rounded-xl cursor-pointer
                bg-gray-700 text-gray-200 border border-gray-600 
                transition-all duration-200 ease-in-out /* Unified transition for smooth changes */
                hover:bg-gray-600 hover:border-gray-500 hover:scale-[1.01] /* Subtle scale on hover */
                min-w-[120px] text-center select-none /* Using arbitrary value for min-width */
                ${isSelected 
                  ? 'bg-palette-purple-light border-palette-purple-dark text-white shadow-md transform scale-100' // Selected state
                  : ''
                }
                ${isSelected 
                  ? 'hover:bg-palette-purple-lighten hover:border-palette-purple-darker hover:scale-[1.02]' // Hover for selected state
                  : ''
                }
                ${shouldAnimate ? 'animate-pulse-select' : ''} /* Apply pulse animation only when triggered */
              `}
              onClick={() => handleOptionClick(option.value)}
              role="radio" // ARIA role for single-select group
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

export default SingleSelectPillBoxField;