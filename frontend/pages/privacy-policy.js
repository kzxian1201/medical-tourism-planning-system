// frontend/pages/privacy-policy.js
import React from 'react';
import LiquidGlassCard from '../components/ui/LiquidGlassCard';

const PrivacyPolicyPage = () => {
  return (
      <div className="flex-grow flex items-center justify-center py-10 px-4 sm:px-6 lg:px-8">
        <LiquidGlassCard className="max-w-4xl w-full p-8 space-y-8">
          <h1 className="text-4xl font-bold text-center text-gray-50">Privacy Policy</h1>
          <p className="text-sm text-gray-400 text-center">Last updated: August 26, 2025</p>

          <section className="space-y-4 text-gray-300">
            <p>
              This Privacy Policy describes how your personal and health information is collected, used, and disclosed by our AI-based medical tourism planning system (the “System”). We are committed to protecting your privacy and ensuring the confidentiality of your personal data.
            </p>

            <h2 className="text-2xl font-semibold text-gray-50">1. Information We Collect</h2>
            <p>
              To provide personalized recommendations and planning, we collect the following types of information, with your explicit consent:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li>
                **Personal Information:** Your email address (for account creation), and optionally, your name, nationality, and contact details.
              </li>
              <li>
                **Health Information:** Information related to your medical purpose, estimated budget for medical care, and other relevant health conditions or history that you choose to provide. This sensitive data is used solely to generate tailored planning advice.
              </li>
              <li>
                **Usage Data:** Information about how you interact with the System, such as your search queries and preferences.
              </li>
            </ul>

            <h2 className="text-2xl font-semibold text-gray-50">2. How We Use Your Information</h2>
            <p>Your information is used to:</p>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li>
                Provide you with a personalized and intelligent medical travel plan.
              </li>
              <li>
                Improve the accuracy and relevance of our AI recommendations.
              </li>
              <li>
                Communicate with you regarding your account and plans.
              </li>
              <li>
                Maintain the security and integrity of the System.
              </li>
            </ul>

            <h2 className="text-2xl font-semibold text-gray-50">3. Data Sharing and Disclosure</h2>
            <p>
              We do not share your personal health information with third parties without your direct consent. Our system may provide you with links to external, reputable websites (e.g., hospitals, airlines). By clicking on these links, you will be subject to the privacy policies of those external sites. We are not responsible for the privacy practices of external websites.
            </p>

            <h2 className="text-2xl font-semibold text-gray-50">4. Data Security</h2>
            <p>
              We use secure Firebase services to store your data. While we strive to protect your personal information, no method of transmission over the Internet is 100% secure.
            </p>

            <h2 className="text-2xl font-semibold text-gray-50">5. Your Rights</h2>
            <p>
              You have the right to access, update, and delete your personal information and account at any time. You can manage this through your profile settings.
            </p>
          </section>
        </LiquidGlassCard>
      </div>
  );
};

export default PrivacyPolicyPage;