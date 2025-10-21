// frontend/components/layouts/MainLayout.js
import React, { useState, useEffect, useRef } from 'react';
import Header from '../layouts/header';
import Footer from '../layouts/footer';

const wallpapers = [
  { path: '/wallpapers/wallpaper1.jpg', lightColor: 'rgba(106, 139, 255, 0.25)' },
  { path: '/wallpapers/wallpaper2.jpg', lightColor: 'rgba(106, 139, 255, 0.25)' },
  { path: '/wallpapers/wallpaper3.jpg', lightColor: 'rgba(106, 139, 255, 0.25)' },
  { path: '/wallpapers/wallpaper4.jpg', lightColor: 'rgba(106, 139, 255, 0.25)' },
  { path: '/wallpapers/wallpaper5.jpg', lightColor: 'rgba(106, 139, 255, 0.25)' },
  { path: '/wallpapers/wallpaper6.jpg', lightColor: 'rgba(106, 139, 255, 0.25)' },
];

/**
 * MainLayout Component
 * This is the primary layout for the application, providing a consistent
 * global background, full viewport height, and includes the Header and Footer.
 * It can conditionally hide Header and Footer based on props.
 */
const MainLayout = ({ children, isAuthPage }) => {
  const [currentWallpaper, setCurrentWallpaper] = useState('');
  const [currentLightColor, setCurrentLightColor] = useState('rgba(106, 139, 255, 0.25)');
  const layoutRef = useRef(null);

  useEffect(() => {
    const selectedWallpaper = wallpapers[Math.floor(Math.random() * wallpapers.length)];
    setCurrentWallpaper(selectedWallpaper.path);
    setCurrentLightColor(selectedWallpaper.lightColor);

    const handleMouseMove = (e) => {
      if (layoutRef.current) {
        layoutRef.current.style.setProperty('--mouse-x', `${e.clientX}px`);
        layoutRef.current.style.setProperty('--mouse-y', `${e.clientY}px`);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <div
      ref={layoutRef}
      className="min-h-screen flex flex-col font-inter text-gray-100"
      style={{
        backgroundImage: `
          radial-gradient(circle at var(--mouse-x, 50%) var(--mouse-y, 50%), ${currentLightColor} 0%, transparent 35%),
          radial-gradient(at 15% 25%, rgba(106, 139, 255, 0.2) 0%, transparent 60%),
          radial-gradient(at 85% 75%, rgba(156, 122, 255, 0.2) 0%, transparent 60%),
          linear-gradient(to bottom, rgba(26, 32, 44, 0.6), rgba(45, 55, 72, 0.6)),
          url(${currentWallpaper})
        `,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundAttachment: 'fixed',
      }}
    >
      {/* Conditionally render Header */}
      {!isAuthPage && <Header />}
      
      <main className="flex-1 flex flex-col items-center justify-start p-4 md:p-8 overflow-y-auto">
        {children}
      </main>

      {/* Conditionally render Footer */}
      {!isAuthPage && <Footer />}
    </div>
  );
};

export default MainLayout;