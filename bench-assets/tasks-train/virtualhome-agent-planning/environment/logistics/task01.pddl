;; Logistics train problem 01: move one package from warehouse to store_b.
(define (problem logistics-train-01-p)
  (:domain logistics-train-01)

  (:objects
    warehouse store_a store_b - location
    pkg1 - package
    truck1 - vehicle
  )

  (:init
    (at-vehicle truck1 warehouse)
    (at-package pkg1 warehouse)
  )

  (:goal (and
    (at-package pkg1 store_b)
  ))
)
