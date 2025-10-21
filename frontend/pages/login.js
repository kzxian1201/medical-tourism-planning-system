// frontend/pages/login.js
import React, { useState, useContext, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { SessionContext } from '../contexts/SessionContext';
import AuthLayout from '../components/layouts/AuthLayout';
import InputField from '../components/ui/InputField';
import LiquidGlassButton from '../components/ui/LiquidGlassButton';
import LoadingSpinner from '../components/ui/LoadingSpinner';

const LoginPage = () => {
  const { signIn, authReady, userId } = useContext(SessionContext);
  const router = useRouter();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [formErrors, setFormErrors] = useState({});
  const [loading, setLoading] = useState(false);

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

  const handleLogin = async (e) => {
    e?.preventDefault();
    setFormErrors({});
    setLoading(true);
    
    let hasError = false;
    const newErrors = {};

    if (!formData.email) {
      newErrors.email = 'Email address is required!';
      hasError = true;
    }

    if (!formData.password) {
      newErrors.password = 'Password is required!';
      hasError = true;
    }

    if (hasError) {
      setFormErrors(newErrors);
      setLoading(false);
      return;
    }

    try {
      const result = await signIn(formData.email, formData.password);
      if (!result.success) {
        setFormErrors({ general: result.error });
      }
    } catch (err) {
      setFormErrors({ general: 'An unexpected error occurred!' });
      console.error('Login error:', err);
    } finally {
      setLoading(false);
    }
  };

return (
    <AuthLayout>
        <div className="flex items-center justify-center h-screen fixed inset-0">
            <div className="w-full max-w-4xl p-8">
                <div className="bg-gray-800 bg-opacity-50 backdrop-filter backdrop-blur-lg rounded-2xl p-10 border border-gray-700 shadow-xl transition-all duration-300 hover:shadow-2xl hover:border-gray-600 w-full">
                    
                    <h1 className="text-4xl sm:text-5xl font-extrabold text-white leading-tight text-center">
                        Welcome Back!
                    </h1>
                    <p className="text-lg text-gray-400 mt-2 mb-8 text-center">
                        Sign in to access your medical travel plans.
                    </p>


                    {formErrors.general && <p className="text-red-400 text-center mb-4">{formErrors.general}</p>}
                    {loading && <LoadingSpinner messageType="login" />}

                    {!loading && (
                        <form onSubmit={handleLogin} className="w-full space-y-4">
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
                                autoComplete="current-password"
                            />
                            {formErrors.password && (
                                        <p className="text-red-400 text-left text-sm mt-1">{formErrors.password}</p>
                            )}
                            <div className="text-right pt-2">
                                <Link href="/forgot-password" className="text-sm text-primary hover:text-primary-light transition-colors">
                                    Forgot Password?
                                </Link>
                            </div>
                            <LiquidGlassButton type="submit" className="w-full mt-6" disabled={loading}>
                                Log In
                            </LiquidGlassButton>
                        </form>
                    )}

                    <div className="border-t border-gray-600/40 mt-8 pt-4 text-center text-gray-300">
                        Don&apos;t have an account?{' '}
                        <Link href="/register" className="text-primary hover:text-primary-light transition-colors">
                            Sign Up
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    </AuthLayout>
);
};

export default LoginPage;