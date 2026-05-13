import * as THREE from 'three';

export function createScene() {
  const root = new THREE.Group();
  root.name = 'desk_lamp';

  // --- Scale factor: millimeters to scene units ---
  const MM = 0.05;

  // --- Dimensions ---
  // Base plate (hexagonal approximation via cylinder)
  const baseSizeMm = 140;
  const baseThickMm = 15;
  const baseRadius = (baseSizeMm * 0.5) * MM;    // 70mm -> 3.5
  const baseHeight = baseThickMm * MM;            // 15mm -> 0.75

  // Arm lower segment
  const armLowerLenMm = 200;
  const armDiamMm = 18;
  const armLowerLen = armLowerLenMm * MM;         // 200mm -> 10.0
  const armRadius = (armDiamMm * 0.5) * MM;       // 9mm -> 0.45

  // Arm upper segment
  const armUpperLenMm = 160;
  const armUpperLen = armUpperLenMm * MM;         // 160mm -> 8.0

  // Joint sphere
  const jointDiamMm = 28;
  const jointRadius = (jointDiamMm * 0.5) * MM;  // 14mm -> 0.7

  // Shade (cone)
  const shadeTopRadMm = 20;
  const shadeBotRadMm = 100;
  const shadeHeightMm = 80;
  const shadeTopRadius = (shadeTopRadMm * 0.5) * MM;   // 10mm -> 0.5
  const shadeBotRadius = (shadeBotRadMm * 0.5) * MM;   // 50mm -> 2.5
  const shadeHeight = shadeHeightMm * MM;               // 80mm -> 4.0

  // Decorative rivets on base (instanced)
  const rivetRadMm = 6;
  const rivetRadius = (rivetRadMm * 0.5) * MM;   // 3mm -> 0.15
  const rivetCount = 6;

  // Arm tilt angles
  const lowerArmTilt = 55 * Math.PI / 180;
  const upperArmTilt = -40 * Math.PI / 180;

  // --- Groups ---
  const lamp_base = new THREE.Group();
  lamp_base.name = 'lamp_base';

  const lower_arm = new THREE.Group();
  lower_arm.name = 'lower_arm';

  const upper_arm = new THREE.Group();
  upper_arm.name = 'upper_arm';

  const shade_assembly = new THREE.Group();
  shade_assembly.name = 'shade_assembly';

  // --- BASE: hexagonal plate ---
  const basePlateGeom = new THREE.CylinderGeometry(baseRadius, baseRadius * 1.1, baseHeight, 6);
  const basePlate = new THREE.Mesh(basePlateGeom);
  basePlate.name = 'base_plate';
  basePlate.position.set(0, baseHeight / 2, 0);
  lamp_base.add(basePlate);

  // --- BASE RIVETS: InstancedMesh arranged in a ring ---
  const rivetGeom = new THREE.SphereGeometry(rivetRadius, 12, 8);
  const rivetMat = new THREE.MeshBasicMaterial();
  const rivets = new THREE.InstancedMesh(rivetGeom, rivetMat, rivetCount);
  rivets.name = 'base_rivets';

  const rivetHelper = new THREE.Object3D();
  const rivetRingRadius = baseRadius * 0.75;
  for (let i = 0; i < rivetCount; i++) {
    const angle = (i / rivetCount) * Math.PI * 2;
    rivetHelper.position.set(
      rivetRingRadius * Math.cos(angle),
      baseHeight + rivetRadius,
      rivetRingRadius * Math.sin(angle)
    );
    rivetHelper.rotation.set(0, 0, 0);
    rivetHelper.updateMatrix();
    rivets.setMatrixAt(i, rivetHelper.matrix);
  }
  rivets.instanceMatrix.needsUpdate = true;
  lamp_base.add(rivets);

  // --- POWER SWITCH: nested non-uniform scaling + rotations ---
  const switch_housing = new THREE.Group();
  switch_housing.name = 'switch_housing';
  switch_housing.position.set(baseRadius * 0.5, baseHeight * 0.8, baseRadius * 0.3);
  switch_housing.rotation.y = -Math.PI / 5;
  switch_housing.scale.set(1.4, 0.6, -1.1); // mirrored Z

  const switch_inner = new THREE.Group();
  switch_inner.name = 'switch_inner';
  switch_inner.rotation.x = Math.PI / 15;
  switch_inner.rotation.z = -Math.PI / 10;
  switch_inner.scale.set(0.8, 1.5, 0.9);
  switch_housing.add(switch_inner);

  const switchGeom = new THREE.BoxGeometry(baseRadius * 0.3, baseHeight * 0.4, baseRadius * 0.15);
  const switchMesh = new THREE.Mesh(switchGeom, new THREE.MeshBasicMaterial());
  switchMesh.name = 'power_switch';
  switchMesh.position.set(0, baseHeight * 0.15, 0);
  switch_inner.add(switchMesh);
  lamp_base.add(switch_housing);

  // --- LOWER ARM: tilted cylinder ---
  const lowerArmGeom = new THREE.CylinderGeometry(armRadius, armRadius, armLowerLen, 20);
  const lowerArmMesh = new THREE.Mesh(lowerArmGeom);
  lowerArmMesh.name = 'lower_arm_segment';
  lowerArmMesh.position.set(0, armLowerLen / 2, 0);
  lower_arm.add(lowerArmMesh);

  lower_arm.position.set(0, baseHeight, 0);
  lower_arm.rotation.z = lowerArmTilt;

  // --- ELBOW JOINT: sphere at top of lower arm ---
  const elbowJointGeom = new THREE.SphereGeometry(jointRadius, 24, 16);
  const elbowJoint = new THREE.Mesh(elbowJointGeom);
  elbowJoint.name = 'elbow_joint';
  elbowJoint.position.set(0, armLowerLen, 0);
  lower_arm.add(elbowJoint);

  // --- UPPER ARM: attached at elbow ---
  upper_arm.position.set(0, armLowerLen, 0);
  upper_arm.rotation.z = upperArmTilt;

  const upperArmGeom = new THREE.CylinderGeometry(armRadius * 0.85, armRadius * 0.85, armUpperLen, 20);
  const upperArmMesh = new THREE.Mesh(upperArmGeom);
  upperArmMesh.name = 'upper_arm_segment';
  upperArmMesh.position.set(0, armUpperLen / 2, 0);
  upper_arm.add(upperArmMesh);

  // --- SHADE ASSEMBLY: cone + rim ring ---
  shade_assembly.position.set(0, armUpperLen, 0);
  shade_assembly.rotation.z = -upperArmTilt * 0.3; // slight correction tilt

  const shadeGeom = new THREE.ConeGeometry(shadeBotRadius, shadeHeight, 36);
  const shadeMesh = new THREE.Mesh(shadeGeom);
  shadeMesh.name = 'lamp_shade';
  shadeMesh.position.set(0, -shadeHeight / 2, 0);
  shade_assembly.add(shadeMesh);

  // Rim ring (torus at bottom of shade)
  const rimRadius = shadeBotRadius;
  const rimTubeRadius = armRadius * 0.4;
  const rimGeom = new THREE.TorusGeometry(rimRadius, rimTubeRadius, 12, 48);
  const rimMesh = new THREE.Mesh(rimGeom);
  rimMesh.name = 'shade_rim';
  rimMesh.rotation.x = Math.PI / 2;
  rimMesh.position.set(0, -shadeHeight, 0);
  shade_assembly.add(rimMesh);

  // Bulb socket (small cylinder inside shade)
  const socketGeom = new THREE.CylinderGeometry(shadeTopRadius * 0.6, shadeTopRadius * 0.8, shadeHeight * 0.3, 16);
  const socketMesh = new THREE.Mesh(socketGeom);
  socketMesh.name = 'bulb_socket';
  socketMesh.position.set(0, -shadeHeight * 0.4, 0);
  shade_assembly.add(socketMesh);

  // --- Assemble hierarchy ---
  // upper_arm is child of lower_arm
  lower_arm.add(upper_arm);
  // shade is child of upper_arm
  upper_arm.add(shade_assembly);

  root.add(lamp_base);
  root.add(lower_arm);

  return root;
}
