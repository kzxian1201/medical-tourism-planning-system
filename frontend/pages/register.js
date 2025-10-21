// frontend/pages/register.js
import React, { useState, useContext, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { SessionContext } from '../contexts/SessionContext';
import AuthLayout from '../components/layouts/AuthLayout';
import InputField from '../components/ui/InputField';
import LiquidGlassButton from '../components/ui/LiquidGlassButton';
import LoadingSpinner from '../components/ui/LoadingSpinner';

const validatePassword = (password) => {
    if (password.length < 8) {
        return "Password must be at least 8 characters long!";
    }
    if (!/[A-Z]/.test(password)) {
        return "Password must contain at least one uppercase letter!";
    }
    if (!/[a-z]/.test(password)) {
        return "Password must contain at least one lowercase letter!";
    }
    if (!/[0-9]/.test(password)) {
        return "Password must contain at least one number!";
    }
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        return "Password must contain at least one special character!";
    }
    return ''; 
};

const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email) ? '' : 'Please enter a valid email address!';
}

const RegisterPage = () => {
  const { register, authReady, userId } = useContext(SessionContext);
  const router = useRouter();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [formErrors, setFormErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [agreedToTerms, setAgreedToTerms] = useState(false);

  useEffect(() => {
    if (authReady && userId) {
      router.push('/');
    }
  }, [authReady, userId, router]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prevData => ({ ...prevData, [name]: value }));
    setFormErrors(prevErrors => ({ ...prevErrors, [name]: '' }));
  };

  const handleRegister = async (e) => {
    e?.preventDefault();
    setFormErrors({});
    setLoading(true);

    let hasError = false;
    const newErrors = {};

    const emailValidationError = validateEmail(formData.email);
    if (emailValidationError) {
        newErrors.email = emailValidationError;
        hasError = true;
    }
    
    const passwordValidationError = validatePassword(formData.password);
    if (passwordValidationError) {
      newErrors.password = passwordValidationError;
      hasError = true;
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match!';
      hasError = true;
    }

    if (!agreedToTerms) {
      newErrors.agreedToTerms = 'You must agree to the Privacy Policy and Terms of Service.';
      hasError = true;
    }

    if (hasError) {
      setFormErrors(newErrors);
      setLoading(false);
      return;
    }

    try {
      const result = await register(formData.email, formData.password);
      if (result.success) {
        router.push('/');
      } else {
        setFormErrors({ general: result.error });
      }
    } catch (err) {
        setFormErrors({ general: 'An unexpected error occurred during registration!' });
        console.error('Registration error:', err);
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
              Create Your Account
            </h1>
            <p className="text-lg text-gray-400 mt-2 mb-8 text-center">
              Join GoCare AI and start planning your medical journey.
            </p>

            {formErrors.general && <p className="text-red-400 text-center mb-4">{formErrors.general}</p>}
            {loading && <LoadingSpinner messageType="register" />}

            {!loading && (
                  <form onSubmit={handleRegister} className="w-full space-y-6">
                    <InputField
                      label="Email Address"
                      type="email"
                      name="email"
                      value={formData.email}
                      onChange={handleChange}
                      placeholder="your-email@example.com"
                      autoComplete="email"
                    />
                    {formErrors.email && (
                      <p className="text-red-400 text-left text-sm mt-1">{formErrors.email}</p>
                    )}

                    <InputField
                      label="Password"
                      type="password"
                      name="password"
                      value={formData.password}
                      onChange={handleChange}
                      placeholder="••••••••"
                      autoComplete="new-password"
                    />
                    {formErrors.password && (
                      <p className="text-red-400 text-left text-sm mt-1">{formErrors.password}</p>
                    )}

                    <InputField
                      label="Confirm Password"
                      type="password"
                      name="confirmPassword"
                      value={formData.confirmPassword}
                      onChange={handleChange}
                      placeholder="••••••••"
                      autoComplete="new-password"
                    />
                    {formErrors.confirmPassword && (
                      <p className="text-red-400 text-left text-sm mt-1">{formErrors.confirmPassword}</p>
                    )}
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="agreedToTerms"
                        checked={agreedToTerms}
                        onChange={(e) => setAgreedToTerms(e.target.checked)}
                        className="form-checkbox text-primary bg-transparent border-gray-500 rounded focus:ring-primary-light"
                      />
                      <label htmlFor="agreedToTerms" className="text-sm text-gray-300 select-none">
                        I agree to the{' '}
                        <Link href="/privacy-policy" passHref className="text-primary hover:underline transition-colors">
                          Privacy Policy
                        </Link>{' '}
                        and{' '}
                        <Link href="/terms-of-service" passHref className="text-primary hover:underline transition-colors">
                          Terms of Service
                        </Link>.
                      </label>
                    </div>
                    {formErrors.agreedToTerms && <p className="text-red-400 text-left text-sm mt-1">{formErrors.agreedToTerms}</p>}
                    
                    <LiquidGlassButton type="submit" className="w-full" disabled={loading}>
                      Register
                    </LiquidGlassButton>
                  </form>
              )}

            <div className="border-t border-gray-600/40 mt-8 pt-4 text-center text-gray-300">
              Already have an account?{' '}
              <Link 
                href="/login" 
                className="text-primary hover:text-primary-light transition-colors"
              >
                Log In
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AuthLayout>
  );
};

export default RegisterPage;