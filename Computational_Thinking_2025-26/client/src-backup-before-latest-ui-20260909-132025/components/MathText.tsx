import { InlineMath } from "react-katex";
import { Component, type ReactNode } from "react";

const MATH_FRAGMENT = /(?:sqrt\([^()]+\)|[A-Za-z0-9]+(?:\s*(?:\^|_)\s*(?:\{[^}]+\}|[A-Za-z0-9]+))|(?:[A-Za-z0-9]+(?:\s*(?:\/|<=|>=|>\s*=|!=|=|\+|-|\*|×|÷)\s*[A-Za-z0-9]+)+)|\+\/−|\+\/-|<=|>=|>\s*=|!=|\bpi\b)/gi;

type TextSegment = {
  value: string;
  math: boolean;
};

function convertToLatex(value: string): string {
  let latex = value.trim()
    .replace(/>\s*=/g, "\\geq")
    .replace(/<=/g, "\\leq")
    .replace(/>=/g, "\\geq")
    .replace(/!=/g, "\\neq")
    .replace(/\+\/−|\+\/-/g, "\\pm")
    .replace(/±/g, "\\pm")
    .replace(/×/g, "\\times")
    .replace(/÷/g, "\\div")
    .replace(/\bpi\b/gi, "\\pi");

  latex = latex.replace(/sqrt\(([^()]+)\)/gi, "\\sqrt{$1}");
  latex = latex.replace(/([A-Za-z0-9])\^\s*(?:\{([^}]+)\}|([A-Za-z0-9]+))/g, (_match, base: string, braced: string | undefined, plain: string | undefined) => (
    `${base}^{${braced ?? plain}}`
  ));
  latex = latex.replace(/([A-Za-z0-9])_\s*(?:\{([^}]+)\}|([A-Za-z0-9]+))/g, (_match, base: string, braced: string | undefined, plain: string | undefined) => (
    `${base}_{${braced ?? plain}}`
  ));
  latex = latex.replace(/\b([A-Za-z0-9]+)\s*\/\s*([A-Za-z0-9]+)\b/g, "\\frac{$1}{$2}");

  return latex;
}

function splitMath(value: string): TextSegment[] {
  const segments: TextSegment[] = [];
  let cursor = 0;

  for (const match of value.matchAll(MATH_FRAGMENT)) {
    const start = match.index ?? 0;
    const fragment = match[0];
    if (start > cursor) {
      segments.push({ value: value.slice(cursor, start), math: false });
    }
    segments.push({ value: fragment, math: true });
    cursor = start + fragment.length;
  }

  if (cursor < value.length) {
    segments.push({ value: value.slice(cursor), math: false });
  }

  return segments.length > 0 ? segments : [{ value, math: false }];
}

class MathErrorBoundary extends Component<
  { original: string; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.original : this.props.children;
  }
}

function MathFragment({ value }: { value: string }) {
  const latex = convertToLatex(value);
  return (
    <MathErrorBoundary original={value}>
      <InlineMath math={latex} />
    </MathErrorBoundary>
  );
}

export default function MathText({ children }: { children: string }) {
  return (
    <span className="math-text">
      {splitMath(children).map((segment, index) => (
        segment.math
          ? <MathFragment key={`${index}-${segment.value}`} value={segment.value} />
          : <span key={`${index}-${segment.value}`}>{segment.value}</span>
      ))}
    </span>
  );
}
