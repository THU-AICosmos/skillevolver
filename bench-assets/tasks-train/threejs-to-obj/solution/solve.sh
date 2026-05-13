#!/bin/bash
set -e

# Prepare output folder
mkdir -p /root/output

# Write the converter script
cat > /root/convert_lamp.mjs << 'SCRIPT'
import * as THREE from 'three';
import { OBJExporter } from 'three/examples/jsm/exporters/OBJExporter.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import fs from 'fs';
import { pathToFileURL } from 'url';

const INPUT  = '/root/data/object.js';
const OUTPUT = '/root/output/scene.obj';

// Helper: gather a single BufferGeometry into the list after applying transforms
function harvestMesh(bufGeom, worldTransform, zUpCorrection, bucket) {
    let geo = bufGeom.clone();
    geo.applyMatrix4(worldTransform);
    geo.applyMatrix4(zUpCorrection);
    if (geo.index) geo = geo.toNonIndexed();
    if (!geo.attributes.normal) geo.computeVertexNormals();
    bucket.push(geo);
}

async function run() {
    const mod = await import(pathToFileURL(INPUT).href);
    const rootObj = mod.createScene();
    rootObj.updateMatrixWorld(true);

    const collected = [];
    const blenderRot = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
    const tmpWorld = new THREE.Matrix4();
    const tmpInst = new THREE.Matrix4();

    rootObj.traverse((child) => {
        if (child.isInstancedMesh) {
            const n = child.count ?? child.instanceCount ?? 0;
            for (let idx = 0; idx < n; idx++) {
                child.getMatrixAt(idx, tmpInst);
                tmpWorld.copy(child.matrixWorld).multiply(tmpInst);
                harvestMesh(child.geometry, tmpWorld, blenderRot, collected);
            }
        } else if (child instanceof THREE.Mesh) {
            harvestMesh(child.geometry, child.matrixWorld, blenderRot, collected);
        }
    });

    console.log(`Collected ${collected.length} geometry chunks`);

    const unified = mergeGeometries(collected, false);
    const wrapper = new THREE.Mesh(unified);
    wrapper.name = rootObj.name ?? 'exported';

    const objText = new OBJExporter().parse(wrapper);
    fs.writeFileSync(OUTPUT, objText);
    console.log(`Written ${OUTPUT}`);
}

run().catch((err) => { console.error(err); process.exit(1); });
SCRIPT

# Execute
node /root/convert_lamp.mjs
