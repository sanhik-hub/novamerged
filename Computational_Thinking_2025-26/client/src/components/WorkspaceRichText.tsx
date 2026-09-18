import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

type WorkspaceRichTextProps = {
  children: string;
  className?: string;
};

export default function WorkspaceRichText({
  children,
  className,
}: WorkspaceRichTextProps) {
  return (
    <div className={className ? `workspace-rich-text ${className}` : "workspace-rich-text"}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          a: ({ node: _node, ...props }) => (
            <a {...props} target="_blank" rel="noreferrer" />
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
