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
      {/* Outer Glowing Magnetic Aura */}
      <motion.div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: isHovered ? '54px' : '30px',
          height: isHovered ? '54px' : '30px',
          borderRadius: '50%',
          border: isHovered ? '1.5px solid rgba(255, 87, 34, 0.85)' : '1px solid rgba(255, 87, 34, 0.4)',
          backgroundColor: isHovered ? 'rgba(255, 87, 34, 0.12)' : 'rgba(255, 87, 34, 0.03)',
          boxShadow: isHovered ? '0 0 28px rgba(255, 87, 34, 0.55), inset 0 0 12px rgba(255, 87, 34, 0.2)' : '0 0 14px rgba(255, 87, 34, 0.2)',
          pointerEvents: 'none',
          zIndex: 9999,
          transform: 'translate(-50%, -50%)',
          backdropFilter: isHovered ? 'blur(2px)' : 'none',
        }}
        animate={{
          x: mousePosition.x - (isHovered ? 27 : 15),
          y: mousePosition.y - (isHovered ? 27 : 15),
          scale: isClicked ? 0.85 : 1,
        }}
        transition={{ type: 'spring', damping: 28, stiffness: 320, mass: 0.08 }}
      />

      {/* Inner Precision Neon Core Dot */}
      <motion.div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          backgroundColor: '#ff7043',
          boxShadow: '0 0 14px #ff5722, 0 0 4px #ffffff',
          pointerEvents: 'none',
          zIndex: 10000,
          transform: 'translate(-50%, -50%)',
        }}
        animate={{
          x: mousePosition.x - 3.5,
          y: mousePosition.y - 3.5,
          scale: isClicked ? 1.4 : 1,
        }}
        transition={{ type: 'spring', damping: 35, stiffness: 500, mass: 0.04 }}
      />
    </>
  );
}
