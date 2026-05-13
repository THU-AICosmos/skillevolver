## Task description

A traffic-safety researcher needs a tally of *non-pedestrian* moving objects in surveillance footage. Video clips are stored under `/app/video`.

For each video file, watch the clip and produce a single integer: the number of distinct moving objects that are **NOT pedestrians on foot**. This means counting riders on bicycles, scooters, and motorcycles together with motor vehicles (cars, vans, trucks, buses). People walking on foot are excluded.

Counting rules:
- A bicycle (or scooter / motorcycle) being ridden contributes **1** to the tally — count the rider+vehicle as a single moving entity, not as a separate person and bike.
- A motor vehicle contributes **1** regardless of how many occupants are inside.
- Any individual entity that lingers across many consecutive frames must only be counted once.
- A parked / stationary vehicle that never moves should still be counted (it is a non-pedestrian object on the street).

Write the result to `/app/video/transit_log.xlsx`. The workbook must contain exactly one sheet named `tally`, with two columns:

- `clip`: the source filename (for example `test1.mp4`).
- `non_pedestrian_count`: the integer total of non-pedestrian moving entities for that clip.

The first row holds the column headers; each subsequent row holds one clip. Do not add any other sheets, columns, rows, or formatting.
