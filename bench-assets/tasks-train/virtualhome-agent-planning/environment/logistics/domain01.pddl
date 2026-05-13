;; Logistics planning domain (train variant).
;; A truck-only single-city delivery problem: packages are moved between
;; locations in one city by a single truck. Strict STRIPS semantics so
;; pyperplan and unified_planning's PlanValidator can handle it.

(define (domain logistics-train-01)
  (:requirements :strips :typing)

  (:types
    location package vehicle
  )

  (:predicates
    (at-package ?p - package ?l - location)
    (at-vehicle ?v - vehicle ?l - location)
    (in ?p - package ?v - vehicle)
  )

  (:action drive
    :parameters (?v - vehicle ?from - location ?to - location)
    :precondition (at-vehicle ?v ?from)
    :effect (and
      (not (at-vehicle ?v ?from))
      (at-vehicle ?v ?to)
    )
  )

  (:action load
    :parameters (?p - package ?v - vehicle ?l - location)
    :precondition (and (at-vehicle ?v ?l) (at-package ?p ?l))
    :effect (and
      (not (at-package ?p ?l))
      (in ?p ?v)
    )
  )

  (:action unload
    :parameters (?p - package ?v - vehicle ?l - location)
    :precondition (and (at-vehicle ?v ?l) (in ?p ?v))
    :effect (and
      (not (in ?p ?v))
      (at-package ?p ?l)
    )
  )
)
