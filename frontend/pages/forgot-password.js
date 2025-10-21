// frontend/pages/forgot-password.js
import React, { useState, useContext, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { SessionContext } from '../contexts/SessionContext';
import AuthLayout from '../components/layouts/AuthLayout';
import InputField from '../components/ui/InputField';
import LiquidGlassButton from '../components/ui/LiquidGlassButton';
import LoadingSpinner from '../components/ui/LoadingSpinner';

const ForgotPasswordPage = () => {
  const { sendPasswordResetEmail, authReady, userId } = useContext(SessionContext);
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    if (authReady && userId) {
      router.push('/');
    }
  }, [authReady, userId, router]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMessage('');
    setLoading(true);

    if (!email) {
      setError('Please enter your email address to reset your password!');
      setLoading(false);
      return;
    }

    try {
      const result = await sendPasswordResetEmail(email);

      if (result.success) {
        setSuccessMessage('A password reset link has been sent to your email address!');
      } else {
        setError(result.error || 'Failed to send password reset email!');
      }
    } catch (err) {
      setError(err.message || 'An unexpected error occurred!');
      console.error('Password reset error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <div className="flex items-center justify-center h-screen fixed inset-0">
        <div className="w-full max-w-4xl p-8">
          <div className="bg-gray-800 bg-opacity-50 backdrop-filter backdrop-blur-lg rounded-2xl p-10 border border-gray-700 shadow-xl transition-all duration-300 hover:shadow-2xl hover:border-gray-600 w-full">

            {/* Title + Description */}
            <h1 className="text-4xl sm:text-5xl font-extrabold text-white leading-tight text-center">
              Forgot Your Password?
            </h1>
            <p className="text-lg text-gray-400 mt-2 mb-8 text-center">
              Enter your email and we&apos;ll send you a reset link.
            </p>

            {error && <p className="text-red-400 text-center mb-4">{error}</p>}
            {successMessage && <p className="text-green-400 text-center mb-4">{successMessage}</p>}
            {loading && <LoadingSpinner messageType="forgot-password" />}

            {!loading && (
              <form onSubmit={handleSubmit} className="w-full space-y-4">
                <InputField
                  label="Email Address"
                  type="email"
                  name="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your-email@example.com"
                  autoComplete="email"
                />
                <LiquidGlassButton type="submit" className="w-full" disabled={loading}>
                  Send Reset Link
                </LiquidGlassButton>
              </form>
            )}

            <div className="border-t border-gray-600/40 mt-8 pt-4 text-center text-gray-300">
              Remember your password?{' '}
              <Link href="/login" className="text-primary hover:text-primary-light transition-colors">
                Log In
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AuthLayout>
  );
};

export default ForgotPasswordPage;