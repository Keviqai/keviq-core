'use client';

import Image from 'next/image';

interface LogoBrandProps {
  size?: 'sm' | 'md' | 'lg';
  showSlogan?: boolean;
  animated?: boolean;
}

const sizes = {
  sm: { icon: 28, title: 14, slogan: 10 },
  md: { icon: 48, title: 22, slogan: 12 },
  lg: { icon: 64, title: 28, slogan: 14 },
};

export function LogoBrand({ size = 'md', showSlogan = false, animated = false }: LogoBrandProps) {
  const s = sizes[size];
  const iconSize = animated ? Math.round(s.icon * 1.8) : s.icon;
  const iconSrc = animated ? '/welcome.gif' : '/logo.png';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: size === 'sm' ? 4 : 8 }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={iconSrc} alt="Keviq Core" width={iconSize} height={iconSize} style={{ objectFit: 'contain' }} />
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: s.title, fontWeight: 700, letterSpacing: '0.05em', color: '#1e293b' }}>
          KEVIQ CORE
        </div>
        {showSlogan && (
          <div style={{ fontSize: s.slogan, color: '#64748b', marginTop: 2 }}>
            Built for Autonomous Agents
          </div>
        )}
      </div>
    </div>
  );
}

export function LogoIcon({ size = 28 }: { size?: number }) {
  return <Image src="/logo.png" alt="Keviq Core" width={size} height={size} />;
}
