import { useState, useRef, useEffect, useCallback } from 'react';

interface FilterExpression {
  field: string;
  operator: string;
  value: string;
  conjunction: 'AND' | 'OR';
}

interface FilterBarProps {
  datasetColumns: { name: string; type: string }[];
  annotationFields: string[];
  onFilterChange: (filter: FilterExpression[]) => void;
}

const BUILTIN_FIELDS = [
  { name: 'annotations.count', type: 'integer' },
  { name: 'annotations.annotated_by', type: 'string' },
  { name: 'annotations.created_at', type: 'datetime' },
  { name: 'annotations.updated_at', type: 'datetime' },
  { name: 'row_index', type: 'integer' },
];

const OPERATORS = ['=', '!=', '~=', '>', '>=', '<', '<='];

const EMPTY_SUGGESTIONS: FilterExpression[] = [
  { field: 'annotations.count', operator: '=', value: '0', conjunction: 'AND' },
  { field: 'annotations.count', operator: '>', value: '0', conjunction: 'AND' },
  { field: 'annotations.annotated_by', operator: '=', value: 'me', conjunction: 'AND' },
];

interface ExpressionPill {
  field: string;
  operator: string;
  value: string;
  conjunction: 'AND' | 'OR';
}

export default function FilterBar({ datasetColumns, annotationFields, onFilterChange }: FilterBarProps) {
  const [pills, setPills] = useState<ExpressionPill[]>([]);
  const [inProgress, setInProgress] = useState<ExpressionPill | null>(null);
  const [draft, setDraft] = useState('');
  const [phase, setPhase] = useState<'field' | 'operator' | 'value'>('field');
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [showEmptySuggestions, setShowEmptySuggestions] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const allFields = useCallback(() => {
    const data = (datasetColumns || []).map((c) => `data.${c.name}`);
    const ann = (annotationFields || []).map((f) => `annotation.${f}`);
    const builtin = BUILTIN_FIELDS.map((f) => f.name);
    return [...data, ...ann, ...builtin];
  }, [datasetColumns, annotationFields]);

  const matchingFields = allFields().filter((f) =>
    f.toLowerCase().includes(draft.toLowerCase())
  );

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowAutocomplete(false);
        setShowEmptySuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const commitPills = (newPills: ExpressionPill[]) => {
    setPills(newPills);
    onFilterChange(newPills.map((p) => ({ ...p })));
  };

  const acceptField = (field: string) => {
    setInProgress({ field, operator: '', value: '', conjunction: 'AND' });
    setDraft('');
    setPhase('operator');
    setShowAutocomplete(false);
    setShowEmptySuggestions(false);
    setHighlightIdx(0);
    inputRef.current?.focus();
  };

  const acceptSuggestion = (sug: FilterExpression) => {
    const newPills = [...pills, { ...sug }];
    commitPills(newPills);
    setInProgress(null);
    setShowEmptySuggestions(false);
    setDraft('');
    setPhase('field');
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Tab' || (e.key === 'Enter' && (showAutocomplete || showEmptySuggestions))) {
      e.preventDefault();
      if (showEmptySuggestions && EMPTY_SUGGESTIONS[highlightIdx]) {
        acceptSuggestion(EMPTY_SUGGESTIONS[highlightIdx]);
        return;
      }
      if (showAutocomplete && matchingFields[highlightIdx]) {
        acceptField(matchingFields[highlightIdx]);
        return;
      }
    }

    if (e.key === 'Enter' && phase === 'value' && draft && inProgress) {
      e.preventDefault();
      commitExpr({ ...inProgress, value: draft.replace(/^"|"$/g, '') });
      setDraft('');
      return;
    }

    if (e.key === 'Backspace') {
      if (draft) return;
      if (inProgress) {
        setInProgress(null);
        setPhase('field');
        setDraft('');
        return;
      }
      if (pills.length > 0) {
        commitPills(pills.slice(0, -1));
        return;
      }
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const options = showEmptySuggestions ? EMPTY_SUGGESTIONS : matchingFields;
      setHighlightIdx((prev) => Math.min(prev + 1, options.length - 1));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx((prev) => Math.max(prev - 1, 0));
      return;
    }
  };

  const handleChange = (val: string) => {
    setDraft(val);
    setHighlightIdx(0);

    if (val === '' && phase === 'field') {
      setShowEmptySuggestions(true);
      setShowAutocomplete(false);
      return;
    }

    if (phase === 'field') {
      if (!inProgress) {
        setInProgress({ field: '', operator: '', value: '', conjunction: 'AND' });
      }
      setShowAutocomplete(true);
      setShowEmptySuggestions(false);

      const op = OPERATORS.find((o) => val.endsWith(o));
      if (op) {
        const fieldPart = val.slice(0, -op.length).trim();
        if (fieldPart) {
          setInProgress({ field: fieldPart, operator: op, value: '', conjunction: 'AND' });
          setDraft('');
          setPhase('value');
        }
      }
      return;
    }

    if (phase === 'operator') {
      const op = OPERATORS.find((o) => val === o);
      if (op) {
        setInProgress((prev) => prev ? { ...prev, operator: op } : null);
        setDraft('');
        setPhase('value');
        return;
      }
      return;
    }
  };

  const commitExpr = (expr: ExpressionPill) => {
    const newPills = [...pills, expr];
    commitPills(newPills);
    setInProgress(null);
    setPhase('field');
    inputRef.current?.focus();
  };

  const removePill = (idx: number) => {
    commitPills(pills.filter((_, i) => i !== idx));
  };

  const toggleConjunction = (idx: number) => {
    const updated = pills.map((p, i) =>
      i === idx ? { ...p, conjunction: p.conjunction === 'AND' ? 'OR' as const : 'AND' as const } : p
    );
    commitPills(updated);
  };

  return (
    <div ref={containerRef} className="relative">
      <div className="flex flex-wrap items-center gap-1.5 px-3 py-2 border border-[var(--color-border)] rounded-lg bg-white min-h-[40px] focus-within:border-sunset-400 transition-colors">
        {/* Existing expression pills */}
        {pills.map((pill, i) => (
          <span key={i} className="inline-flex items-center text-sm">
            {/* Conjunction toggle */}
            {i > 0 && (
              <button
                onClick={() => toggleConjunction(i)}
                className="mx-1 px-1.5 py-0.5 text-xs font-bold rounded bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
              >
                {pill.conjunction}
              </button>
            )}
            {/* Expression group as seamless pill */}
            <span className="inline-flex items-center rounded-md overflow-hidden shadow-sm">
              <span className="px-2 py-0.5 bg-purple-100 text-purple-800 text-xs font-medium">
                {pill.field}
              </span>
              <span className="px-1.5 py-0.5 bg-blue-100 text-blue-800 text-xs font-mono">
                {pill.operator}
              </span>
              <span className="px-2 py-0.5 bg-amber-100 text-amber-800 text-xs">
                {pill.value}
              </span>
            </span>
            <button
              onClick={() => removePill(i)}
              className="ml-0.5 text-gray-400 hover:text-gray-600 text-xs leading-none"
            >
              ✕
            </button>
          </span>
        ))}

        {/* Active expression being typed */}
        {inProgress && (
          <span className="inline-flex items-center rounded-md overflow-hidden shadow-sm">
            {inProgress.field && (
              <span className="px-2 py-0.5 bg-purple-100 text-purple-800 text-xs font-medium">
                {inProgress.field}
              </span>
            )}
            {!inProgress.field && phase === 'field' && (
              <span className="px-2 py-0.5 bg-purple-100 text-purple-800 text-xs font-medium min-w-[40px]">
                {draft || '\u00A0'}
              </span>
            )}
            {inProgress.operator && (
              <span className="px-1.5 py-0.5 bg-blue-100 text-blue-800 text-xs font-mono">
                {inProgress.operator}
              </span>
            )}
            {phase === 'operator' && inProgress.field && (
              <span className="px-1.5 py-0.5 bg-blue-100 text-blue-800 text-xs font-mono min-w-[24px]">
                {draft || '\u00A0'}
              </span>
            )}
            {phase === 'value' && (
              <span className="px-2 py-0.5 bg-amber-100 text-amber-800 text-xs min-w-[24px]">
                {draft || '\u00A0'}
              </span>
            )}
          </span>
        )}

        {/* Draft input */}
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (!draft && pills.length === 0) {
              setShowEmptySuggestions(true);
            }
          }}
          placeholder={pills.length === 0 ? 'Filter data…' : '+ Add filter'}
          className="flex-1 min-w-[120px] border-none outline-none text-sm bg-transparent text-[var(--color-text)] placeholder-gray-400"
        />
      </div>

      {/* Autocomplete dropdown */}
      {showAutocomplete && matchingFields.length > 0 && (
        <div className="absolute z-50 top-full mt-1 left-0 right-0 bg-white border border-[var(--color-border)] rounded-lg shadow-lg max-h-48 overflow-y-auto">
          {matchingFields.map((f, i) => (
            <button
              key={f}
              onMouseDown={(e) => { e.preventDefault(); acceptField(f); }}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                i === highlightIdx ? 'bg-purple-50 text-purple-800' : 'text-[var(--color-text)] hover:bg-gray-50'
              }`}
            >
              <span className="font-mono text-xs">{f}</span>
            </button>
          ))}
          <div className="px-3 py-1.5 text-xs text-gray-400 border-t border-gray-100">
            Tab to accept
          </div>
        </div>
      )}

      {/* Empty-state suggestions */}
      {showEmptySuggestions && draft === '' && (
        <div className="absolute z-50 top-full mt-1 left-0 right-0 bg-white border border-[var(--color-border)] rounded-lg shadow-lg">
          <div className="px-3 py-1.5 text-xs text-gray-400 font-medium">Quick filters</div>
          {EMPTY_SUGGESTIONS.map((sug, i) => (
            <button
              key={`${sug.field}-${sug.operator}-${sug.value}`}
              onMouseDown={(e) => { e.preventDefault(); acceptSuggestion(sug); }}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                i === highlightIdx ? 'bg-purple-50 text-purple-800' : 'text-[var(--color-text)] hover:bg-gray-50'
              }`}
            >
              <span className="inline-flex items-center gap-1">
                <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 text-xs font-medium">{sug.field}</span>
                <span className="px-1 py-0.5 rounded bg-blue-100 text-blue-700 text-xs font-mono">{sug.operator}</span>
                <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-xs">{sug.value}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
