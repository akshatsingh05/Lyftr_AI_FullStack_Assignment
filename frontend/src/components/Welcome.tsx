const EXAMPLES = [
  "What is the capital of France?",
  "Explain how a hash map works in two paragraphs.",
  "Draft a polite email asking to move a meeting to Friday.",
  "Give me three ideas for a weekend project with a Raspberry Pi.",
];

export function Welcome({ onPick, disabled }: { onPick: (t: string) => void; disabled: boolean }) {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col justify-center px-6 py-10">
      <h1 className="font-serif text-4xl leading-tight tracking-tight text-ink sm:text-5xl">What would you like to work through?</h1>
      <p className="mt-4 max-w-md text-base leading-relaxed text-ink-soft">
        Ask anything. Under each answer you will see where it came from, how long it took and how many tokens it used.
      </p>
      <ul className="mt-8 grid gap-2.5 sm:grid-cols-2">
        {EXAMPLES.map((e) => (
          <li key={e}>
            <button
              onClick={() => onPick(e)}
              disabled={disabled}
              className="h-full w-full rounded-xl border border-line bg-surface px-4 py-3 text-left text-sm leading-snug text-ink transition-colors hover:border-accent/50 hover:bg-accent-soft/50 disabled:opacity-50"
            >
              {e}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
