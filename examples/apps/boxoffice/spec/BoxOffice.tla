---------------------------- MODULE BoxOffice ----------------------------
(***************************************************************************)
(* Box Office as a distributed system: customers, the ticketing service,   *)
(* Kafka, and the payment service, with the clock that expires holds.      *)
(*                                                                         *)
(* Each action is one transaction of one service, as the Java code commits *)
(* it (see the operation named in each comment). Between actions, anything *)
(* can interleave: the clock can tick, another customer can hold the same  *)
(* seat, a message can sit in a topic. TLC explores every such interleaving *)
(* up to the bounds in BoxOffice.cfg and checks the invariants at the end. *)
(*                                                                         *)
(* The order state machine, Decide(status, input), is not written here. It *)
(* is generated from the behavioural contract of OrderLifecycle#decide     *)
(* (OrderLifecycleContract.tla), which the build proves the bytecode obeys. *)
(*                                                                         *)
(* Simplifications: one hold and one order per customer (the hold id, the  *)
(* order id and the customer are the same value); a relay publishes each   *)
(* outbox entry exactly once, since the inbox makes a redelivery a no-op;   *)
(* a transaction that fails is retried until the record is dead-lettered,  *)
(* which the model does in one step.                                       *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, OrderLifecycleContract

CONSTANTS
    Customers,   \* who can hold seats, place orders and cancel them
    Seats,       \* the seats of the one concert
    MaxTime,     \* how far the clock runs, in ticks
    HoldTtl,     \* how long a hold lasts, in ticks (boxoffice.hold.ttl)
    Sweeper      \* whether the hold sweeper runs (HoldService.releaseExpiredHolds)

VARIABLES
    time,        \* the clock
    seat,        \* seat -> [status, holdId, expiresAt, orderId]  (the seats collection)
    hold,        \* customer -> [seats, expiresAt]                 (the holds collection; no hold: seats = {})
    order,       \* customer -> order status, or "NONE"           (the orders collection)
    payment,     \* customer -> payment status, or "NONE"         (the payments collection)
    tOutbox,     \* the ticketing outbox: commands waiting for the relay
    pOutbox,     \* the payment outbox: events waiting for the relay
    commands,    \* the Kafka topic payments.commands
    events,      \* the Kafka topic payments.events
    dlt          \* dead-lettered records: a message whose transaction kept failing

vars == <<time, seat, hold, order, payment, tOutbox, pOutbox, commands, events, dlt>>

None == "none"
Available == [status |-> "AVAILABLE", holdId |-> None, expiresAt |-> 0, orderId |-> None]
Msg(kind, c) == [kind |-> kind, order |-> c]

(***************************************************************************)
(* Reads, as the store makes them.                                         *)
(***************************************************************************)

\* TicketingStore.hold: a seat a new hold may take. An expired hold is free before the sweeper runs.
Holdable(s) == seat[s].status = "AVAILABLE" \/ (seat[s].status = "HELD" /\ seat[s].expiresAt <= time)

\* TicketingStore.heldBy: the seats a hold still holds, expired or not.
HeldBy(c) == {s \in Seats : seat[s].status = "HELD" /\ seat[s].holdId = c}

\* TicketingStore.heldUnexpiredBy
HeldUnexpiredBy(c) == {s \in HeldBy(c) : seat[s].expiresAt > time}

(***************************************************************************)
(* Customers and the ticketing service.                                    *)
(***************************************************************************)

\* HoldService.hold: all of S or none, in one transaction. A conflict is a 409 and changes nothing.
Hold(c, S) ==
    /\ hold[c].seats = {}
    /\ \A s \in S : Holdable(s)
    /\ seat' = [s \in Seats |-> IF s \in S
                                THEN [status |-> "HELD", holdId |-> c, expiresAt |-> time + HoldTtl, orderId |-> None]
                                ELSE seat[s]]
    /\ hold' = [hold EXCEPT ![c] = [seats |-> S, expiresAt |-> time + HoldTtl]]
    /\ UNCHANGED <<time, order, payment, tOutbox, pOutbox, commands, events, dlt>>

\* OrderService.place: the hold must be unexpired; the order and the charge command commit together.
PlaceOrder(c) ==
    /\ hold[c].seats # {}
    /\ order[c] = "NONE"
    /\ HeldUnexpiredBy(c) = hold[c].seats
    /\ order' = [order EXCEPT ![c] = "PENDING_PAYMENT"]
    /\ tOutbox' = Append(tOutbox, Msg("ChargePayment", c))
    /\ UNCHANGED <<time, seat, hold, payment, pOutbox, commands, events, dlt>>

\* OrderTransitions.apply: the decision's effects, then the status change, in the caller's transaction.
\* SELL_SEATS sells the seats the hold still holds; if that is not all of them, the transaction fails.
Has(decision, effect) == \E i \in 1..Len(decision.effects) : decision.effects[i] = effect

SellsEverySeat(c, decision) == ~Has(decision, "SELL_SEATS") \/ HeldBy(c) = hold[c].seats

Sold(c, s) == [seat[s] EXCEPT !.status = "SOLD", !.orderId = c, !.expiresAt = 0]

Released(c, s) ==
    IF (seat[s].status = "HELD" /\ seat[s].holdId = c) \/ (seat[s].status = "SOLD" /\ seat[s].orderId = c)
    THEN Available
    ELSE seat[s]

SeatsAfter(c, decision) ==
    [s \in Seats |->
        IF Has(decision, "SELL_SEATS") /\ s \in HeldBy(c) THEN Sold(c, s)
        ELSE IF Has(decision, "RELEASE_SEATS") THEN Released(c, s)
        ELSE seat[s]]

ApplyTransition(c, decision) ==
    /\ seat' = SeatsAfter(c, decision)
    /\ order' = [order EXCEPT ![c] = decision.next]
    /\ tOutbox' = IF Has(decision, "REQUEST_REFUND") THEN Append(tOutbox, Msg("RefundPayment", c)) ELSE tOutbox

\* OrderService.cancel: a rejected cancellation is a 409 and changes nothing.
Cancel(c) ==
    /\ order[c] # "NONE"
    /\ LET decision == Decide(order[c], [kind |-> "CancellationRequested"])
       IN /\ decision.kind = "Transition"
          /\ ApplyTransition(c, decision)
    /\ UNCHANGED <<time, hold, payment, pOutbox, commands, events, dlt>>

\* PaymentEventHandler.handle: the payment outcome becomes an OrderInput, and the decision is applied.
Input(m, c) ==
    CASE m.kind = "PaymentCaptured" -> [kind |-> "PaymentCaptured", seatsStillHeld |-> HeldBy(c) = hold[c].seats]
      [] m.kind = "PaymentDeclined" -> [kind |-> "PaymentDeclined"]
      [] m.kind = "PaymentRefunded" -> [kind |-> "PaymentRefunded"]

HandleEvent ==
    /\ events # <<>>
    /\ LET m == Head(events)
           c == m.order
           decision == Decide(order[c], Input(m, c))
       IN /\ events' = Tail(events)
          /\ IF decision.kind # "Transition" THEN
                 UNCHANGED <<seat, order, tOutbox, dlt>>
             ELSE IF ~SellsEverySeat(c, decision) THEN
                 \* IllegalStateException rolls the transaction back; Kafka retries, then dead-letters the record.
                 /\ dlt' = dlt \cup {m}
                 /\ UNCHANGED <<seat, order, tOutbox>>
             ELSE
                 /\ ApplyTransition(c, decision)
                 /\ UNCHANGED dlt
    /\ UNCHANGED <<time, hold, payment, pOutbox, commands>>

\* HoldService.releaseExpiredHolds
Sweep ==
    /\ Sweeper
    /\ \E s \in Seats : seat[s].status = "HELD" /\ seat[s].expiresAt <= time
    /\ seat' = [s \in Seats |-> IF seat[s].status = "HELD" /\ seat[s].expiresAt <= time THEN Available ELSE seat[s]]
    /\ UNCHANGED <<time, hold, order, payment, tOutbox, pOutbox, commands, events, dlt>>

(***************************************************************************)
(* The relays and Kafka.                                                   *)
(***************************************************************************)

\* OutboxRelay.publishPending, in each service: in order, one entry at a time.
RelayCommand ==
    /\ tOutbox # <<>>
    /\ commands' = Append(commands, Head(tOutbox))
    /\ tOutbox' = Tail(tOutbox)
    /\ UNCHANGED <<time, seat, hold, order, payment, pOutbox, events, dlt>>

RelayEvent ==
    /\ pOutbox # <<>>
    /\ events' = Append(events, Head(pOutbox))
    /\ pOutbox' = Tail(pOutbox)
    /\ UNCHANGED <<time, seat, hold, order, payment, tOutbox, commands, dlt>>

(***************************************************************************)
(* The payment service.                                                    *)
(***************************************************************************)

Outcome(status) == IF status \in {"CAPTURED", "REFUNDED"} THEN "PaymentCaptured" ELSE "PaymentDeclined"

\* PaymentCommandHandler.charge: the gateway captures or declines; a repeated charge reports the first outcome.
Charge(c, result) ==
    IF payment[c] = "NONE" THEN
        /\ payment' = [payment EXCEPT ![c] = result]
        /\ pOutbox' = Append(pOutbox, Msg(Outcome(result), c))
    ELSE
        /\ pOutbox' = Append(pOutbox, Msg(Outcome(payment[c]), c))
        /\ UNCHANGED payment

\* PaymentCommandHandler.refund
Refund(c) ==
    CASE payment[c] = "NONE" ->
            /\ payment' = [payment EXCEPT ![c] = "VOIDED"]   \* the refund overtook the charge
            /\ UNCHANGED pOutbox
      [] payment[c] = "CAPTURED" ->
            /\ payment' = [payment EXCEPT ![c] = "REFUNDED"]
            /\ pOutbox' = Append(pOutbox, Msg("PaymentRefunded", c))
      [] payment[c] = "REFUNDED" ->
            /\ pOutbox' = Append(pOutbox, Msg("PaymentRefunded", c))
            /\ UNCHANGED payment
      [] OTHER ->
            UNCHANGED <<payment, pOutbox>>                    \* nothing captured to refund

HandleCommand ==
    /\ commands # <<>>
    /\ LET m == Head(commands)
       IN /\ commands' = Tail(commands)
          /\ \/ m.kind = "ChargePayment" /\ \E result \in {"CAPTURED", "DECLINED"} : Charge(m.order, result)
             \/ m.kind = "RefundPayment" /\ Refund(m.order)
    /\ UNCHANGED <<time, seat, hold, order, tOutbox, events, dlt>>

(***************************************************************************)
(* The clock.                                                              *)
(***************************************************************************)

Tick ==
    /\ time < MaxTime
    /\ time' = time + 1
    /\ UNCHANGED <<seat, hold, order, payment, tOutbox, pOutbox, commands, events, dlt>>

(***************************************************************************)
(* The specification.                                                      *)
(***************************************************************************)

Init ==
    /\ time = 0
    /\ seat = [s \in Seats |-> Available]
    /\ hold = [c \in Customers |-> [seats |-> {}, expiresAt |-> 0]]
    /\ order = [c \in Customers |-> "NONE"]
    /\ payment = [c \in Customers |-> "NONE"]
    /\ tOutbox = <<>> /\ pOutbox = <<>> /\ commands = <<>> /\ events = <<>>
    /\ dlt = {}

Next ==
    \/ \E c \in Customers : \E S \in (SUBSET Seats) \ {{}} : Hold(c, S)
    \/ \E c \in Customers : PlaceOrder(c)
    \/ \E c \in Customers : Cancel(c)
    \/ RelayCommand
    \/ HandleCommand
    \/ RelayEvent
    \/ HandleEvent
    \/ Sweep
    \/ Tick

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Invariants: the safety properties of examples/apps/boxoffice/README.md. *)
(***************************************************************************)

SeatStatuses == {"AVAILABLE", "HELD", "SOLD"}
OrderStatuses == {"NONE", "PENDING_PAYMENT", "CONFIRMED", "DECLINED", "REFUND_PENDING", "REFUNDED"}
PaymentStatuses == {"NONE", "CAPTURED", "DECLINED", "REFUNDED", "VOIDED"}

TypeOK ==
    /\ time \in 0..MaxTime
    /\ \A s \in Seats : seat[s].status \in SeatStatuses
    /\ \A c \in Customers : order[c] \in OrderStatuses /\ payment[c] \in PaymentStatuses

\* 1. No double sale: two confirmed orders never share a seat.
NoDoubleSale ==
    \A c1, c2 \in Customers : c1 # c2 /\ order[c1] = "CONFIRMED" /\ order[c2] = "CONFIRMED"
        => hold[c1].seats \cap hold[c2].seats = {}

\* 4. No seats without money, both ways: a confirmed order owns every seat it was placed for, and a sold seat
\*    belongs to a confirmed order.
ConfirmedOrdersOwnTheirSeats ==
    \A c \in Customers : order[c] = "CONFIRMED"
        => \A s \in hold[c].seats : seat[s].status = "SOLD" /\ seat[s].orderId = c

SoldSeatsHaveConfirmedOrders ==
    \A s \in Seats : seat[s].status = "SOLD" => order[seat[s].orderId] = "CONFIRMED"

\* 3. No money without seats: captured money is held for a confirmed order, is being refunded, or its capture
\*    event is still on its way to the ticketing service. Money whose event was dead-lettered is stranded.
CaptureInFlight(c) ==
    \/ \E i \in 1..Len(pOutbox) : pOutbox[i] = Msg("PaymentCaptured", c)
    \/ \E i \in 1..Len(events) : events[i] = Msg("PaymentCaptured", c)

NoMoneyStranded ==
    \A c \in Customers : payment[c] = "CAPTURED"
        => order[c] \in {"CONFIRMED", "REFUND_PENDING"} \/ CaptureInFlight(c)

\* A dead-lettered record is a transaction the system gave up on: an operator has to repair the order by hand.
NothingDeadLettered == dlt = {}

\* 5. Agreement at quiescence: when nothing is in flight, the two services tell the same story.
Quiet == tOutbox = <<>> /\ pOutbox = <<>> /\ commands = <<>> /\ events = <<>> /\ dlt = {}

AgreementAtQuiescence ==
    Quiet => \A c \in Customers :
        /\ (order[c] = "CONFIRMED") <=> (payment[c] = "CAPTURED")
        /\ (order[c] = "DECLINED") <=> (payment[c] = "DECLINED")
        /\ (order[c] = "REFUNDED") <=> (payment[c] = "REFUNDED")

=============================================================================
