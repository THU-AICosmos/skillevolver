;; Logistics train problem 03: one truck ferrying three packages across three locations.
(define (problem logistics-train-03-p)
  (:domain logistics-train-03)

  (:objects
    loc_alpha loc_beta loc_gamma - location
    parcel_1 parcel_2 parcel_3 - package
    rover - vehicle
  )

  (:init
    (at-vehicle rover loc_alpha)
    (at-package parcel_1 loc_alpha)
    (at-package parcel_2 loc_beta)
    (at-package parcel_3 loc_gamma)
  )

  (:goal (and
    (at-package parcel_1 loc_gamma)
    (at-package parcel_2 loc_alpha)
    (at-package parcel_3 loc_beta)
  ))
)
