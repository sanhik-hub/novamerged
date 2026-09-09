import { InlineMath } from "react-katex";
import { Component, type ReactNode } from "react";

// ─── Math fragment detection ───────────────────────────────────────────────
const MATH_FRAGMENT = /(?:sqrt\([^()]+\)|[A-Za-z0-9]+(?:\s*(?:\^|_)\s*(?:\{[^}]+\}|[A-Za-z0-9]+))|(?:[A-Za-z0-9]+(?:\s*(?:\/|<=|>=|>\s*=|!=|=|\+|-|\*|×|÷)\s*[A-Za-z0-9]+)+)|\+\/−|\+\/-|<=|>=|>\s*=|!=|\bpi\b)/gi;

// ─── Chemical formula detection ────────────────────────────────────────────
// Matches tokens that look like chemical formulas:
//   optional leading coefficient  (e.g. "6" in "6CO2")
//   one or more element groups    (e.g. "C6", "H12", "O6")
//   optionally followed by charge (e.g. "2+", "3-")
// Examples: H2O, CO2, C6H12O6, H2SO4, Ca(OH)2, 6CO2, NaCl, O2, Fe2O3
const CHEM_TOKEN = /\b(\d*)([A-Z][a-z]?(?:\d+)?(?:[A-Z][a-z]?(?:\d+)?){1,})\b/g;

// Elements we recognise — prevents false-positives on plain words like "To", "In"
const ELEMENT_SYMBOLS = new Set([
  "H","He","Li","Be","B","C","N","O","F","Ne",
  "Na","Mg","Al","Si","P","S","Cl","Ar","K","Ca",
  "Sc","Ti","V","Cr","Mn","Fe","Co","Ni","Cu","Zn",
  "Ga","Ge","As","Se","Br","Kr","Rb","Sr","Y","Zr",
  "Nb","Mo","Tc","Ru","Rh","Pd","Ag","Cd","In","Sn",
  "Sb","Te","I","Xe","Cs","Ba","La","Ce","Pr","Nd",
  "Pm","Sm","Eu","Gd","Tb","Dy","Ho","Er","Tm","Yb",
  "Lu","Hf","Ta","W","Re","Os","Ir","Pt","Au","Hg",
  "Tl","Pb","Bi","Po","At","Rn","Fr","Ra","Ac","Th",
  "Pa","U","Np","Pu","Am","Cm","Bk","Cf","Es","Fm",
  "Md","No","Lr","Rf","Db","Sg","Bh","Hs","Mt","Ds",
  "Rg","Cn","Nh","Fl","Mc","Lv","Ts","Og",
]);

/** Returns true if the string starts with a known element symbol. */
function startsWithElement(s: string): boolean {
  // Check two-char symbol first, then one-char
  return ELEMENT_SYMBOLS.has(s.slice(0, 2)) || ELEMENT_SYMBOLS.has(s.slice(0, 1));
}

/**
 * Render a plain-text string with chemical subscripts applied.
 * e.g. "H2O" → <span>H<sub>2</sub>O</span>
 * Numbers that directly follow a letter in a chemical token become <sub>.
 */
function renderChemSubscripts(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let cursor = 0;

  for (const match of text.matchAll(CHEM_TOKEN)) {
    const start  = match.index ?? 0;
    const full   = match[0];          // e.g. "6CO2" or "H2SO4"
    const coeff  = match[1];          // leading digit(s), may be ""
    const formula = match[2];         // e.g. "CO2", "H2SO4"

    // Only treat as chemical if it starts with a recognised element
    if (!startsWithElement(formula)) continue;

    // Push plain text before this match
    if (start > cursor) {
      nodes.push(text.slice(cursor, start));
    }

    // Leading coefficient as normal text
    if (coeff) nodes.push(coeff);

    // Tokenise the formula into element+number groups
    // e.g. "C6H12O6" → ["C",6,"H",12,"O",6]
    const formulaParts: ReactNode[] = [];
    let fi = 0;
    while (fi < formula.length) {
      // Element symbol: one upper-case letter optionally followed by one lower-case
      const elemMatch = /^([A-Z][a-z]?)/.exec(formula.slice(fi));
      if (!elemMatch) { formulaParts.push(formula[fi]); fi++; continue; }
      const elem = elemMatch[1];
      fi += elem.length;
      formulaParts.push(elem);
      // Optional subscript digits
      const numMatch = /^(\d+)/.exec(formula.slice(fi));
      if (numMatch) {
        formulaParts.push(<sub key={`${fi}-sub`}>{numMatch[1]}</sub>);
        fi += numMatch[1].length;
      }
    }
    nodes.push(<span key={`chem-${start}`}>{formulaParts}</span>);

    cursor = start + full.length;
  }

  // Remaining plain text
  if (cursor < text.length) nodes.push(text.slice(cursor));

  return nodes.length > 0 ? nodes : [text];
}

// ─── Types ─────────────────────────────────────────────────────────────────
type TextSegment = { value: string; math: boolean };

// ─── LaTeX conversion ──────────────────────────────────────────────────────
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
  latex = latex.replace(
    /([A-Za-z0-9])\^\s*(?:\{([^}]+)\}|([A-Za-z0-9]+))/g,
    (_m, base: string, braced?: string, plain?: string) => `${base}^{${braced ?? plain}}`,
  );
  latex = latex.replace(
    /([A-Za-z0-9])_\s*(?:\{([^}]+)\}|([A-Za-z0-9]+))/g,
    (_m, base: string, braced?: string, plain?: string) => `${base}_{${braced ?? plain}}`,
  );
  latex = latex.replace(/\b([A-Za-z0-9]+)\s*\/\s*([A-Za-z0-9]+)\b/g, "\\frac{$1}{$2}");

  return latex;
}

// ─── Math splitting ────────────────────────────────────────────────────────
function splitMath(value: string): TextSegment[] {
  const segments: TextSegment[] = [];
  let cursor = 0;

  for (const match of value.matchAll(MATH_FRAGMENT)) {
    const start    = match.index ?? 0;
    const fragment = match[0];
    if (start > cursor) segments.push({ value: value.slice(cursor, start), math: false });
    segments.push({ value: fragment, math: true });
    cursor = start + fragment.length;
  }

  if (cursor < value.length) segments.push({ value: value.slice(cursor), math: false });
  return segments.length > 0 ? segments : [{ value, math: false }];
}

// ─── Error boundary ────────────────────────────────────────────────────────
class MathErrorBoundary extends Component<
  { original: string; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError(): { failed: boolean } { return { failed: true }; }
  render() { return this.state.failed ? this.props.original : this.props.children; }
}

// ─── Renderers ─────────────────────────────────────────────────────────────
function MathFragment({ value }: { value: string }) {
  return (
    <MathErrorBoundary original={value}>
      <InlineMath math={convertToLatex(value)} />
    </MathErrorBoundary>
  );
}

// ─── Public component ──────────────────────────────────────────────────────
export default function MathText({ children }: { children: string }) {
  return (
    <span className="math-text">
      {splitMath(children).map((segment, index) =>
        segment.math ? (
          <MathFragment key={`${index}-${segment.value}`} value={segment.value} />
        ) : (
          // Plain-text segment: apply chemical subscripts
          <span key={`${index}-${segment.value}`}>
            {renderChemSubscripts(segment.value).map((node, ni) => (
              typeof node === "string"
                ? <span key={ni}>{node}</span>
                : <span key={ni}>{node}</span>
            ))}
          </span>
        ),
      )}
    </span>
  );
}
