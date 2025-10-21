// frontend/components/ui/InputField.js
import React, { useState } from 'react';
import { FaEye, FaEyeSlash } from 'react-icons/fa'; // 确保你已安装 react-icons

/**
 * InputField component
 * This component provides a styled input field. It handles password visibility
 * internally if the type is 'password'.
 */
const InputField = ({
  label,
  type = 'text',
  name,
  value,
  onChange,
  placeholder,
  className = '',
  required = false,
  error = null
}) => {
  // Use state to manage password visibility for 'password' type inputs
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const isPasswordInput = type === 'password';

  // Determine the input type to render
  const inputType = isPasswordInput && isPasswordVisible ? 'text' : type;

  const togglePasswordVisibility = () => {
    setIsPasswordVisible(!isPasswordVisible);
  };

  return (
    <div className={`mb-4 ${className}`}>
      <label htmlFor={name} className="block text-gray-200 text-sm font-bold mb-2">
        {label}
        {required && <span className="text-red-600 ml-1">*</span>}
      </label>
      
      {/* This relative container is crucial for the absolute positioning of the icon */}
      <div className="relative">
        <input
          id={name}
          type={inputType}
          name={name}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          required={required}
          className={`
            shadow-lg appearance-none border rounded-xl w-full py-3 px-4
            text-gray-100 leading-tight
            focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary-light
            bg-white bg-opacity-5 backdrop-filter backdrop-blur-sm
            transition-all-ease
            ${error ? 'border-red-600 focus:ring-red-600' : 'border-gray-600'}
            ${isPasswordInput ? 'pr-10' : ''}  /* Add padding to the right for password inputs */
          `}
        />
        
        {/* Only render the toggle button for password inputs */}
        {isPasswordInput && (
          <button
            type="button"
            onClick={togglePasswordVisibility}
            className="
              absolute right-0 top-1/2 transform -translate-y-1/2 pr-3 flex items-center 
              text-gray-400
              focus:outline-none focus:ring-2 focus:ring-primary focus:ring-opacity-75
              transition-all duration-200
            "
            aria-label={isPasswordVisible ? "Hide password" : "Show password"}
          >
            {isPasswordVisible ? (
              <FaEyeSlash className="h-5 w-5" />
            ) : (
              <FaEye className="h-5 w-5" />
            )}
          </button>
        )}
      </div>

      {error && (
        <p className="text-red-400 text-left text-sm mt-1">{error}</p>
      )}
    </div>
  );
};

export default InputField;