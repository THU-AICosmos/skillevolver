import * as THREE from 'three';
import { OBJExporter } from 'three/examples/jsm/exporters/OBJExporter.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import fs from 'fs';
import { pathToFileURL } from 'url';

async function generateReference() {
    const moduleURL = pathToFileURL('/root/data/object.js').href;
    const mod = await import(moduleURL);
    const scene = mod.createScene();
    scene.updateMatrixWorld(true);

    const allGeoms = [];
    const worldMat = new THREE.Matrix4();
    const instMat = new THREE.Matrix4();
    const rotX = new THREE.Matrix4().makeRotationX(-Math.PI / 2);

    const collectGeometry = (src, mat) => {
        let g = src.clone();
        g.applyMatrix4(mat);
        g.applyMatrix4(rotX);
        if (g.index) {
            g = g.toNonIndexed();
        }
        if (!g.attributes.normal) {
            g.computeVertexNormals();
        }
        allGeoms.push(g);
    };

    scene.traverse((node) => {
        if (node.isInstancedMesh) {
            const count = node.count ?? node.instanceCount ?? 0;
            for (let k = 0; k < count; k++) {
                node.getMatrixAt(k, instMat);
                worldMat.copy(node.matrixWorld).multiply(instMat);
                collectGeometry(node.geometry, worldMat);
            }
            return;
        }
        if (node instanceof THREE.Mesh) {
            collectGeometry(node.geometry, node.matrixWorld);
        }
    });

    const combined = mergeGeometries(allGeoms, false);
    const outputMesh = new THREE.Mesh(combined);
    const exp = new OBJExporter();
    fs.mkdirSync('/root/ground_truth', { recursive: true });
    fs.writeFileSync('/root/ground_truth/scene.obj', exp.parse(outputMesh));
    console.log('Reference mesh written to /root/ground_truth/scene.obj');
}

generateReference().catch((e) => {
    console.error('Ground truth generation failed:', e);
    process.exit(1);
});
