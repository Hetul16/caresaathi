// Run work straight after the commit that scheduled it, never inside it.
//
// Loading on mount is the shape of almost every panel here: an effect asks the API and the answer fills the panel.
// React's compiler rule react-hooks/set-state-in-effect is right that setting state *during* an effect cascades
// renders, so the call is handed to a microtask: the effect body only schedules, and every setState that follows
// lands in a later, batched pass. Behaviour is unchanged apart from a sub-millisecond delay before the fetch starts.
export function afterCommit(work: () => unknown): void {
  void Promise.resolve().then(work);
}
