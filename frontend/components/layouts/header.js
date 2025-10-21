// frontend/components/layout/Header.js
import React, { useContext, useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { SessionContext } from '../../contexts/SessionContext';
import { UserCircleIcon, Bars3Icon, XMarkIcon } from '@heroicons/react/24/solid';

/**
 * Header Component
 * Provides consistent top navigation for the application.
 * Dynamically displays links based on user authentication status and current route.
 * It uses a subtle glassmorphism effect for its background.
 */
const Header = () => {
  // Access authentication state from SessionContext
  const { userId, userEmail, authReady, signOut } = useContext(SessionContext);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const router = useRouter();

  // Determine if the user is authenticated
  const isAuthenticated = authReady && userId;

  // Determine if the "Get Started" link should be shown
  // It should not be shown if the user is already on the /plan page
  const showGetStartedLink = router.pathname !== '/plan';

  return (
    // Header container with glassmorphism effect
    <header className="w-full py-4 px-4 sm:px-6 md:px-8 lg:px-10 sticky top-0 z-40
                       bg-white bg-opacity-5 backdrop-filter backdrop-blur-lg
                       border-b border-gray-700 border-opacity-30 shadow-lg transition-all-ease">
      <div className="max-w-7xl mx-auto flex justify-between items-center">
        {/* Logo/Brand Name */}
        <Link href="/" className="flex items-center space-x-2 text-xl sm:text-2xl font-bold text-gray-50">
          <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
          </svg>
          <span className="text-palette-blue-light">GoCare</span>
          <span className="text-white">AI</span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center space-x-8">
          {authReady && (
            <>
              {isAuthenticated ? (
                <>
                  {showGetStartedLink && (
                    <Link href="/plan" className="px-6 py-3 rounded-full text-white font-semibold transition-transform duration-300 transform hover:scale-105"
                          style={{
                            background: `linear-gradient(135deg, rgba(144, 202, 249, 0.2), rgba(100, 116, 139, 0.2))`
                          }}>
                      Start New Plan
                    </Link>
                  )}
                  <Link href="/plan/history" className="text-gray-300 hover:text-white transition-colors">
                    My Plans
                  </Link>
                  <Link href="/profile" className="text-gray-300 hover:text-white transition-colors flex items-center space-x-1">
                    <UserCircleIcon className="h-6 w-6" />
                    <span>Profile</span>
                  </Link>
                  <button
                    onClick={signOut}
                    className="text-gray-300 hover:text-white transition-colors"
                  >
                    Sign Out
                  </button>
                </>
              ) : (
                <>
                  <Link href="/login" className="text-gray-300 hover:text-white transition-colors">
                    Login
                  </Link>
                  <Link href="/register" className="bg-primary hover:bg-primary-dark text-white px-6 py-3 rounded-full transition-colors">
                    Register
                  </Link>
                </>
              )}
            </>
          )}
        </nav>

        {/* Mobile Menu Button */}
        <div className="md:hidden flex items-center">
          <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="text-gray-300">
            {isMobileMenuOpen ? (
              <XMarkIcon className="h-8 w-8" />
            ) : (
              <Bars3Icon className="h-8 w-8" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Navigation */}
      {isMobileMenuOpen && (
        <div className="md:hidden mt-4">
          <ul className="flex flex-col space-y-4 text-left">
            {authReady && (
              <>
                {isAuthenticated ? (
                  <>
                    {showGetStartedLink && (
                      <li>
                        <Link href="/plan" className="w-full text-left bg-primary hover:bg-primary-dark text-white px-6 py-3 rounded-full transition-colors block" onClick={() => setIsMobileMenuOpen(false)}>
                          Start New Plan
                        </Link>
                      </li>
                    )}
                    <li>
                      <Link href="/plan/history" className="text-gray-300 hover:text-white transition-colors w-full text-left block" onClick={() => setIsMobileMenuOpen(false)}>
                        My Plans
                      </Link>
                    </li>
                    <li>
                      <Link href="/profile" className="text-gray-300 hover:text-white transition-colors w-full text-left block" onClick={() => setIsMobileMenuOpen(false)}>
                        My Profile
                      </Link>
                    </li>
                    <li>
                      <button
                        onClick={() => { signOut(); setIsMobileMenuOpen(false); }}
                        className="text-gray-300 hover:text-white transition-colors w-full text-left"
                      >
                        Sign Out
                      </button>
                    </li>
                  </>
                ) : (
                  <>
                    <li>
                      <Link href="/login" className="text-gray-300 hover:text-white transition-colors" onClick={() => setIsMobileMenuOpen(false)}>
                        Login
                      </Link>
                    </li>
                    <li>
                      <Link href="/register" className="bg-primary hover:bg-primary-dark text-white px-6 py-3 rounded-full transition-colors" onClick={() => setIsMobileMenuOpen(false)}>
                        Register
                      </Link>
                    </li>
                  </>
                )}
              </>
            )}
          </ul>
        </div>
      )}
    </header>
  );
};

export default Header;