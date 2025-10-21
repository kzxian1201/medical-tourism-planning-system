// frontend/components/layouts/AuthLayout.js
import React from 'react';

// AuthLayout Component
// This layout is specifically for authentication pages (Login, Register).
// It provides a centered container with a liquid glass card for auth forms.
const AuthLayout = ({ children }) => {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 font-inter">
      <div className="liquid-glass-card relative p-8 max-w-md w-full">
        {children}
      </div>
    </div>
  );
};

export default AuthLayout;