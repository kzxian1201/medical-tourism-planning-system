// frontend/pages/index.js
import React, { useContext } from 'react';
import Link from 'next/link';
import LiquidGlassButton from '../components/ui/LiquidGlassButton';
import LiquidGlassCard from '../components/ui/LiquidGlassCard';
import { SessionContext } from '../contexts/SessionContext';
import { SparklesIcon, GlobeAltIcon, CheckCircleIcon } from '@heroicons/react/24/solid';

/**
 * Home Page Component
 * Displays the main landing content of the application.
 */
export default function Home() {
  const { userId, authReady } = useContext(SessionContext);
  const isAuthenticated = authReady && userId;

  return (
    <>
      <section className="flex-grow flex flex-col items-center justify-center text-center px-4 py-20 sm:py-24 md:py-32 lg:py-40 w-full">
        <LiquidGlassCard
          className="max-w-3xl mx-auto w-full p-6 sm:p-8 bg-white bg-opacity-5 backdrop-filter backdrop-blur-lg border border-gray-700 border-opacity-30 shadow-lg rounded-lg animate-breathe-light"
        >
          <div className="text-center space-y-4 flex flex-col items-center">
            <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-extrabold text-gray-50 leading-tight">
              AI-Powered <span className="text-primary">Medical</span> Travel
            </h1>
            <p className="text-lg sm:text-xl md:text-2xl text-gray-300 max-w-2xl">
              Your personalized medical journey, simplified. From consultation to recovery, all in one seamless plan.
            </p>
            <div className="pt-6">
              {isAuthenticated && (
                <Link href="/plan">
                  <LiquidGlassButton className="px-8 py-4 text-lg">
                    Get Started
                  </LiquidGlassButton>
                </Link>
              )}
            </div>
          </div>
        </LiquidGlassCard>
      </section>

      <section className="py-12 px-4 sm:px-6 md:px-8 lg:px-10 w-full">
        <h2 className="text-3xl sm:text-4xl font-bold text-center text-white mb-10">Our Key Selling Points</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {/* Feature Card 1: Intelligent Planning */}
          <LiquidGlassCard className="p-6" clickable={true}>
            <div className="text-center space-y-4 flex flex-col items-center">
              <SparklesIcon className="h-16 w-16 text-primary mb-2" />
              <h3 className="text-xl font-semibold text-gray-50">Intelligent Planning</h3>
              <p className="text-gray-300 text-base">Leverages AI to craft a comprehensive itinerary that perfectly matches your needs.</p>
            </div>
          </LiquidGlassCard>

          {/* Feature Card 2: One-Stop Service */}
          <LiquidGlassCard className="p-6" clickable={true}>
            <div className="text-center space-y-4 flex flex-col items-center">
              <GlobeAltIcon className="h-16 w-16 text-accent mb-2" />
              <h3 className="text-xl font-semibold text-gray-50">One-Stop Service</h3>
              <p className="text-gray-300 text-base">Covers medical appointments, flights, hotels, local transport, and translation – hassle-free.</p>
            </div>
          </LiquidGlassCard>

          {/* Feature Card 3: Personalized Customization */}
          <LiquidGlassCard className="p-6" clickable={true}>
            <div className="text-center space-y-4 flex flex-col items-center">
              <CheckCircleIcon className="h-16 w-16 text-palette-purple-light mb-2" />
              <h3 className="text-xl font-semibold text-gray-50">Personalized Customization</h3>
              <p className="text-gray-300 text-base">Every preference is incorporated into your bespoke plan, ensuring comfort and convenience.</p>
            </div>
          </LiquidGlassCard>
        </div>
      </section>
    </>
  );
}