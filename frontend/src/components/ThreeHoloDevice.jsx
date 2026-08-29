import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function ThreeHoloDevice({
  stressLevel = 60,
  urgency = 50,
  touchType = 'taps',
  height = '420px',
}) {
  const mountRef = useRef(null);
  const touchPointsRef = useRef([]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Scene & Camera
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      42,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.set(0, 0, 16);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    // 1. Phone Body Chassis (Rounded Box)
    const phoneGeo = new THREE.BoxGeometry(5.2, 9.8, 0.5, 8, 16, 2);
    const phoneMat = new THREE.MeshStandardMaterial({
      color: 0x10172a,
      metalness: 0.85,
      roughness: 0.25,
    });
    const phoneMesh = new THREE.Mesh(phoneGeo, phoneMat);
    group.add(phoneMesh);

    // Phone Edge Bezel Rim (Soft Amber Glow)
    const rimGeo = new THREE.BoxGeometry(5.35, 9.95, 0.46, 8, 16, 2);
    const rimMat = new THREE.MeshBasicMaterial({
      color: 0xfb923c,
      wireframe: true,
      transparent: true,
      opacity: 0.4,
    });
    const rimMesh = new THREE.Mesh(rimGeo, rimMat);
    group.add(rimMesh);

    // 2. Interactive Screen Mesh
    const screenGeo = new THREE.PlaneGeometry(4.7, 9.1, 24, 48);
    const screenMat = new THREE.MeshStandardMaterial({
      color: 0x090d18,
      emissive: 0x151220,
      roughness: 0.15,
      metalness: 0.2,
      side: THREE.DoubleSide,
    });
    const screenMesh = new THREE.Mesh(screenGeo, screenMat);
    screenMesh.position.z = 0.26;
    group.add(screenMesh);

    // 3. Dynamic Screen Grid Wireframe Overlay (Peach / Amber)
    const gridMat = new THREE.MeshBasicMaterial({
      color: 0xfdba74,
      wireframe: true,
      transparent: true,
      opacity: 0.22,
    });
    const gridMesh = new THREE.Mesh(screenGeo, gridMat);
    gridMesh.position.z = 0.27;
    group.add(gridMesh);

    // 4. Touch Wave Rings Group
    const wavesGroup = new THREE.Group();
    wavesGroup.position.z = 0.28;
    group.add(wavesGroup);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const primaryLight = new THREE.PointLight(0xfb923c, 2.2, 40);
    primaryLight.position.set(6, 8, 10);
    scene.add(primaryLight);

    const cyanLight = new THREE.PointLight(0x38bdf8, 1.8, 40);
    cyanLight.position.set(-6, -8, 10);
    scene.add(cyanLight);

    // Mouse Parallax & Drag Rotation
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;
    let rotX = 0.1;
    let rotY = -0.15;
    let targetRotX = 0.1;
    let targetRotY = -0.15;

    const onMouseDown = (e) => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const onMouseMove = (e) => {
      if (isDragging) {
        const deltaX = e.clientX - prevMouseX;
        const deltaY = e.clientY - prevMouseY;
        targetRotY += deltaX * 0.008;
        targetRotX += deltaY * 0.008;
        prevMouseX = e.clientX;
        prevMouseY = e.clientY;
      }
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    // Click to emit touch ripple
    const onClick = (e) => {
      const rect = container.getBoundingClientRect();
      const clickX = ((e.clientX - rect.left) / rect.width - 0.5) * 4.2;
      const clickY = -((e.clientY - rect.top) / rect.height - 0.5) * 8.4;

      const rippleGeo = new THREE.RingGeometry(0.05, 0.18, 32);
      const rippleMat = new THREE.MeshBasicMaterial({
        color: stressLevel > 70 ? 0xf43f5e : 0xfb923c,
        transparent: true,
        opacity: 0.85,
        side: THREE.DoubleSide,
      });
      const rippleMesh = new THREE.Mesh(rippleGeo, rippleMat);
      rippleMesh.position.set(clickX, clickY, 0.01);
      wavesGroup.add(rippleMesh);

      touchPointsRef.current.push({
        mesh: rippleMesh,
        geo: rippleGeo,
        mat: rippleMat,
        scale: 1,
        opacity: 0.85,
      });
    };

    container.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    container.addEventListener('click', onClick);

    // Resize Handler
    const handleResize = () => {
      if (!container) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);

    // Animation Loop
    let animationFrameId;
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      // Smooth rotation lerp
      rotX += (targetRotX - rotX) * 0.08;
      rotY += (targetRotY - rotY) * 0.08;

      group.rotation.x = rotX + Math.sin(elapsedTime * 1.2) * 0.03;
      group.rotation.y = rotY + Math.cos(elapsedTime * 0.9) * 0.04;
      group.position.y = Math.sin(elapsedTime * 1.5) * 0.15;

      // Update color based on stress
      if (stressLevel > 75) {
        rimMat.color.setHex(0xf43f5e);
        gridMat.color.setHex(0xfb7185);
      } else {
        rimMat.color.setHex(0xfb923c);
        gridMat.color.setHex(0xfdba74);
      }

      // Update touch ripple animations
      for (let i = touchPointsRef.current.length - 1; i >= 0; i--) {
        const item = touchPointsRef.current[i];
        item.scale += 0.08;
        item.opacity -= 0.025;
        item.mesh.scale.set(item.scale, item.scale, 1);
        item.mat.opacity = Math.max(0, item.opacity);

        if (item.opacity <= 0) {
          wavesGroup.remove(item.mesh);
          item.geo.dispose();
          item.mat.dispose();
          touchPointsRef.current.splice(i, 1);
        }
      }

      // Periodically spawn simulated touch ripples when simulation active
      if (Math.random() < 0.04) {
        const randX = (Math.random() - 0.5) * 3.4;
        const randY = (Math.random() - 0.5) * 6.5;
        const simRippleGeo = new THREE.RingGeometry(0.04, 0.14, 32);
        const simRippleMat = new THREE.MeshBasicMaterial({
          color: stressLevel > 70 ? 0xf43f5e : 0xfb923c,
          transparent: true,
          opacity: 0.8,
          side: THREE.DoubleSide,
        });
        const simMesh = new THREE.Mesh(simRippleGeo, simRippleMat);
        simMesh.position.set(randX, randY, 0.01);
        wavesGroup.add(simMesh);

        touchPointsRef.current.push({
          mesh: simMesh,
          geo: simRippleGeo,
          mat: simRippleMat,
          scale: 1,
          opacity: 0.8,
        });
      }

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      container.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      container.removeEventListener('click', onClick);
      window.removeEventListener('resize', handleResize);

      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }

      phoneGeo.dispose();
      phoneMat.dispose();
      rimGeo.dispose();
      rimMat.dispose();
      screenGeo.dispose();
      screenMat.dispose();
      gridMat.dispose();
      renderer.dispose();
    };
  }, [stressLevel, urgency, touchType]);

  return (
    <div
      style={{
        width: '100%',
        height: height,
        position: 'relative',
        cursor: 'grab',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        ref={mountRef}
        style={{
          width: '100%',
          height: '100%',
          position: 'absolute',
          top: 0,
          left: 0,
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '12px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(16, 22, 38, 0.85)',
          padding: '4px 12px',
          borderRadius: '20px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          fontSize: '11px',
          color: 'var(--text-muted)',
          pointerEvents: 'none',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}
      >
        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#fb923c' }} />
        Interactive 3D Mesh • Click/Drag to Inspect
      </div>
    </div>
  );
}
