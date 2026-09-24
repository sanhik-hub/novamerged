import React from "react";
import MathText from "./MathText";

type WorkspaceSolutionTextProps = {
  children: string;
  className?: string;
};

function normalizeSolutionMath(value: string) {
  return value
    .trim()
    .replace(/−/g, "-")
    .replace(/∗/g, "*")
    .replace(/×/g, "*")
    .replace(/\b1sqrt\b/gi, "1/sqrt")
    .replace(/\bddx\b/gi, "d/dx")
    .replace(/\bdudx\b/gi, "du/dx")
    .replace(/\bdydx\b/gi, "dy/dx")
    .replace(/\bdydu\b/gi, "dy/du")
    .replace(/\bxa\b/g, "x/a")
    .replace(/\b1a\b/g, "1/a")
    .replace(/\ba∗sqrt\b/gi, "a*sqrt")
    .replace(/\ba\*sqrt\b/gi, "a*sqrt");
}

/*
 * Explicitly backtick-delimited mathematical expressions.
 *
 * Examples:
 *   `x/a`
 *   `dydx`
 *   `sqrt(a^2-x^2)`
 *   `a*sqrt(1-x^2/a^2)`
 */
const MATH_TOKEN =
  /`[^`]+`(?:\s*\([^)]*\))?|`[^`]+`/g;

function renderLine(line: string, lineIndex: number) {
  const explicitMatches = [...line.matchAll(MATH_TOKEN)];

  /*
   * If the source contains explicit backtick math, preserve that
   * behaviour and render each expression through MathText.
   */
  if (explicitMatches.length > 0) {
    const nodes: React.ReactNode[] = [];
    let cursor = 0;

    for (const match of explicitMatches) {
      const start = match.index ?? 0;
      const rawValue = match[0];

      if (start > cursor) {
        nodes.push(
          <span key={`text-${lineIndex}-${cursor}`}>
            {line.slice(cursor, start)}
          </span>,
        );
      }

      const value = rawValue
        .replace(/^`/, "")
        .replace(/`(\s*\([^)]*\))?$/, "$1");

      nodes.push(
        <MathText key={`math-${lineIndex}-${start}`}>
          {normalizeSolutionMath(value)}
        </MathText>,
      );

      cursor = start + rawValue.length;
    }

    if (cursor < line.length) {
      nodes.push(
        <span key={`text-${lineIndex}-${cursor}`}>
          {line.slice(cursor)}
        </span>,
      );
    }

    return nodes;
  }

  /*
   * Newer solution responses often contain mathematical expressions
   * without backticks, e.g.
   *
   *   sqrt(a^2 - x^2)
   *   a*sin(theta)
   *   cos^2(theta)
   *
   * MathText already knows how to detect these expressions, so send
   * the whole line through it when there are no explicit backticks.
   */
  return (
    <MathText key={`math-line-${lineIndex}`}>
      {normalizeSolutionMath(line)}
    </MathText>
  );
}

function splitSolutionIntoParagraphs(solution: string) {
  const normalized = String(solution)
    .replace(/\r\n?/g, "\n")
    .trim();

  if (!normalized) {
    return [];
  }

  const steps = normalized
    .split(/(?=\bStep\s+\d+\s*:)/gi)
    .map((part) => part.trim())
    .filter(Boolean);

  if (steps.length > 1) {
    return steps;
  }

  return normalized
    .split(/\n\s*\n+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export default function WorkspaceSolutionText({
  children,
  className,
}: WorkspaceSolutionTextProps) {
  const paragraphs = splitSolutionIntoParagraphs(children);

  return (
    <div
      className={
        className
          ? `workspace-solution-text ${className}`
          : "workspace-solution-text"
      }
    >
      {paragraphs.map((paragraph, index) => (
        <div className="workspace-solution-line" key={index}>
          {renderLine(paragraph, index)}
        </div>
      ))}
    </div>
  );
}
