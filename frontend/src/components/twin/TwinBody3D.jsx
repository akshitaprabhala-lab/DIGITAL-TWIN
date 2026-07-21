import React, { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

// layer -> shell material config
const LAYER_SHELL = {
  skin: { color: "#E5C8B8", opacity: 0.96, roughness: 0.75 },
  muscle: { color: "#A63D31", opacity: 0.55, roughness: 0.5 },
  skeletal: { color: "#F3F2EE", opacity: 0.28, roughness: 0.4 },
  nervous: { color: "#3a2f52", opacity: 0.3, roughness: 0.5 },
};

// organ anatomical-ish positions + region membership
const ORGAN_LAYOUT = {
  brain: { pos: [0, 2.65, 0.02], r: 0.26, region: "head" },
  thyroid: { pos: [0, 1.98, 0.16], r: 0.09, region: "head" },
  heart: { pos: [-0.16, 1.15, 0.12], r: 0.17, region: "thorax" },
  lungs: { pos: [0.32, 1.2, 0.05], r: 0.19, region: "thorax", mirror: true },
  liver: { pos: [0.26, 0.58, 0.12], r: 0.19, region: "abdomen" },
  pancreas: { pos: [-0.05, 0.46, 0.14], r: 0.12, region: "abdomen" },
  kidneys: { pos: [0.3, 0.35, -0.14], r: 0.11, region: "abdomen", mirror: true },
  blood: { pos: [0, -0.35, 0.05], r: 0.16, region: "pelvis" },
};

const REGION_PARTS = ["head", "thorax", "abdomen", "pelvis", "arms", "legs"];

function Organ({ okey, cfg, out, selected, layer }) {
  const ref = useRef();
  const ref2 = useRef();
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const beat = okey === "heart" ? 1 + Math.sin(t * 6) * 0.06 : 1;
    const glow = out ? 0.55 + Math.sin(t * 3) * 0.35 : 0.0;
    [ref.current, ref2.current].forEach((m) => {
      if (!m) return;
      m.scale.setScalar(beat);
      if (m.material) m.material.emissiveIntensity = glow;
    });
  });
  const visible = layer !== "skin" || selected;
  const color = out ? "#D97706" : selected ? "#0D9488" : "#c98b6b";
  const emissive = out ? "#D97706" : "#0D9488";
  const positions = cfg.mirror
    ? [cfg.pos, [-cfg.pos[0], cfg.pos[1], cfg.pos[2]]]
    : [cfg.pos];
  return (
    <>
      {positions.map((p, i) => (
        <mesh key={i} ref={i === 0 ? ref : ref2} position={p} visible={visible}>
          <sphereGeometry args={[cfg.r, 24, 24]} />
          <meshStandardMaterial
            color={color} emissive={emissive} emissiveIntensity={out ? 0.6 : 0}
            roughness={0.35} metalness={0.1}
            transparent opacity={selected || out ? 0.98 : 0.85}
          />
        </mesh>
      ))}
    </>
  );
}

function BodyShell({ layer, selectedRegion, onSelectRegion }) {
  const torso = useRef();
  useFrame(({ clock }) => {
    if (torso.current) {
      const s = 1 + Math.sin(clock.getElapsedTime() * 1.1) * 0.02;
      torso.current.scale.set(s, 1, s);
    }
  });
  const shell = LAYER_SHELL[layer] || LAYER_SHELL.skin;

  const mat = (region) => {
    const isSel = selectedRegion === region;
    return (
      <meshStandardMaterial
        color={isSel ? "#0D9488" : shell.color}
        transparent opacity={isSel ? Math.min(1, shell.opacity + 0.15) : shell.opacity}
        roughness={shell.roughness} metalness={0.05}
      />
    );
  };
  const pick = (region) => (e) => { e.stopPropagation(); onSelectRegion(region); };

  return (
    <group>
      {/* head */}
      <mesh position={[0, 2.6, 0]} onClick={pick("head")}>
        <sphereGeometry args={[0.42, 32, 32]} />
        {mat("head")}
      </mesh>
      {/* neck */}
      <mesh position={[0, 2.05, 0]}>
        <cylinderGeometry args={[0.16, 0.19, 0.28, 16]} />
        {mat("head")}
      </mesh>
      {/* thorax */}
      <mesh ref={torso} position={[0, 1.2, 0]} onClick={pick("thorax")}>
        <capsuleGeometry args={[0.52, 0.5, 8, 24]} />
        {mat("thorax")}
      </mesh>
      {/* abdomen */}
      <mesh position={[0, 0.5, 0]} onClick={pick("abdomen")}>
        <capsuleGeometry args={[0.46, 0.32, 8, 24]} />
        {mat("abdomen")}
      </mesh>
      {/* pelvis */}
      <mesh position={[0, -0.25, 0]} onClick={pick("pelvis")}>
        <capsuleGeometry args={[0.44, 0.16, 8, 24]} />
        {mat("pelvis")}
      </mesh>
      {/* arms */}
      {[-1, 1].map((s) => (
        <mesh key={s} position={[s * 0.72, 1.1, 0]} rotation={[0, 0, s * 0.18]} onClick={pick("arms")}>
          <capsuleGeometry args={[0.15, 1.25, 8, 16]} />
          {mat("arms")}
        </mesh>
      ))}
      {/* legs */}
      {[-1, 1].map((s) => (
        <mesh key={s} position={[s * 0.24, -1.35, 0]} onClick={pick("legs")}>
          <capsuleGeometry args={[0.19, 1.5, 8, 16]} />
          {mat("legs")}
        </mesh>
      ))}
    </group>
  );
}

export default function TwinBody3D({ layer = "skin", organStatus = {}, selectedRegion, onSelectRegion }) {
  const organs = useMemo(() => Object.entries(ORGAN_LAYOUT), []);
  return (
    <Canvas
      camera={{ position: [0, 0.8, 6.2], fov: 42 }}
      dpr={[1, 1.8]}
      gl={{ antialias: true }}
      data-testid="twin-canvas"
    >
      <color attach="background" args={["#0A0A0B"]} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[3, 5, 4]} intensity={1.1} />
      <pointLight position={[-4, 2, 3]} intensity={0.6} color="#0D9488" />
      <pointLight position={[4, -2, 2]} intensity={0.4} color="#D97706" />
      <group position={[0, -0.3, 0]}>
        <BodyShell layer={layer} selectedRegion={selectedRegion} onSelectRegion={onSelectRegion} />
        {organs.map(([okey, cfg]) => {
          const out = organStatus[okey] === "out";
          const selected = selectedRegion && cfg.region === selectedRegion;
          return <Organ key={okey} okey={okey} cfg={cfg} out={out} selected={selected} layer={layer} />;
        })}
      </group>
      <OrbitControls enablePan={false} minDistance={4} maxDistance={9}
        minPolarAngle={Math.PI / 4} maxPolarAngle={Math.PI / 1.7} />
    </Canvas>
  );
}

export { REGION_PARTS, ORGAN_LAYOUT };
