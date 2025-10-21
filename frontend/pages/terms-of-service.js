// frontend/pages/terms-of-service.js
import React from 'react';
import LiquidGlassCard from '../components/ui/LiquidGlassCard';

const TermsOfServicePage = () => {
  return (
      <div className="flex-grow flex items-center justify-center py-10 px-4 sm:px-6 lg:px-8">
        <LiquidGlassCard className="max-w-4xl w-full p-8 space-y-8">
          <h1 className="text-4xl font-bold text-center text-gray-50">Terms of Service</h1>
          <p className="text-sm text-gray-400 text-center">Last updated: August 26, 2025</p>

          <section className="space-y-4 text-gray-300">
            <h2 className="text-2xl font-semibold text-gray-50">1. Nature of the Service</h2>
            <p>
              This System is an AI-powered planning and decision-support tool. The information and recommendations provided are for informational purposes only and are designed to assist you in making informed decisions about your medical travel.
            </p>
            <p>
              **The System does not provide medical advice.** Always consult with a qualified healthcare professional for medical advice, diagnosis, or treatment.
            </p>

            <h2 className="text-2xl font-semibold text-gray-50">2. No Liability</h2>
            <p>
              The System is not liable for any medical outcomes, travel arrangements, or any other consequences resulting from the use of its recommendations. You are solely responsible for verifying the accuracy of information and for all bookings and payments made with external providers.
            </p>

            <h2 className="text-2xl font-semibold text-gray-50">3. User Responsibilities</h2>
            <p>
              You agree to use the System responsibly and to provide accurate and truthful information. You are solely responsible for maintaining the confidentiality of your account password.
            </p>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li>
                You must not use the System to handle emergency medical situations.
              </li>
              <li>
                You must not use the System for any illegal or unauthorized purpose.
              </li>
            </ul>

            <h2 className="text-2xl font-semibold text-gray-50">4. External Links</h2>
            <p>
              The System contains links to third-party websites. We have no control over, and assume no responsibility for, the content, privacy policies, or practices of any third-party sites or services.
            </p>
          </section>
        </LiquidGlassCard>
      </div>
  );
};

export default TermsOfServicePage;