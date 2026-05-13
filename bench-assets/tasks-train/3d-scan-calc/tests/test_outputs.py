import collections
import json
import math
import os
import struct


class TestOutputs:
    def test_file_exists(self):
        """Check output file was created."""
        assert os.path.exists("/root/coating_estimate.json"), "Output file not found"

    def _compute_ground_truth(self):
        stl_path = "/root/sonar_scan.stl"
        triangles = []

        with open(stl_path, "rb") as fh:
            fh.read(80)
            num = struct.unpack("<I", fh.read(4))[0]
            for _ in range(num):
                rec = fh.read(50)
                fv = struct.unpack("<3f3f3f3f", rec[:48])
                attr = struct.unpack("<H", rec[48:50])[0]
                p1 = (fv[3], fv[4], fv[5])
                p2 = (fv[6], fv[7], fv[8])
                p3 = (fv[9], fv[10], fv[11])
                triangles.append((p1, p2, p3, attr))

        # Connected component extraction
        def snap(v):
            return (round(v[0], 4), round(v[1], 4), round(v[2], 4))

        adjacency = collections.defaultdict(list)
        for idx, tri in enumerate(triangles):
            for pt in tri[:3]:
                adjacency[snap(pt)].append(idx)

        visited = set()
        components = []
        for idx in range(len(triangles)):
            if idx in visited:
                continue
            cluster = []
            queue = collections.deque([idx])
            visited.add(idx)
            while queue:
                cur = queue.popleft()
                cluster.append(cur)
                for pt in triangles[cur][:3]:
                    for nb in adjacency[snap(pt)]:
                        if nb not in visited:
                            visited.add(nb)
                            queue.append(nb)
            components.append([triangles[i] for i in cluster])

        # Surface area computation and cost lookup
        # Derived from reading /root/coating_price_list.md
        PRICE_TABLE = {5: 0.50, 12: 3.25, 37: 8.75, 60: 12.00, 88: 15.50}

        results = []
        for comp in components:
            sa = 0.0
            for tri in comp:
                a, b, c = tri[0], tri[1], tri[2]
                e1 = (b[0]-a[0], b[1]-a[1], b[2]-a[2])
                e2 = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
                cx = e1[1]*e2[2] - e1[2]*e2[1]
                cy = e1[2]*e2[0] - e1[0]*e2[2]
                cz = e1[0]*e2[1] - e1[1]*e2[0]
                sa += 0.5 * math.sqrt(cx*cx + cy*cy + cz*cz)

            code = comp[0][3]
            rate = PRICE_TABLE.get(code, 1.0)
            cost = sa * rate
            results.append((cost, sa, code))

        # Largest by surface area
        results.sort(key=lambda x: x[1], reverse=True)
        return results[0]  # (cost, area, code)

    def test_values_correct(self):
        """Validate submission against ground truth."""
        expected_cost, expected_area, expected_code = self._compute_ground_truth()

        with open("/root/coating_estimate.json") as fh:
            submission = json.load(fh)

        assert "total_coating_cost" in submission
        assert "coating_code" in submission
        assert "surface_area" in submission

        # Check coating code
        assert submission["coating_code"] == expected_code, \
            f"Expected Coating Code {expected_code}, got {submission['coating_code']}"

        # Check surface area (0.1% tolerance)
        sub_area = submission["surface_area"]
        assert math.isclose(sub_area, expected_area, rel_tol=0.001), \
            f"Surface area mismatch. Expected ~{expected_area:.2f}, got {sub_area:.2f}"

        # Check total cost (0.1% tolerance)
        sub_cost = submission["total_coating_cost"]
        assert math.isclose(sub_cost, expected_cost, rel_tol=0.001), \
            f"Cost mismatch. Expected ~{expected_cost:.2f}, got {sub_cost:.2f}"
