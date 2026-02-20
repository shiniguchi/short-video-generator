"""UGCJob state machine — guard layer for status transitions.

DB column is source of truth, not the state machine instance.
For existing rows, always instantiate with start_value=job.status so the
machine starts at the current persisted state.

Usage:
    sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
    sm.send("start")  # validates pending -> running; writes job.status = "running"
"""
from statemachine import StateMachine, State


class UGCJobStateMachine(StateMachine):
    """Guards all UGCJob status transitions.

    States map 1:1 to UGCJob.status column values.
    Invalid transitions raise statemachine.exceptions.TransitionNotAllowed.
    """

    # --- States ---
    pending = State(initial=True)
    running = State()
    stage_analysis_review = State()
    stage_script_review = State()
    stage_aroll_review = State()
    stage_broll_review = State()
    stage_composition_review = State()
    approved = State(final=True)
    failed = State(final=True)

    # --- Transitions ---
    start = pending.to(running)
    complete_analysis = running.to(stage_analysis_review)
    approve_analysis = stage_analysis_review.to(running)
    complete_script = running.to(stage_script_review)
    approve_script = stage_script_review.to(running)
    complete_aroll = running.to(stage_aroll_review)
    approve_aroll = stage_aroll_review.to(running)
    complete_broll = running.to(stage_broll_review)
    approve_broll = stage_broll_review.to(running)
    complete_composition = running.to(stage_composition_review)
    approve_final = stage_composition_review.to(approved)

    # fail is reachable from any non-final state
    fail = (
        pending.to(failed)
        | running.to(failed)
        | stage_analysis_review.to(failed)
        | stage_script_review.to(failed)
        | stage_aroll_review.to(failed)
        | stage_broll_review.to(failed)
        | stage_composition_review.to(failed)
    )
