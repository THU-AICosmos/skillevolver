import * as THREE from 'three';

/**
 * Creates a cylinder beam connecting two 3D points.
 * Used for structural members like columns, braces, and beams.
 * @param {THREE.Vector3} point1 - Start point.
 * @param {THREE.Vector3} point2 - End point.
 * @param {number} radius - Beam radius.
 * @param {string} name - Mesh name.
 * @returns {THREE.Mesh}
 */
function createBeam(point1, point2, radius, name) {
    const direction = new THREE.Vector3().subVectors(point2, point1);
    const length = direction.length();
    const geometry = new THREE.CylinderGeometry(radius, radius, length, 16);
    const mesh = new THREE.Mesh(geometry);
    mesh.name = name;
    const Y_AXIS = new THREE.Vector3(0, 1, 0);
    mesh.quaternion.setFromUnitVectors(Y_AXIS, direction.clone().normalize());
    mesh.position.copy(point1).add(direction.multiplyScalar(0.5));
    return mesh;
}

export function createScene() {
    // --- DIMENSIONS ---

    // Base dimensions
    const basePadSize = 12;
    const basePadHeight = 1.5;
    const numStabilizers = 4;
    const stabilizerLength = 8;
    const stabilizerRadius = 0.4;
    const stabilizerFootSize = 2.5;

    // Tower dimensions
    const towerHeight = 50;
    const towerWidth = 3;
    const columnRadius = 0.35;
    const numBraceLevels = 8;

    // Slewing unit
    const turntableRadius = 2.5;
    const turntableHeight = 1.0;

    // Operator cabin
    const cabinWidth = 3;
    const cabinDepth = 2.5;
    const cabinHeight = 2.8;

    // Jib (main horizontal boom)
    const jibLength = 40;
    const jibHeight = 2.0;
    const jibBeamRadius = 0.25;
    const numJibStruts = 12;

    // Counter-jib
    const counterJibLength = 15;
    const numCounterweights = 3;
    const counterweightSize = 2.0;

    // Mast head / pendant lines
    const mastPeakHeight = 6;

    // Hook assembly
    const cableRadius = 0.08;
    const hookRadius = 0.6;

    // --- OBJECT CREATION ---

    const root = new THREE.Group();
    root.name = 'construction_crane';

    // --- 1. Base Structure ---
    const base_structure = new THREE.Group();
    base_structure.name = 'base_structure';
    root.add(base_structure);

    // Base pad
    const basePadGeometry = new THREE.BoxGeometry(basePadSize, basePadHeight, basePadSize);
    const basePadMesh = new THREE.Mesh(basePadGeometry);
    basePadMesh.name = 'base_pad';
    basePadMesh.position.y = basePadHeight / 2;
    base_structure.add(basePadMesh);

    // Stabilizer legs extending outward at 45-degree angles
    for (let i = 0; i < numStabilizers; i++) {
        const angle = (i / numStabilizers) * Math.PI * 2 + Math.PI / 4;
        const dx = Math.cos(angle);
        const dz = Math.sin(angle);

        const legStart = new THREE.Vector3(dx * basePadSize / 2, basePadHeight, dz * basePadSize / 2);
        const legEnd = new THREE.Vector3(dx * (basePadSize / 2 + stabilizerLength), basePadHeight * 0.3, dz * (basePadSize / 2 + stabilizerLength));
        const leg = createBeam(legStart, legEnd, stabilizerRadius, `stabilizer_leg_${i}`);
        base_structure.add(leg);

        // Stabilizer foot pad
        const footGeometry = new THREE.BoxGeometry(stabilizerFootSize, 0.3, stabilizerFootSize);
        const footMesh = new THREE.Mesh(footGeometry);
        footMesh.name = `stabilizer_foot_${i}`;
        footMesh.position.set(legEnd.x, 0.15, legEnd.z);
        base_structure.add(footMesh);
    }

    // --- 2. Tower Section ---
    const tower_section = new THREE.Group();
    tower_section.name = 'tower_section';
    tower_section.position.y = basePadHeight;
    root.add(tower_section);

    // Four vertical columns at corners of the tower
    const cornerOffsets = [
        [-towerWidth / 2, -towerWidth / 2],
        [towerWidth / 2, -towerWidth / 2],
        [towerWidth / 2, towerWidth / 2],
        [-towerWidth / 2, towerWidth / 2],
    ];

    for (let i = 0; i < 4; i++) {
        const [cx, cz] = cornerOffsets[i];
        const col = createBeam(
            new THREE.Vector3(cx, 0, cz),
            new THREE.Vector3(cx, towerHeight, cz),
            columnRadius,
            `tower_column_${i}`
        );
        tower_section.add(col);
    }

    // Diagonal braces between levels
    const levelSpacing = towerHeight / numBraceLevels;
    for (let level = 0; level < numBraceLevels; level++) {
        const y0 = level * levelSpacing;
        const y1 = (level + 1) * levelSpacing;
        // X-brace on front face (z = -towerWidth/2)
        const frontBrace = createBeam(
            new THREE.Vector3(-towerWidth / 2, y0, -towerWidth / 2),
            new THREE.Vector3(towerWidth / 2, y1, -towerWidth / 2),
            columnRadius * 0.5,
            `tower_brace_front_${level}`
        );
        tower_section.add(frontBrace);
        // X-brace on right face (x = towerWidth/2)
        const rightBrace = createBeam(
            new THREE.Vector3(towerWidth / 2, y0, -towerWidth / 2),
            new THREE.Vector3(towerWidth / 2, y1, towerWidth / 2),
            columnRadius * 0.5,
            `tower_brace_right_${level}`
        );
        tower_section.add(rightBrace);
    }

    // Tower cap plate
    const towerCapGeometry = new THREE.BoxGeometry(towerWidth + 1, 0.5, towerWidth + 1);
    const towerCapMesh = new THREE.Mesh(towerCapGeometry);
    towerCapMesh.name = 'tower_cap';
    towerCapMesh.position.y = towerHeight + 0.25;
    tower_section.add(towerCapMesh);

    // --- 3. Slewing Unit (rotates on top of tower) ---
    const slewing_unit = new THREE.Group();
    slewing_unit.name = 'slewing_unit';
    slewing_unit.position.y = basePadHeight + towerHeight + 0.5;
    root.add(slewing_unit);

    // Turntable
    const turntableGeometry = new THREE.CylinderGeometry(turntableRadius, turntableRadius, turntableHeight, 24);
    const turntableMesh = new THREE.Mesh(turntableGeometry);
    turntableMesh.name = 'turntable';
    turntableMesh.position.y = turntableHeight / 2;
    slewing_unit.add(turntableMesh);

    // --- 3a. Operator Cabin ---
    const operator_cabin = new THREE.Group();
    operator_cabin.name = 'operator_cabin';
    operator_cabin.position.set(towerWidth / 2 + cabinWidth / 2, turntableHeight, 0);
    slewing_unit.add(operator_cabin);

    const cabinBodyGeometry = new THREE.BoxGeometry(cabinWidth, cabinHeight, cabinDepth);
    const cabinBodyMesh = new THREE.Mesh(cabinBodyGeometry);
    cabinBodyMesh.name = 'cabin_body';
    cabinBodyMesh.position.y = cabinHeight / 2;
    operator_cabin.add(cabinBodyMesh);

    const cabinWindowGeometry = new THREE.BoxGeometry(cabinWidth * 0.9, cabinHeight * 0.5, 0.1);
    const cabinWindowMesh = new THREE.Mesh(cabinWindowGeometry);
    cabinWindowMesh.name = 'cabin_window';
    cabinWindowMesh.position.set(0, cabinHeight * 0.6, cabinDepth / 2 + 0.05);
    operator_cabin.add(cabinWindowMesh);

    const cabinRoofGeometry = new THREE.BoxGeometry(cabinWidth + 0.4, 0.2, cabinDepth + 0.4);
    const cabinRoofMesh = new THREE.Mesh(cabinRoofGeometry);
    cabinRoofMesh.name = 'cabin_roof';
    cabinRoofMesh.position.y = cabinHeight + 0.1;
    operator_cabin.add(cabinRoofMesh);

    // --- 3b. Jib Arm (main horizontal boom) ---
    const jib_arm = new THREE.Group();
    jib_arm.name = 'jib_arm';
    jib_arm.position.y = turntableHeight + 1;
    slewing_unit.add(jib_arm);

    // Top and bottom horizontal chords of the jib
    const jibTopBeam = createBeam(
        new THREE.Vector3(0, jibHeight, 0),
        new THREE.Vector3(jibLength, jibHeight, 0),
        jibBeamRadius,
        'jib_beam_top'
    );
    jib_arm.add(jibTopBeam);

    const jibBottomBeam = createBeam(
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(jibLength, 0, 0),
        jibBeamRadius,
        'jib_beam_bottom'
    );
    jib_arm.add(jibBottomBeam);

    // Vertical struts along the jib
    for (let i = 0; i <= numJibStruts; i++) {
        const x = (i / numJibStruts) * jibLength;
        const strut = createBeam(
            new THREE.Vector3(x, 0, 0),
            new THREE.Vector3(x, jibHeight, 0),
            jibBeamRadius * 0.6,
            `jib_strut_${i}`
        );
        jib_arm.add(strut);
    }

    // Trolley (movable block along jib)
    const trolleyGeometry = new THREE.BoxGeometry(1.5, 0.8, 1.5);
    const trolleyMesh = new THREE.Mesh(trolleyGeometry);
    trolleyMesh.name = 'trolley';
    trolleyMesh.position.set(jibLength * 0.7, -0.4, 0);
    jib_arm.add(trolleyMesh);

    // --- 3c. Counter-Jib ---
    const counter_jib = new THREE.Group();
    counter_jib.name = 'counter_jib';
    counter_jib.position.y = turntableHeight + 1;
    slewing_unit.add(counter_jib);

    // Counter-jib beam extending backward
    const counterBeam = createBeam(
        new THREE.Vector3(0, jibHeight / 2, 0),
        new THREE.Vector3(-counterJibLength, jibHeight / 2, 0),
        jibBeamRadius * 1.2,
        'counter_beam'
    );
    counter_jib.add(counterBeam);

    // Counterweights stacked at the back
    for (let i = 0; i < numCounterweights; i++) {
        const cwGeometry = new THREE.BoxGeometry(counterweightSize, counterweightSize, counterweightSize);
        const cwMesh = new THREE.Mesh(cwGeometry);
        cwMesh.name = `counterweight_${i}`;
        cwMesh.position.set(
            -counterJibLength + counterweightSize / 2,
            counterweightSize * i + counterweightSize / 2,
            0
        );
        counter_jib.add(cwMesh);
    }

    // --- 3d. Mast Head & Pendant Lines ---
    const mast_head = new THREE.Group();
    mast_head.name = 'mast_head';
    mast_head.position.y = turntableHeight + 1;
    slewing_unit.add(mast_head);

    // Peak structure (pyramid/cone on top)
    const peakGeometry = new THREE.ConeGeometry(1.0, mastPeakHeight, 4);
    const peakMesh = new THREE.Mesh(peakGeometry);
    peakMesh.name = 'mast_peak';
    peakMesh.position.y = jibHeight + mastPeakHeight / 2;
    mast_head.add(peakMesh);

    // Pendant line to jib tip
    const pendantFront = createBeam(
        new THREE.Vector3(0, jibHeight + mastPeakHeight, 0),
        new THREE.Vector3(jibLength * 0.75, jibHeight, 0),
        cableRadius * 2,
        'pendant_front'
    );
    mast_head.add(pendantFront);

    // Pendant line to counter-jib end
    const pendantBack = createBeam(
        new THREE.Vector3(0, jibHeight + mastPeakHeight, 0),
        new THREE.Vector3(-counterJibLength * 0.9, jibHeight / 2, 0),
        cableRadius * 2,
        'pendant_back'
    );
    mast_head.add(pendantBack);

    // --- 4. Hook Assembly (hangs from trolley) ---
    const hook_assembly = new THREE.Group();
    hook_assembly.name = 'hook_assembly';
    // Position below the trolley on the jib
    const trolleyWorldX = jibLength * 0.7;
    hook_assembly.position.set(trolleyWorldX, turntableHeight + 1 - 0.8, 0);
    slewing_unit.add(hook_assembly);

    // Cable
    const cableLength = 20;
    const cable = createBeam(
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(0, -cableLength, 0),
        cableRadius,
        'cable'
    );
    hook_assembly.add(cable);

    // Hook block
    const hookBlockGeometry = new THREE.BoxGeometry(1.2, 0.8, 1.2);
    const hookBlockMesh = new THREE.Mesh(hookBlockGeometry);
    hookBlockMesh.name = 'hook_block';
    hookBlockMesh.position.y = -cableLength - 0.4;
    hook_assembly.add(hookBlockMesh);

    // Hook (torus shape)
    const hookGeometry = new THREE.TorusGeometry(hookRadius, 0.1, 8, 16, Math.PI);
    const hookMesh = new THREE.Mesh(hookGeometry);
    hookMesh.name = 'hook';
    hookMesh.position.y = -cableLength - 0.8 - hookRadius;
    hookMesh.rotation.z = Math.PI;
    hook_assembly.add(hookMesh);

    return root;
}
