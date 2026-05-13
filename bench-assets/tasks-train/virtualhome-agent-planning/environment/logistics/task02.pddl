;; Logistics train problem 02: two trucks, two packages must swap destinations.
(define (problem logistics-train-02-p)
  (:domain logistics-train-02)

  (:objects
    depot hub port - location
    crate_red crate_blue - package
    truck_a truck_b - vehicle
  )

  (:init
    (at-vehicle truck_a depot)
    (at-vehicle truck_b port)
    (at-package crate_red depot)
    (at-package crate_blue port)
  )

  (:goal (and
    (at-package crate_red port)
    (at-package crate_blue depot)
  ))
)
