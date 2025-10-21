// frontend/components/layout/Footer.js
import React from 'react';
import Link from 'next/link';

const Footer = () => {
  return (
    <footer className="w-full py-6 px-4 sm:px-6 md:px-8 lg:px-10
                       bg-white bg-opacity-5 backdrop-filter backdrop-blur-lg
                       border-t border-gray-700 border-opacity-30 shadow-lg
                       text-gray-400 text-sm text-center">
      <div className="container mx-auto flex flex-col items-center">
        {/* Company Name on its own line */}
        <p className="mb-2">&copy; {new Date().getFullYear()} GoCare AI. All rights reserved.</p>
        
        {/* Links on a separate line, centered */}
        <div className="flex space-x-4">
          <Link href="/privacy-policy" passHref className="text-primary hover:text-primary-light transition-colors">
            Privacy Policy
          </Link>
          <Link href="/terms-of-service" passHref className="text-primary hover:text-primary-light transition-colors">
            Terms of Service
          </Link>
        </div>
      </div>
    </footer>
  );
};

export default Footer;