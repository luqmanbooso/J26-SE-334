import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

export default function CustomCursor() {
  const [mousePosition, setMousePosition] = useState({ x: -100, y: -100 });
  const [isHovered, setIsHovered] = useState(false);
  const [isClicked, setIsClicked] = useState(false);

  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };

    const handleMouseDown = () => setIsClicked(true);
    const handleMouseUp = () => setIsClicked(false);

    const handleMouseOver = (e) => {
      if (e.target.closest('button, a, input, select, .glass-card, .phone-device-3d, .sidebar-button, .nav-link, .chip-item')) {
        setIsHovered(true);
      } else {
        setIsHovered(false);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mouseup', handleMouseUp);
    window.addEventListener('mouseover', handleMouseOver);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('mouseover', handleMouseOver);
    };
  }, []);

  return (
    <>
      {/* Outer Glowing Magnetic Aura (Soft Light Coral/Amber) */}
      <motion.div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: isHovered ? '48px' : '26px',
          height: isHovered ? '48px' : '26px',
          borderRadius: '50%',
          border: isHovered ? '1.5px solid rgba(251, 146, 60, 0.65)' : '1px solid rgba(251, 146, 60, 0.3)',
          backgroundColor: isHovered ? 'rgba(251, 146, 60, 0.08)' : 'rgba(251, 146, 60, 0.02)',
          boxShadow: isHovered ? '0 0 18px rgba(251, 146, 60, 0.35), inset 0 0 8px rgba(251, 146, 60, 0.15)' : '0 0 10px rgba(251, 146, 60, 0.15)',
          pointerEvents: 'none',
          zIndex: 9999,
          transform: 'translate(-50%, -50%)',
          backdropFilter: isHovered ? 'blur(2px)' : 'none',
        }}
        animate={{
          x: mousePosition.x - (isHovered ? 24 : 13),
          y: mousePosition.y - (isHovered ? 24 : 13),
          scale: isClicked ? 0.85 : 1,
        }}
        transition={{ type: 'spring', damping: 28, stiffness: 320, mass: 0.08 }}
      />

      {/* Inner Precision Light Orange Core Dot */}
      <motion.div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: '#fb923c',
          boxShadow: '0 0 10px #fb923c, 0 0 3px #ffffff',
          pointerEvents: 'none',
          zIndex: 10000,
          transform: 'translate(-50%, -50%)',
        }}
        animate={{
          x: mousePosition.x - 3,
          y: mousePosition.y - 3,
          scale: isClicked ? 1.4 : 1,
        }}
        transition={{ type: 'spring', damping: 35, stiffness: 500, mass: 0.04 }}
      />
    </>
  );
}
