// frontend/pages/_app.js
import "@/styles/globals.css";
import { SessionProvider } from '../contexts/SessionContext';
import MainLayout from '../components/layouts/MainLayout';
import { useRouter } from 'next/router';

export default function App({ Component, pageProps }) {
  const router = useRouter();

  const isAuthPage = ['/login', '/register', '/forgot-password'].includes(router.pathname);

  return (
    <SessionProvider>
      <MainLayout isAuthPage={isAuthPage}>
        <Component {...pageProps} />
      </MainLayout>
    </SessionProvider>
  );
}